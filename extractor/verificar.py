"""Verificación asistida por LLM de una regeneración, con autorreparación.

Tras `build`, compara cada artículo cambiado contra el texto crudo de las
páginas del PDF donde aparece y decide si la extracción es fiel al PDF o trae
un artefacto (pie de página colado, texto omitido, orden roto...). No juzga si
el cambio es una reforma de fondo: el repo debe reflejar lo que dice el PDF.

Además corre una comprobación determinista de cobertura (`cobertura`): cada
párrafo extraído debe estar literal en el PDF y no puede quedar texto sin
extraer entre párrafos. Si falla, el veredicto es artefacto diga lo que diga
el LLM.

El LLM nunca redacta texto legal. Solo puede:
  - emitir un veredicto por artículo, y
  - señalar líneas del PDF que son mobiliario de página (encabezado, pie,
    numeración). Cada línea señalada se comprueba de forma determinista (debe
    repetirse en el borde de muchas páginas) antes de convertirse en un patrón
    de `fuente/ruido.json`, que el parser descarta en la siguiente pasada.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from .parse import extract_clean_text
from .perfil import PerfilFuente, pagina

MODELO_DEFAULT = "gpt-5.4-mini"
MODELO_FUERTE_DEFAULT = "gpt-5.5"   # segunda opinión de lo que no salga "fiel"
MAX_ARTICULOS = 60           # artículos verificados por pasada (control de costo)
MAX_PAGINAS_CONTEXTO = 6     # páginas crudas por artículo en el prompt
MAX_BLOQUE_CHARS = 1500
MAX_ARTICULO_CHARS = 12000   # texto completo del artículo en el prompt
MAX_HUECO = 0                # caracteres del PDF sin extraer tolerados entre párrafos
MAX_RONDAS = 2               # pasadas de reparar → regenerar → reverificar
BORDE_LINEAS = 2             # una línea de ruido vive en las N primeras/últimas
FRACCION_PAGINAS_RUIDO = 0.3
MIN_PAGINAS_RUIDO = 3

RUIDO_PATH = Path("fuente") / "ruido.json"
VEREDICTOS = ("fiel", "artefacto", "incierto")


# ------------------------------------------------------------------ ruido

def cargar_ruido(out: str | Path) -> tuple[re.Pattern, ...]:
    path = Path(out) / RUIDO_PATH
    if not path.exists():
        return ()
    patrones = json.loads(path.read_text(encoding="utf-8")).get("patrones", [])
    return tuple(re.compile(p) for p in patrones)


def con_ruido(perfil: PerfilFuente, out: str | Path) -> PerfilFuente:
    """Perfil + los patrones de ruido aprendidos para ese repo de datos."""
    extra = cargar_ruido(out)
    return replace(perfil, ruido_res=perfil.ruido_res + extra) if extra else perfil


def _guardar_ruido(out: str | Path, nuevos: list[str]) -> None:
    path = Path(out) / RUIDO_PATH
    previos = (json.loads(path.read_text(encoding="utf-8")).get("patrones", [])
               if path.exists() else [])
    patrones = sorted(set(previos) | set(nuevos))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"patrones": patrones}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _mascara(linea: str) -> str:
    return re.sub(r"\d+", "#", " ".join(linea.split()))


def _bordes(pagina: str) -> set[str]:
    lineas = [l for l in (x.strip() for x in pagina.splitlines()) if l]
    return {_mascara(l) for l in lineas[:BORDE_LINEAS] + lineas[-BORDE_LINEAS:]}


def _ya_descartada(linea: str, perfil: PerfilFuente) -> bool:
    s = linea.strip()
    return bool((perfil.header_prefixes and s.startswith(perfil.header_prefixes))
                or (perfil.page_footer_re and perfil.page_footer_re.match(s))
                or any(r.match(s) for r in perfil.ruido_res))


def patrones_de_ruido(lineas: list[str], paginas: list[str]) -> list[str]:
    """Convierte líneas señaladas por el LLM en regex, solo si de verdad son
    mobiliario de página: la misma línea (dígitos enmascarados) en el borde de
    una fracción alta de las páginas. El texto legal no cumple eso."""
    umbral = max(MIN_PAGINAS_RUIDO, int(len(paginas) * FRACCION_PAGINAS_RUIDO))
    bordes = [_bordes(p) for p in paginas]
    patrones = []
    for linea in lineas:
        m = _mascara(linea)
        if not m or sum(m in b for b in bordes) < umbral:
            continue
        cuerpo = re.escape(m).replace(r"\#", r"\d+").replace(r"\ ", r"\s+")
        patrones.append(f"^{cuerpo}$")
    return sorted(set(patrones))


# ------------------------------------------------------------------ cambios

@dataclass
class Cambio:
    clave: str
    antes: str
    despues: str

    def bloques(self) -> tuple[list[str], list[str]]:
        """(eliminados, añadidos) a nivel de párrafo."""
        a = [b for b in self.antes.split("\n\n") if b.strip()]
        d = [b for b in self.despues.split("\n\n") if b.strip()]
        sa, sd = set(a), set(d)
        return [b for b in a if b not in sd], [b for b in d if b not in sa]


def _git(out: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(out), *args],
                          capture_output=True, text=True).stdout


def cambios(out: str | Path) -> list[Cambio]:
    """Artículos cuyo texto difiere de HEAD en el árbol de trabajo."""
    out = Path(out)
    claves = set()
    for line in _git(out, "status", "--porcelain", "--no-renames", "--", "articulos").splitlines():
        path = line[3:].strip()
        if path.endswith(".md"):
            claves.add(Path(path).stem)
    res = []
    for clave in sorted(claves):
        actual = out / "articulos" / f"{clave}.md"
        res.append(Cambio(
            clave=clave,
            antes=_git(out, "show", f"HEAD:./articulos/{clave}.md"),
            despues=actual.read_text(encoding="utf-8") if actual.exists() else "",
        ))
    return res


# ------------------------------------------------------------------ contexto

def paginas_crudas(pdf_path: str, perfil: PerfilFuente | None = None) -> list[str]:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return [(pagina(page, perfil) if perfil else page).extract_text() or "" for page in pdf.pages]


def _norm(s: str) -> str:
    d = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in d if unicodedata.category(c) != "Mn"))


def _coincidencias(bloque: str, normas: list[str]) -> list[int]:
    nb = _norm(bloque)
    return [i for i, n in enumerate(normas) if nb[:50] in n] if len(nb) >= 20 else []


def paginas_de(bloques: list[str], articulo: list[str], normas: list[str]) -> list[int]:
    """Índices de las páginas donde arrancan (y si hace falta, continúan) los bloques.

    Un mismo párrafo puede repetirse en varios artículos, así que se ancla al
    inicio del artículo: la primera página donde algún bloque suyo es único.
    """
    unicas = [c[0] for b in articulo if len(c := _coincidencias(b, normas)) == 1]
    ancla = min(unicas, default=0)
    idx: list[int] = []
    for b in bloques:
        cands = _coincidencias(b, normas)
        if not cands:
            continue
        p = min((c for c in cands if c >= ancla), default=cands[0])
        idx.append(p)
        if _norm(b)[-40:] not in normas[p] and p + 1 < len(normas):
            idx.append(p + 1)
    return sorted(set(idx))[:MAX_PAGINAS_CONTEXTO]


# ------------------------------------------------------------------ cobertura

# Encabezados estructurales que el parser consume como contexto, no como cuerpo.
ENCABEZADO_RE = re.compile(
    r"\b(?:T[íi]tulo\s+[a-záéíóú]+|Cap[íi]tulo\s+(?:[IVXLC]+|[úu]nico)(?:\s+(?:Bis|Ter|Qu[áa]ter))?)\b",
    re.IGNORECASE)


@dataclass
class Flujo:
    """Texto limpio del PDF + su forma normalizada, con índice de vuelta."""
    texto: str
    norma: str
    idx: list[int]

    @classmethod
    def de(cls, texto: str) -> "Flujo":
        norma, idx = [], []
        for i, ch in enumerate(texto):
            n = _norm(ch)
            norma.append(n)
            idx.extend([i] * len(n))
        return cls(texto, "".join(norma), idx)

    def original(self, a: int, b: int) -> str:
        return " ".join(self.texto[self.idx[a]:self.idx[b - 1] + 1].split())


_TITULO_MD_RE = re.compile(r"^# Art[íi]culo (\d+)(?:\.(\d+))?\S* ?(.*)$", re.MULTILINE)


def _encabezado_propio(md: str) -> re.Pattern | None:
    """Forma normalizada del encabezado del artículo en el PDF, a partir del
    título del .md: "articulo" (o "articulos", errata), el número, el ordinal
    "o" opcional ("1o."), el subnúmero y el sufijo ("7a", "163quater")."""
    m = _TITULO_MD_RE.search(md)
    if not m:
        return None
    num, sub, suf = m.group(1), m.group(2) or "", _norm(m.group(3))
    return re.compile(rf"articulos?{num}o?{sub}{suf}")


# Bloque de encabezado entre notas previas (`notas_previas_encabezado`):
# "CAPITULO II De los Habitantes del Estado", "TÍTULO PRIMERO", "CAPITULO III TER".
_ESTRUCTURA_RE = re.compile(
    r"(?:(?:T[íi]tulo|Cap[íi]tulo|Secci[óo]n)\s+[^\s.]+(?:\s+(?:Bis|Ter|Qu[áa]ter|[A-Z]))?\.?"
    r"(?:\s+[^.;:()]{1,200}?\.?)?\s*)+", re.IGNORECASE)
_ART_EN_HUECO_RE = re.compile(r"\bArt[íi]culos?\b", re.IGNORECASE)
_NOTA_MD_RE = re.compile(r"_?\(.*\)\.?_?", re.DOTALL)
MAX_HUECO_ESTRUCTURA = 600


def cobertura(md: str, flujo: Flujo) -> list[dict]:
    """Comprobación determinista de un artículo extraído contra el PDF: cada
    párrafo debe estar literal y en orden, y entre párrafos consecutivos no
    puede quedar texto del PDF sin extraer."""
    crudos = [b.strip() for b in md.split("\n\n")
              if b.strip() and not b.startswith("# ") and _norm(b)]
    bloques = [_norm(b) for b in crudos]
    unicos = [(len(b), i) for i, b in enumerate(bloques) if flujo.norma.count(b) == 1]
    if not unicos:
        # Artículo sin ningún párrafo único (p. ej. "Derogado."): solo literalidad.
        return [{"tipo": "no_literal", "fragmento": b[:120]}
                for b in bloques if b not in flujo.norma]
    k = max(unicos)[1]
    ini = flujo.norma.find(bloques[k])
    fin = ini + len(bloques[k])
    problemas: list[dict] = []
    # Con `notas_previas` las notas que preceden al encabezado abren el artículo,
    # así que el propio encabezado ("Artículo 7º- A.") queda entre ellas y el
    # primer párrafo. Se tolera ese hueco, una vez, si es exactamente el
    # encabezado de este artículo. Con `notas_previas_encabezado` entre esas
    # notas puede quedar además un encabezado de Título/Capítulo/Sección; se
    # tolera solo mientras todo lo anterior del artículo sean notas.
    propio = _encabezado_propio(md)
    tolerado = False

    def solo_estructura(texto: str, antes: int) -> bool:
        if len(texto) > MAX_HUECO_ESTRUCTURA or not all(
                _NOTA_MD_RE.fullmatch(c) for c in crudos[:antes]):
            return False
        arts = list(_ART_EN_HUECO_RE.finditer(texto))
        corte = arts[-1].start() if arts else len(texto)
        previo, cola = texto[:corte].strip(), _norm(texto[corte:])
        return ((not previo or bool(_ESTRUCTURA_RE.fullmatch(previo)))
                and (not cola or bool(not tolerado and propio and propio.fullmatch(cola))))

    def hueco(a: int, b: int, antes: int) -> None:
        nonlocal tolerado
        if b - a <= MAX_HUECO:
            return
        texto = flujo.original(a, b)
        resto = _norm(ENCABEZADO_RE.sub("", texto))
        if not resto:
            return
        if not tolerado and propio and propio.fullmatch(resto):
            tolerado = True
            return
        if solo_estructura(texto, antes):
            if _ART_EN_HUECO_RE.search(texto):
                tolerado = True
            return
        problemas.append({"tipo": "texto_omitido", "fragmento": texto})

    for t in range(k + 1, len(bloques)):
        b = bloques[t]
        p = flujo.norma.find(b, fin)
        if p == -1:
            problemas.append({"tipo": "no_literal", "fragmento": b[:120]})
            continue
        hueco(fin, p, t)
        fin = p + len(b)
    for t in reversed(range(k)):
        b = bloques[t]
        p = flujo.norma.rfind(b, 0, ini)
        if p == -1:
            problemas.append({"tipo": "no_literal", "fragmento": b[:120]})
            continue
        hueco(p + len(b), ini, t + 1)
        ini = p
    return problemas


# ------------------------------------------------------------------ LLM

PROMPT = """Eres verificador de un sistema que versiona leyes mexicanas en git. \
Un extractor automático convirtió el PDF oficial a texto y, respecto de la versión \
anterior, cambió el artículo {clave} de: {nombre}.

Tu única tarea: decidir si los BLOQUES AÑADIDOS reproducen fielmente lo que dice el \
PDF. No evalúes si el cambio es una reforma de fondo, editorial o de puntuación: si el \
PDF lo dice así, es fiel. La ausencia de una nota de reforma no es señal de nada.

Reglas:
- Todo bloque añadido es copia literal del PDF una vez descartadas las líneas que el \
extractor reconoce como encabezado o pie. Los encabezados y pies que veas en el texto \
crudo son normales: solo son un problema si aparecen DENTRO de los bloques añadidos.
- Solo se listan los bloques que cambiaron. Los párrafos del artículo que no cambiaron \
NO aparecen entre los añadidos; consulta el texto completo del artículo antes de decir \
que falta algo.
- Las páginas del PDF cubren solo la zona de los bloques cambiados.
- Diferencias de saltos de línea o de dónde se parte un párrafo no son artefacto si \
las palabras son las mismas y están en el mismo orden. Erratas del propio PDF tampoco.

Es "artefacto" si dentro de un bloque añadido hay numeración de página o encabezados \
colados, texto de otro artículo, palabras fuera de orden o duplicadas, o si el PDF \
tiene, en la zona de un bloque añadido, texto legal que no está en el artículo completo.

BLOQUES ELIMINADOS (versión anterior):
{eliminados}

BLOQUES AÑADIDOS (extracción nueva):
{anadidos}

TEXTO COMPLETO DEL ARTÍCULO (extracción nueva):
{articulo}

TEXTO CRUDO DEL PDF:
{paginas}

Responde SOLO un objeto JSON:
{{
  "veredicto": "fiel" | "artefacto" | "incierto",
  "explicacion": "una o dos frases, en español",
  "problemas": [{{"tipo": "ruido_pagina" | "texto_faltante" | "duplicado" | "orden" | "otro", "fragmento": "cita literal breve"}}],
  "lineas_ruido": ["líneas COMPLETAS del texto crudo del PDF, copiadas literalmente, que son encabezado, pie o numeración de página y no texto legal"]
}}
"problemas" va vacío si el veredicto es "fiel". "incierto" = no puedes decidir con lo dado."""


def openai_call(modelo: str) -> Callable[[str], str]:
    from openai import OpenAI
    client = OpenAI()

    def call(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=modelo,
            max_completion_tokens=8000,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    return call


def _recorta(bloques: list[str]) -> str:
    if not bloques:
        return "(ninguno)"
    return "\n\n".join(b if len(b) <= MAX_BLOQUE_CHARS else b[:MAX_BLOQUE_CHARS] + " […]"
                       for b in bloques)


@dataclass
class Veredicto:
    clave: str
    veredicto: str
    explicacion: str = ""
    problemas: list[dict] = field(default_factory=list)
    lineas_ruido: list[str] = field(default_factory=list)


def verificar_cambio(c: Cambio, paginas: list[str], normas: list[str],
                     call: Callable[[str], str], perfil: PerfilFuente) -> Veredicto:
    eliminados, anadidos = c.bloques()
    articulo = [b for b in (c.despues or c.antes).split("\n\n") if b.strip()]
    idx = paginas_de(anadidos or eliminados, articulo, normas)
    crudo = "\n\n".join(f"=== PÁGINA {i + 1} ===\n{paginas[i]}" for i in idx) \
        or "(no se localizó el artículo en el PDF)"
    completo = (c.despues if len(c.despues) <= MAX_ARTICULO_CHARS
                else "(omitido por extensión; no afirmes que falta texto)")
    prompt = PROMPT.format(clave=c.clave, nombre=perfil.nombre,
                           eliminados=_recorta(eliminados), anadidos=_recorta(anadidos),
                           articulo=completo or "(artículo eliminado)", paginas=crudo)
    try:
        data = json.loads(call(prompt))
    except Exception as e:
        return Veredicto(c.clave, "incierto", f"el verificador falló: {e}")
    v = data.get("veredicto")
    return Veredicto(
        clave=c.clave,
        veredicto=v if v in VEREDICTOS else "incierto",
        explicacion=str(data.get("explicacion", "")),
        problemas=[p for p in data.get("problemas", []) if isinstance(p, dict)],
        lineas_ruido=[l for l in data.get("lineas_ruido", []) if isinstance(l, str)],
    )


# ------------------------------------------------------------------ orquestación

@dataclass
class Resultado:
    veredictos: list[Veredicto]
    total_cambios: int
    patrones_nuevos: list[str]
    rondas: int

    @property
    def ok(self) -> bool:
        return (all(v.veredicto == "fiel" for v in self.veredictos)
                and self.total_cambios <= len(self.veredictos))


def verificar(pdf_path: str, out: str | Path, perfil: PerfilFuente,
              call: Callable[[str], str] | None, *, reparar: bool = False,
              rebuild: Callable[[PerfilFuente], None] | None = None,
              call_fuerte: Callable[[str], str] | None = None) -> Resultado:
    """Verifica los artículos cambiados; con `reparar`, aprende ruido de página,
    regenera con `rebuild` y vuelve a verificar (hasta MAX_RONDAS).

    Lo que `call` no dé por fiel se reevalúa con `call_fuerte` (modelo más
    capaz), cuyo veredicto es el definitivo."""
    paginas = paginas_crudas(pdf_path, perfil)
    normas = [_norm(p) for p in paginas]
    base = perfil
    aprendidos: list[str] = []
    ronda = 0
    while True:
        ronda += 1
        todos = cambios(out)
        flujo = Flujo.de(extract_clean_text(pdf_path, perfil=perfil))

        def evaluar(c: Cambio) -> Veredicto:
            if call is None:
                v = Veredicto(c.clave, "fiel", "Cobertura determinista en verde.")
            else:
                v = verificar_cambio(c, paginas, normas, call, perfil)
                if v.veredicto != "fiel" and call_fuerte:
                    v = verificar_cambio(c, paginas, normas, call_fuerte, perfil)
            duros = cobertura(c.despues, flujo)
            if duros:
                v = replace(v, veredicto="artefacto", problemas=duros + v.problemas,
                            explicacion="El texto extraído no coincide con el PDF "
                                        "(comprobación determinista). "
                                        + ("" if v.veredicto == "fiel" else v.explicacion))
            return v

        with ThreadPoolExecutor(max_workers=6) as pool:
            veredictos = list(pool.map(evaluar, todos[:MAX_ARTICULOS]))
        lineas = [l for v in veredictos for l in v.lineas_ruido
                  if not _ya_descartada(l, perfil)]
        ya = set(p.pattern for p in cargar_ruido(out))
        nuevos = [p for p in patrones_de_ruido(lineas, paginas) if p not in ya]
        if not (reparar and rebuild and nuevos and ronda <= MAX_RONDAS):
            return Resultado(veredictos, len(todos), aprendidos, ronda)
        _guardar_ruido(out, nuevos)
        aprendidos += nuevos
        perfil = con_ruido(base, out)
        rebuild(perfil)


def auditar(pdf_path: str, out: str | Path, perfil: PerfilFuente) -> dict:
    """Cobertura determinista de TODOS los artículos del repo de datos contra
    el PDF. Sirve de línea base: un cambio al extractor no puede sumar claves."""
    flujo = Flujo.de(extract_clean_text(pdf_path, perfil=perfil))
    arts = sorted((Path(out) / "articulos").glob("*.md"))
    malos = {a.stem: pr for a in arts
             if (pr := cobertura(a.read_text(encoding="utf-8"), flujo))}
    return {"total": len(arts), "con_problemas": malos}


ICONO = {"fiel": "✅", "artefacto": "❌", "incierto": "❔"}


def reporte_md(r: Resultado) -> str:
    lineas = ["### 🔬 Verificación de la extracción (LLM vs. PDF)", ""]
    if not r.veredictos:
        lineas.append("Sin artículos cambiados tras la verificación.")
    elif r.ok:
        lineas.append("Todos los cambios reproducen fielmente el PDF oficial.")
    else:
        lineas.append("**Hay cambios que parecen artefactos de extracción — no mergear sin revisar.**")
    if r.patrones_nuevos:
        lineas += ["", "Se detectó mobiliario de página nuevo en el PDF y se regeneró sin él "
                   "(`fuente/ruido.json`): " + ", ".join(f"`{p}`" for p in r.patrones_nuevos)]
    lineas.append("")
    for v in r.veredictos:
        lineas.append(f"- {ICONO[v.veredicto]} **{v.clave}** — {v.veredicto}: {v.explicacion}")
        for p in v.problemas:
            lineas.append(f"  - `{p.get('tipo', 'otro')}`: «{str(p.get('fragmento', ''))[:160]}»")
    if r.total_cambios > len(r.veredictos):
        lineas += ["", f"_Se verificaron {len(r.veredictos)} de {r.total_cambios} artículos cambiados._"]
    return "\n".join(lineas) + "\n"


def modelo_configurado() -> str:
    return os.environ.get("VERIFICADOR_MODELO") or MODELO_DEFAULT


def modelo_fuerte_configurado() -> str:
    return os.environ.get("VERIFICADOR_MODELO_FUERTE") or MODELO_FUERTE_DEFAULT

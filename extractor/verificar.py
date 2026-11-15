"""Verificación asistida por LLM de una regeneración, con autorreparación.

Tras `build`, compara cada artículo cambiado contra el texto crudo de las
páginas del PDF donde aparece y clasifica el cambio: reforma real o artefacto
de extracción (pie de página colado, texto cortado, orden roto...).

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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from .perfil import PerfilFuente

MODELO_DEFAULT = "gpt-5.4-mini"
MAX_ARTICULOS = 60           # artículos verificados por pasada (control de costo)
MAX_PAGINAS_CONTEXTO = 6     # páginas crudas por artículo en el prompt
MAX_BLOQUE_CHARS = 1500
MAX_RONDAS = 2               # pasadas de reparar → regenerar → reverificar
BORDE_LINEAS = 2             # una línea de ruido vive en las N primeras/últimas
FRACCION_PAGINAS_RUIDO = 0.3
MIN_PAGINAS_RUIDO = 3

RUIDO_PATH = Path("fuente") / "ruido.json"
VEREDICTOS = ("reforma", "artefacto", "mixto", "incierto")


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

def paginas_crudas(pdf_path: str) -> list[str]:
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


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


# ------------------------------------------------------------------ LLM

PROMPT = """Eres verificador de un sistema que versiona leyes mexicanas en git. \
Un extractor automático convirtió el PDF oficial a texto y, respecto de la versión \
anterior, cambió el artículo {clave} de: {nombre}.

Decide si el cambio es una reforma real o un artefacto de extracción, comparando \
contra el texto crudo de las páginas del PDF (incluye encabezados y pies de página).

Todo bloque añadido es copia literal del PDF una vez descartadas las líneas que el \
extractor reconoce como encabezado o pie; el extractor no inventa ni reescribe texto. \
Los encabezados y pies que veas en el texto crudo son normales: solo son un problema \
si aparecen DENTRO de los bloques añadidos.

Señales de artefacto: numeración de página o encabezados colados dentro del texto \
("12 de 416", nombre de la institución), frases cortadas, párrafos duplicados o fuera \
de orden, texto de otro artículo, texto legal del PDF que falta en la extracción.
Señales de reforma real: el nuevo texto se lee completo y coherente en el PDF y suele \
ir acompañado de una nota de reforma con fecha reciente.

BLOQUES ELIMINADOS (versión anterior):
{eliminados}

BLOQUES AÑADIDOS (extracción nueva):
{anadidos}

TEXTO CRUDO DEL PDF:
{paginas}

Responde SOLO un objeto JSON:
{{
  "veredicto": "reforma" | "artefacto" | "mixto" | "incierto",
  "explicacion": "una o dos frases, en español",
  "problemas": [{{"tipo": "ruido_pagina" | "texto_faltante" | "texto_cortado" | "duplicado" | "orden" | "otro", "fragmento": "cita literal breve del texto extraído"}}],
  "lineas_ruido": ["líneas COMPLETAS del texto crudo del PDF, copiadas literalmente, que son encabezado, pie o numeración de página y no texto legal"]
}}
"mixto" = hay reforma real y además artefactos. "incierto" = no puedes decidir con lo dado."""


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
    prompt = PROMPT.format(clave=c.clave, nombre=perfil.nombre,
                           eliminados=_recorta(eliminados), anadidos=_recorta(anadidos),
                           paginas=crudo)
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
        return (all(v.veredicto == "reforma" for v in self.veredictos)
                and self.total_cambios <= len(self.veredictos))


def verificar(pdf_path: str, out: str | Path, perfil: PerfilFuente,
              call: Callable[[str], str], *, reparar: bool = False,
              rebuild: Callable[[PerfilFuente], None] | None = None) -> Resultado:
    """Verifica los artículos cambiados; con `reparar`, aprende ruido de página,
    regenera con `rebuild` y vuelve a verificar (hasta MAX_RONDAS)."""
    paginas = paginas_crudas(pdf_path)
    normas = [_norm(p) for p in paginas]
    aprendidos: list[str] = []
    ronda = 0
    while True:
        ronda += 1
        todos = cambios(out)
        veredictos = [verificar_cambio(c, paginas, normas, call, perfil)
                      for c in todos[:MAX_ARTICULOS]]
        lineas = [l for v in veredictos for l in v.lineas_ruido]
        ya = set(p.pattern for p in cargar_ruido(out))
        nuevos = [p for p in patrones_de_ruido(lineas, paginas) if p not in ya]
        if not (reparar and rebuild and nuevos and ronda <= MAX_RONDAS):
            return Resultado(veredictos, len(todos), aprendidos, ronda)
        _guardar_ruido(out, nuevos)
        aprendidos += nuevos
        rebuild(con_ruido(perfil, out))


ICONO = {"reforma": "✅", "artefacto": "❌", "mixto": "⚠️", "incierto": "❔"}


def reporte_md(r: Resultado) -> str:
    lineas = ["### 🔬 Verificación de la extracción (LLM vs. PDF)", ""]
    if not r.veredictos:
        lineas.append("Sin artículos cambiados tras la verificación.")
    elif r.ok:
        lineas.append("Todos los cambios corresponden al texto del PDF oficial.")
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

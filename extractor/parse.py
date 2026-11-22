"""Segmentación de un PDF legal en artículos estructurados.

El motor es agnóstico a la fuente: toda diferencia entre documentos (CPEUM
federal, constituciones estatales, ...) vive en un `PerfilFuente` (ver
`perfil.py`). El default es `CPEUM`, así que el comportamiento federal previo
se conserva intacto.

Cada PDF entrega texto digital con un encabezado repetido por página; el
articulado termina donde empiezan los "Transitorios". Las notas de reforma
(cuando la fuente las trae inline) van al pie de cada bloque.
"""
from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass, field
from datetime import date

import pdfplumber

from .perfil import CPEUM, PerfilFuente, pagina

# Globales federales conservadas por compatibilidad (apuntan al perfil CPEUM).
ARTICLE_RE = CPEUM.article_re
TITULO_RE = CPEUM.titulo_re
CAPITULO_RE = CPEUM.capitulo_re
TRANSITORIOS_RE = CPEUM.transitorios_re
HEADER_PREFIXES = CPEUM.header_prefixes
PAGE_FOOTER_RE = CPEUM.page_footer_re
VERSION_RE = CPEUM.version_re


def reform_dates_in(text: str) -> list[date]:
    """Fechas de reforma (DOF) en `text`. Federal; ver `PerfilFuente.fechas_de`."""
    return CPEUM.fechas_de(text)


@dataclass
class Article:
    number: int
    suffix: str = ""           # "", "Bis", "Ter"
    titulo: str = ""           # Título al que pertenece
    capitulo: str = ""         # Capítulo al que pertenece
    body: str = ""             # texto completo del artículo
    reform_dates: list[date] = field(default_factory=list)
    label_ordinal: str = "federal"   # estilo del ordinal en la etiqueta
    # Numeración decimal ("Artículo 88.1" → "1"): solo si el `article_re` del
    # perfil captura el grupo nombrado `sub`.
    subnumero: str = ""

    @property
    def key(self) -> str:
        """Identificador estable: '004', '004-bis', '088-1'."""
        base = f"{self.number:03d}"
        if self.subnumero:
            base = f"{base}-{self.subnumero}"
        if not self.suffix:
            return base
        # Sin acentos ni espacios ("Quáter", "Bis A"), pero la ñ se queda: en
        # Coahuila "7 Ñ" sigue a "7 N" y serían el mismo archivo.
        s = unicodedata.normalize("NFKD", self.suffix.lower().replace("ñ", "\0"))
        s = "".join(c for c in s if not unicodedata.combining(c)).replace("\0", "ñ")
        return f"{base}-{re.sub(r'\s+', '-', s.strip())}"

    @property
    def label(self) -> str:
        # Ordinal según la fuente: federal "1o."/"10."; "masc" "1º"; "plano" "1".
        if self.subnumero:
            num = f"{self.number}.{self.subnumero}"
        elif self.label_ordinal == "federal":
            num = f"{self.number}o." if self.number <= 9 else f"{self.number}."
        elif self.label_ordinal == "masc":
            num = f"{self.number}º"
        else:
            num = f"{self.number}"
        suf = f" {self.suffix}" if self.suffix else ""
        return f"Artículo {num}{suf}"

    @property
    def last_reform(self) -> date | None:
        return max(self.reform_dates) if self.reform_dates else None


# Encabezado estructural en su propia línea: "Título Segundo", "Capítulo II",
# "Sección V", "CAPÍTULO ÚNICO", con sufijo opcional ("CAPITULO III TER",
# "TITULO TERCERO A"). Solo la línea entera: "Título Cuarto de esta
# Constitución." o "CAPÍTULO I A los…" son texto de un artículo, no un encabezado.
_ORDINALES = (r"Primer[oa]|Segund[oa]|Tercer[oa]|Cuart[oa]|Quint[oa]|Sext[oa]|"
              r"S[ée]ptim[oa]|Octav[oa]|Noven[oa]|D[ée]cim[oa](?:\s+\w+)?|[ÚU]nic[oa]|"
              r"Preliminar")
ENCABEZADO_RE = re.compile(
    r"^(?:T[íi]tulo|Cap[íi]tulo|Secci[óo]n)\s+(?:[IVXLC]+|\d{1,3}|" + _ORDINALES +
    r")(?:\s+(?:Bis|Ter|Qu[áa]ter|(?-i:[A-Z])))?\.?$", re.IGNORECASE)
# Un bloque de encabezado (encabezado + denominación + nota "Denominación ...
# reformada") es corto: si el siguiente artículo no aparece en estas líneas, la
# línea no era un encabezado estructural y se trata como antes.
MAX_LINEAS_ENCABEZADO = 8


def _strip_headers(page_text: str, perfil: PerfilFuente) -> str:
    lines = []
    for line in page_text.splitlines():
        s = line.strip()
        if perfil.header_prefixes and s.startswith(perfil.header_prefixes):
            continue
        if perfil.page_footer_re and perfil.page_footer_re.match(s):
            continue
        if any(r.match(s) for r in perfil.ruido_res):
            continue
        lines.append(line)
    return "\n".join(lines)


def extract_clean_text(pdf_path: str, *, perfil: PerfilFuente = CPEUM) -> str:
    """Devuelve el texto completo del PDF sin encabezados de página."""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            parts.append(_strip_headers(pagina(page, perfil).extract_text() or "", perfil))
    return "\n".join(parts)


def version_date(pdf_path: str, *, perfil: PerfilFuente = CPEUM) -> date | None:
    """Fecha de la última reforma incorporada al PDF = versión del snapshot."""
    if perfil.version_de is None and perfil.version_re is None:
        return None
    with pdfplumber.open(pdf_path) as pdf:
        paginas = pdf.pages[:perfil.version_paginas] if perfil.version_de else pdf.pages[:1]
        head = "\n".join(pagina(p, perfil).extract_text() or "" for p in paginas)
    if perfil.version_de is not None:        # parser propio de la fuente (estatal)
        return perfil.version_de(head)
    m = perfil.version_re.search(head)       # federal: DOF DD-MM-YYYY
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def _articulado_text(text: str, *, perfil: PerfilFuente = CPEUM) -> str:
    """Recorta el texto al articulado, cortando antes de los Transitorios."""
    m = perfil.transitorios_re.search(text)
    return text[: m.start()] if m else text


def _subnumero(am: re.Match) -> str:
    """Subnúmero decimal del encabezado, si el `article_re` del perfil lo captura."""
    return am.groupdict().get("sub") or ""


def parse(pdf_path: str, *, perfil: PerfilFuente = CPEUM) -> list[Article]:
    """Parsea el PDF y devuelve la lista de artículos en orden."""
    return parse_text(extract_clean_text(pdf_path, perfil=perfil), perfil=perfil)


def parse_text(clean_text: str, start: int = 1, *,
               perfil: PerfilFuente = CPEUM) -> list[Article]:
    """Segmenta texto ya limpio (sin encabezados) en artículos.

    `start` es el número del primer artículo esperado (relevante para el gate
    estricto). El gate del perfil decide cómo se valida la secuencia:
    - "estricto"   (federal): solo el siguiente esperado (rechaza citas inline).
    - "monotonico" (estatal): cualquier número mayor al último (tolera huecos
      por derogación, que en el gate estricto detenían todo el parseo).
    """
    if perfil.preprocess:
        clean_text = perfil.preprocess(clean_text)
    text = _articulado_text(clean_text, perfil=perfil)
    lines = text.splitlines()

    articles: list[Article] = []
    current: Article | None = None
    cur_titulo = ""
    cur_capitulo = ""
    expected = start   # gate estricto: número esperado
    last = start - 1   # gate monotonico: último número aceptado

    def flush(art: Article | None) -> None:
        if art is not None:
            art.body = art.body.strip()
            art.reform_dates = perfil.fechas_de(art.body)
            articles.append(art)

    def acepta(stripped: str) -> bool:
        """¿Esta línea abre un artículo que el gate aceptaría ahora mismo?"""
        am = perfil.article_re.match(stripped)
        if not am:
            return False
        num = int(am.group(1))
        if (num == expected) if perfil.gate == "estricto" else (num > last):
            return True
        return (current is not None and num == current.number
                and bool(am.group(2) or _subnumero(am)))

    def fin_bloque_encabezado(i: int) -> int | None:
        """Si en `i` empieza un bloque de encabezado estructural (Título /
        Capítulo / Sección + su denominación + nota de reforma de la
        denominación) que desemboca en el siguiente artículo, devuelve el
        índice de ese artículo. El bloque pertenece a la estructura, no al
        cuerpo del artículo anterior."""
        if not ENCABEZADO_RE.match(lines[i].strip()):
            return None
        vistas = 0
        for j in range(i + 1, len(lines)):
            if acepta(lines[j].strip()):
                return j
            # Con `notas_previas` las notas del bloque no alargan el bloque: son
            # del artículo que lo cierra, y una racha de seis es común (Tabasco).
            if not (perfil.notas_previas is not None
                    and (not lines[j].strip() or perfil.notas_previas.match(lines[j].strip()))):
                vistas += 1
            if vistas >= MAX_LINEAS_ENCABEZADO:
                return None
        return None

    def titulo_nuevo(titulo: str) -> tuple[str, str]:
        """(título, capítulo) al registrar `titulo`. Un título distinto abre su
        propia división: el capítulo del anterior no sigue vigente (un Título
        sin capítulos no hereda "CAPITULO III" del que lo precede)."""
        return titulo, (cur_capitulo if titulo == cur_titulo else "")

    idx_cuerpo: list[int] = []   # renglones de `lines` que forman el cuerpo actual

    def notas_previas(i: int) -> list[str]:
        """Con `perfil.notas_previas`: las notas de reforma pegadas al encabezado
        de artículo que empieza en `i` (solo renglones en blanco entre ellas). Son
        de ese artículo, no del anterior: se quitan de su cuerpo y se devuelven
        en el orden del PDF. Las de un bloque de encabezado (que el parser no
        copia a ningún cuerpo) también se devuelven; con
        `notas_previas_encabezado`, todas las del bloque y las que lo preceden."""
        if perfil.notas_previas is None or not perfil.article_strip_re.match(lines[i].rstrip()):
            return []

        def es_nota(k: int) -> bool:
            return bool(perfil.notas_previas.match(lines[k].strip()))

        tope, dentro = i, []
        if perfil.notas_previas_encabezado and bloque_desde is not None and saltar_hasta == i:
            tope = bloque_desde
            dentro = [k for k in range(bloque_desde, i) if es_nota(k)]
        j = tope
        while j > 0 and (not lines[j - 1].strip() or es_nota(j - 1)):
            j -= 1
        while j < tope and not lines[j].strip():
            j += 1
        if current is not None and j < tope:
            # Los renglones de la racha que entraron al cuerpo son su cola. Si
            # quitarlos lo deja vacío ("Artículo 115.-" + "(DEROGADO, ...)"), la
            # primera nota es su cuerpo y se queda.
            partes = current.body.split("\n")          # el cuerpo termina en "\n"
            while j < tope:
                quitar = sum(1 for k in idx_cuerpo if k >= j)
                queda = "\n".join(partes[:len(partes) - 1 - quitar]) + "\n"
                em = perfil.article_strip_re.match(queda)
                if queda[em.end() if em else 0:].strip():
                    break
                j += 1
                while j < tope and not lines[j].strip():
                    j += 1
            if j < tope and quitar:
                current.body = queda
                del idx_cuerpo[len(idx_cuerpo) - quitar:]
        previas = [k for k in range(j, tope) if lines[k].strip()]
        return [lines[k].strip() for k in previas + dentro]

    bloque_desde: int | None = None   # inicio del último bloque de encabezado saltado
    saltar_hasta = 0
    for i, raw in enumerate(lines):
        line = raw.rstrip()
        stripped = line.strip()

        if i < saltar_hasta:
            # Dentro de un bloque de encabezado: se registran Título/Capítulo
            # y se descarta la denominación (no es texto de ningún artículo).
            if perfil.titulo_re.match(stripped) and ENCABEZADO_RE.match(stripped):
                cur_titulo, cur_capitulo = titulo_nuevo(stripped)
            elif perfil.capitulo_re.match(stripped):
                cur_capitulo = stripped
            continue
        if current is not None:
            fin = fin_bloque_encabezado(i)
            if fin is not None:
                saltar_hasta = fin
                bloque_desde = i
                if perfil.titulo_re.match(stripped):
                    cur_titulo, cur_capitulo = titulo_nuevo(stripped)
                elif perfil.capitulo_re.match(stripped):
                    cur_capitulo = stripped
                continue

        tm = perfil.titulo_re.match(stripped)
        if tm and current is None or (tm and stripped == tm.group(0)):
            if current is None or len(stripped) < 30:
                cur_titulo, cur_capitulo = titulo_nuevo(stripped)
                continue

        cm = perfil.capitulo_re.match(stripped)
        if cm and (current is None or len(stripped) < 25):
            cur_capitulo = stripped
            continue

        am = perfil.article_re.match(stripped)
        if am:
            num = int(am.group(1))
            suffix = (am.group(2) or "").title()
            if perfil.gate == "estricto":
                is_accept = num == expected
            else:
                is_accept = num > last
            sub = _subnumero(am)
            # "88.1" tras el 88 es, como "88 Bis", una unidad propia del mismo número.
            is_variant = current is not None and num == current.number and bool(suffix or sub)
            if is_accept or is_variant:
                notas = notas_previas(i)
                flush(current)
                current = Article(
                    number=num, suffix=suffix,
                    titulo=cur_titulo, capitulo=cur_capitulo,
                    label_ordinal=perfil.label_ordinal, subnumero=sub,
                )
                current.body = line + "\n"
                idx_cuerpo = [i]
                if notas:
                    # Encabezado, notas (cada una su párrafo) y luego el texto que
                    # seguía al encabezado en su renglón: el normalizador quita
                    # solo la primera línea.
                    em = perfil.article_strip_re.match(line)
                    current.body = (line[:em.end()] + "\n" + "\n\n".join(notas) + "\n\n"
                                    + line[em.end():] + "\n")
                if is_accept:
                    expected = num + 1
                    last = num
                continue

        if current is not None:
            current.body += line + "\n"
            idx_cuerpo.append(i)

    flush(current)
    if perfil.reformas_de is not None:
        tabla = perfil.reformas_de(clean_text)
        for art in articles:
            art.reform_dates = sorted(set(art.reform_dates) | set(tabla.get(art.key, ())))
    return articles

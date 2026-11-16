"""Constitución Política del Estado Libre y Soberano de Quintana Roo."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import perfil_estatal

_INDICE = "https://www.congresoqroo.gob.mx/leyes/176/"

# Encabezados pegados al texto y sufijos latinos más allá de Ter: el regex
# genérico los fundía con el artículo anterior.
_SUFIJOS = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])?(?:\s|$|(?<=[.\-–—]))"

# Las anotaciones al margen fechan con "POE DD-MM-AAAA[, DD-MM-AAAA...]".
_POE_RE = re.compile(r"POE\s+(\d{2}-\d{2}-\d{4}(?:\s*,\s*\d{2}-\d{2}-\d{4})*)")
_FECHA_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


def _fechas(texto: str) -> list[date]:
    out: set[date] = set()
    for clausula in _POE_RE.findall(texto):
        for d, mo, y in _FECHA_RE.findall(clausula):
            try:
                out.add(date(int(y), int(mo), int(d)))
            except ValueError:
                continue
    return sorted(out)


_INDICE_RE = re.compile(r"^\s*[ÍI]NDICE DE CONTENIDO\s*$", re.MULTILINE)
_RENGLON_INDICE_RE = re.compile(r"\.{4,}\s*\d+\s*$", re.MULTILINE)


def _preprocess(texto: str) -> str:
    """Quita el índice de contenido de las primeras páginas: sus renglones
    ("Artículo 1º ......... 12") parecen encabezados de artículo y el parser los
    tomaba por el articulado. Va de "ÍNDICE DE CONTENIDO" al último renglón con
    puntos guía."""
    ini = _INDICE_RE.search(texto)
    if not ini:
        return texto
    fin = None
    for fin in _RENGLON_INDICE_RE.finditer(texto, ini.end()):
        pass
    return texto[:ini.start()] + texto[fin.end():] if fin else texto


def _version(texto: str) -> Optional[date]:
    """Portada: 'Ultima reforma publicada POE 22-06-2026'."""
    m = re.search(r"[ÚU]ltima\s+reforma\s+publicada\s+POE\s+(\d{2})-(\d{2})-(\d{4})",
                  texto, re.IGNORECASE)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


PERFIL = replace(
    perfil_estatal(
        ambito="quintana-roo",
        clave="roo",
        nombre="Constitución Política del Estado Libre y Soberano de Quintana Roo",
        fuente="Periódico Oficial del Estado de Quintana Roo — Congreso del Estado de Quintana Roo",
        url_fuente=_INDICE,
        texto_original="1975-01-12",
        label_ordinal="plano",
        # Encabezado (cambia con la legislatura) y pie "Página N de TOTAL".
        page_footer_re=re.compile(
            r"(?:P[áa]gina \d+ de \d+|[XVLI]+ Legislatura del Estado Libre y Soberano de Quintana Roo\.?)$"),
        fechas_de=_fechas,
        version_de=_version,
        preprocess=_preprocess,
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
    leak_re=re.compile(r"P[áa]gina \d+ de \d+"),
)

# La página de la ley enlaza todas las versiones históricas; el nombre lleva la
# fecha (L176-XVIII-AAAAMMDD-...) y gana la más reciente, no la última del HTML.
# Solo cuentan los textos íntegros ("...-Constitución.pdf"; los decretos sueltos
# no lo llevan) y fechas AAAAMMDD: las de 2018 vienen en DDMMAAAA.
RESOLVER = {
    "tipo": "indice",
    "index_url": _INDICE,
    "patron": re.compile(
        r'href="(https://documentos\.congresoqroo\.gob\.mx/leyes/L176-[IVXL]+-(20\d{2}[01]\d[0-3]\d)-'
        r'[^"]*Constituci[^"]*\.pdf)"'),
    "encoding": "utf-8",
    "orden": "yyyymmdd",
}

LISTO = True

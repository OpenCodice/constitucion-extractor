"""Constitución Política del Estado Libre y Soberano de Morelos."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from ..perfil import perfil_estatal

# Versión "sin notas de reforma": la otra repite tras cada artículo el texto anterior.
URL = "https://marcojuridico.morelos.gob.mx/documentos/3/notas/download"
_SUFIJO = r"(?i:bis|ter|qu[aá]ter)|[A-F](?=\.)"

# El asterisco de "reformado" también marca encabezados ("CAPITULO *I",
# "*TITULO TERCERO", "CAPÍTULO * IV") y denominaciones: sin quitarlo, el motor no
# los reconoce y se pegan al artículo anterior.
_ENCABEZADO_AST_RE = re.compile(
    r"^\*?\s*(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s*\*\s*|^\*\s*(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+",
    re.MULTILINE | re.IGNORECASE)
_DENOMINACION_AST_RE = re.compile(r"^\*(?=[^a-z\n]+$)", re.MULTILINE)


def _preprocess(texto: str) -> str:
    texto = _ENCABEZADO_AST_RE.sub(lambda m: (m.group(1) or m.group(2)) + " ", texto)
    return _DENOMINACION_AST_RE.sub("", texto)


def _version(texto: str) -> date | None:
    """Encabezado de cada página: "Última Reforma: 27-01-2026"."""
    m = re.search(r"[ÚU]ltima Reforma:\s*(\d{2})-(\d{2})-(\d{4})", texto)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


PERFIL = replace(
    perfil_estatal(
        ambito="morelos",
        clave="mor",
        nombre="Constitución Política del Estado Libre y Soberano de Morelos",
        fuente="Periódico Oficial «Tierra y Libertad» — Consejería Jurídica del Poder Ejecutivo del Estado de Morelos",
        url_fuente=URL,
        texto_original="1930-11-16",
        label_ordinal="plano",
        # Encabezado de 4 renglones y ficha de 6 al pie, en cada página.
        header_prefixes=(
            "Constitución Política del Estado Libre y Soberano de Morelos, que reforma",
            "Consejería Jurídica del Poder Ejecutivo del Estado de Morelos",
            "Dirección General de Normatividad.", "Subdirección de Jurismática.",
            "Aprobación 1930/11/20", "Promulgación 1930/11/20", "Publicación 1930/11/20",
            "Vigencia 1930/11/20", "Expidió Congreso Constituyente", "Periódico Oficial 3 7 7"),
        page_footer_re=re.compile(r"\d{1,3} de \d{2,3}$"),
        preprocess=_preprocess,
        version_de=_version,
    ),
    # El asterisco antes del número marca un artículo reformado: "ARTICULO *1.-";
    # sin punto ni guion solo tras un sufijo ("ARTICULO *133-bis Tienen").
    article_re=re.compile(
        r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+\*?\s*(\d+)\s*[oº°]?[\s-]*(" + _SUFIJO + r")?\s*(?:\.\s*-?|-|(?<=(?i:bis|ter))\s)"),
    article_strip_re=re.compile(
        r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+\*?\s*\d+\s*[oº°]?[\s-]*(?:" + _SUFIJO + r")?\s*(?:\.\s*-?|-|(?<=(?i:bis|ter))\s)\s*"),
)

RESOLVER = {"tipo": "directo", "url": URL}

LISTO = True

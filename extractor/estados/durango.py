"""Durango: Constitución Política del Estado Libre y Soberano de Durango."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..parse import ENCABEZADO_RE
from ..perfil import _MESES, perfil_estatal

# Notas de reforma en renglón propio tras el bloque que anotan: "PÁRRAFO
# REFORMADO POR DEC. 294 P.O. 99 BIS DE FECHA 11 DE DICIEMBRE DE 2025."
_NOTA_RE = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ]+(?:\s+[IVXLC]+)?\s+)?(?:REFORMAD|ADICIONAD|DEROGAD|RECORRID)[OA]S?\b"
    r".*(?:DEC\.|P\.\s?O\.).*\d{4}\.?$")
_ARTICULO_RE = re.compile(r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d")


def separar_notas(texto: str) -> str:
    """Aísla cada nota con renglones en blanco: muchas no cierran en punto y el
    normalizador las pegaría al párrafo siguiente. Dentro de un bloque de
    encabezado no se agregan: el parser solo reconoce bloques cortos."""
    out: list[str] = []
    en_encabezado = False
    for linea in texto.split("\n"):
        s = linea.strip()
        if ENCABEZADO_RE.match(s):
            en_encabezado = True
        elif _ARTICULO_RE.match(s):
            en_encabezado = False
        if _NOTA_RE.match(s) and not en_encabezado:
            out += ["", linea, ""]
        else:
            out.append(linea)
    return "\n".join(out)


# La portada (y cada página) dice "FECHA DE ÚLTIMA REFORMA:" y en el renglón
# siguiente "DEC. 426 P.O. 44 BIS DEL 31 DE MAYO DE 2026."
_VERSION_RE = re.compile(
    r"[ÚU]LTIMA\s+REFORMA:\s*\n\s*DEC\.[^\n]*?(\d{1,2})\s+DE\s+(" + "|".join(_MESES) +
    r")\s+DE\s+(\d{4})", re.IGNORECASE)


def version_portada(texto: str) -> Optional[date]:
    m = _VERSION_RE.search(texto)
    if not m:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


_BASE = perfil_estatal(
    ambito="durango",
    clave="dur",
    nombre="Constitución Política del Estado Libre y Soberano de Durango",
    fuente="Periódico Oficial del Gobierno del Estado de Durango — H. Congreso del Estado de Durango",
    url_fuente=("https://congresodurango.gob.mx/Archivos/legislacion/"
                "CONSTITUCION%20POLITICA%20DEL%20ESTADO%20(NUEVA).pdf"),
    texto_original="2013-08-29",
    header_prefixes=(
        "CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE DURANGO",
        "FECHA DE ÚLTIMA REFORMA:"),
    label_ordinal="plano",
    # Pie: número de página suelto. El tercer renglón del encabezado ("DEC. 426
    # P.O. 44 BIS DEL 31 DE MAYO DE 2026.") cambia con cada reforma; en el cuerpo
    # las notas nunca empiezan por "DEC.".
    page_footer_re=re.compile(r"(?:\d{1,3}|DEC\.\s+\d+\b.*\d{4}\.)$"),
    version_de=version_portada,
    preprocess=separar_notas,
)

# Encabezados "ARTÍCULO 116 bis. - La", "ARTÍCULO 163 QUÁTER.-", "ARTÍCULO 28.- - Toda".
# Se exige el punto o guion de cierre: un renglón que empieza con una cita
# ("ARTÍCULO 12 de esta...") no abre artículo.
_ART = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*((?i:Bis|Ter|Qu[áa]ter|Quintus))?\s*"
PERFIL = replace(
    _BASE,
    article_re=re.compile(_ART + r"(?:\.\s*-?|-)(?:\s|$)"),
    article_strip_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+\s*(?i:Bis|Ter|Qu[áa]ter|Quintus)?\s*"
        r"(?:\.\s*-?|-)(?:\s*-)*\s*"),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

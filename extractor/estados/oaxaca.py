"""Constitución Política del Estado Libre y Soberano de Oaxaca."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import _MESES, perfil_estatal

_INDICE = "https://www.congresooaxaca.gob.mx/legislaciones/legislacion_estatal.html"

# La puntuación tras el número es obligatoria: las notas al pie empiezan igual
# ("Artículo 114 bis adicionado mediante decreto...") y abrirían un artículo
# duplicado. Sufijos hasta Quinquies ("Artículo 114 QUÁTER.-").
_SUFIJOS = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])"

_FECHA_RE = re.compile(
    r"(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")\s+(?:de|del)\s+(?:año\s+)?(\d{4})",
    re.IGNORECASE)


def _fechas(texto: str) -> list[date]:
    """Las notas fechan "el 30 de junio del 2015" (con "del")."""
    out: set[date] = set()
    for d, mo, y in _FECHA_RE.findall(texto):
        try:
            out.add(date(int(y), _MESES[mo.lower()], int(d)))
        except ValueError:
            continue
    return sorted(out)


def _version(texto: str) -> Optional[date]:
    """Portada: 'Última reforma: Decreto número 1596, aprobado ... el 14 de julio del
    2026, publicado en el Periódico Oficial ... de fecha 1 de agosto del 2026.'
    La versión es la fecha de publicación, no la de aprobación."""
    m = re.search(r"[ÚU]ltima\s+reforma.*?publicad[oa]\b.*?(\d{1,2})\s+de\s+(" +
                  "|".join(_MESES) + r")\s+del?\s+(\d{4})", texto, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


PERFIL = replace(
    perfil_estatal(
        ambito="oaxaca",
        clave="oax",
        nombre="Constitución Política del Estado Libre y Soberano de Oaxaca",
        fuente="Periódico Oficial del Estado de Oaxaca — H. Congreso del Estado Libre y "
               "Soberano de Oaxaca",
        url_fuente=_INDICE,
        texto_original="1922-04-04",
        label_ordinal="plano",
        header_prefixes=("H. Congreso del Estado Libre y Soberano de Oaxaca",
                         "DIRECCIÓN DE INFORMÁTICA Y GACETA PARLAMENTARIA"),
        # Número de página suelto y la línea de la legislatura, que cambia cada trienio.
        page_footer_re=re.compile(r"(?:\d{1,3}|[LXVI]+ Legislatura Constitucional)$"),
        fechas_de=_fechas,
        version_de=_version,
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
)

# El nombre del PDF lleva el decreto de la última reforma y la carpeta (docs66)
# cambia con la legislatura; el índice lo enlaza con ruta relativa.
RESOLVER = {
    "tipo": "indice",
    "index_url": _INDICE,
    "patron": re.compile(
        r'href="([^"]*Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Oaxaca[^"]*\.pdf)"'),
    "encoding": "utf-8",
    "orden": "unico",
}

LISTO = True

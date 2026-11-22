"""Constitución Política del Estado Libre y Soberano de Puebla."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..perfil import perfil_estatal


def _filtro_char(c: dict) -> bool:
    """Descarta lo menor a 9 pt: las llamadas de nota en superíndice, que pegadas
    al número ("Artículo 142386") cambiarían la numeración, y el encabezado."""
    return c.get("size", 12) >= 9


_INICIO_RE = re.compile(r"^CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE\nPUEBLA\n", re.M)
_FECHA = r"\d{1,2}/ ?[a-z]{3}/ ?/?\d{4}"
# Pie de cada página: su número y las notas al pie ("Párrafo reformado el
# 15/mar/2025.", ya sin su número), en uno o más renglones. Toda nota lleva fechas
# "DD/mmm/AAAA", que el texto de los artículos nunca usa.
_PIE_RE = re.compile(
    r"(?:\d{1,3}"
    r"|(?:Art[íi]culo|P[áa]rrafo|Fracci[óo]n|Inciso|Apartado|Cap[íi]tulo|T[íi]tulo|"
    r"Secci[óo]n|Denominaci[óo]n|Base|Numeral)\b.*(?:reformad|adicionad|derogad)[oa]s? el\b.*"
    r"|.*" + _FECHA + r".*)$")


def _preprocess(texto: str) -> str:
    # Antes del articulado van la tabla de reformas y el índice, que citan artículos.
    m = _INICIO_RE.search(texto)
    if m:
        texto = texto[m.end():]
    return texto


_MESES = {m: i + 1 for i, m in enumerate(
    ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"])}
_PUBLICACION_RE = re.compile(r"^(\d{1,2})/ ?([a-z]{3})/ ?/?(\d{4})\b", re.MULTILINE)


def _version(texto: str) -> Optional[date]:
    """La portada no trae fecha: la versión es la publicación más reciente de la
    tabla «REFORMAS» («06/mar/2026 ÚNICO. Se reforma…»), que acaba en el índice."""
    inicio = re.search(r"^REFORMAS$", texto, re.MULTILINE)
    fin = re.search(r"^CONTENIDO$", texto, re.MULTILINE)
    if not inicio or not fin:
        return None
    fechas = [date(int(a), _MESES[m], int(d))
              for d, m, a in _PUBLICACION_RE.findall(texto[inicio.end():fin.start()]) if m in _MESES]
    return max(fechas, default=None)


PERFIL = perfil_estatal(
    ambito="puebla",
    clave="pue",
    nombre="Constitución Política del Estado Libre y Soberano de Puebla",
    fuente="Periódico Oficial del Estado de Puebla — Orden Jurídico Poblano, Secretaría de Gobernación",
    url_fuente=("https://ojp.puebla.gob.mx/media/k2/attachments/"
                "Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Puebla_TEV_06032026.pdf"),
    texto_original="1917-10-04",
    label_ordinal="plano",
    filtro_char=_filtro_char,
    page_footer_re=_PIE_RE,
    preprocess=_preprocess,
    version_de=_version,
    version_paginas=20,
)

RESOLVER = {
    "tipo": "indice",
    # La categoría "Constitución Local" enlaza el vigente (fecha DDMMAAAA en el
    # nombre) y también las constituciones históricas de 1825 y 1861.
    "index_url": ("https://ojp.puebla.gob.mx/legislacion-del-estado/itemlist/category/"
                  "9-constitucion-local"),
    "encoding": "utf-8",
    "patron": re.compile(
        r'href="(/media/k2/attachments/Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Puebla_'
        r'(?!de_1[89]\d\d)[^"]*\.pdf)"'),
    "orden": "unico",
}

LISTO = True

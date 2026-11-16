"""Constitución Política del Estado Libre y Soberano de San Luis Potosí."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

_INDICE = "http://lx.congresosanluis.gob.mx/legislacion/constitucion"

# Sufijos latinos más allá de Ter y encabezados pegados al texto
# ("ARTÍCULO 45.-El..."): el regex genérico los fundía con el artículo anterior.
_SUFIJOS = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])?(?:\s|$|(?<=[.\-–—]))"

_ARTICULO_RE = re.compile(r"^\s*(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+")
# Encabezado estructural en mayúsculas en su propia línea: "TÍTULO DECIMOSEGUNDO",
# "CAPÍTULO ÚNICO", "SECCIÓN III".
_ESTRUCTURA_RE = re.compile(
    r"^\s*(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|APARTADO)\s+[A-ZÁÉÍÓÚ0-9]+(?:\s+[A-ZÁÉÍÓÚ]+)?\.?\s*$")
# "(REFORMADO, ...)", y también "(ARTÍCULO REFORMADO ...)", "(TÍTULO Y CAPÍTULO
# ADICIONADOS ...)" o la errata "(REFORADO ...)".
_NOTA_RE = re.compile(
    r"^\s*\((?:[A-ZÁÉÍÓÚÑ]+\s+){0,3}?(?:REFORMAD|REFORAD|ADICIONAD|DEROGAD|RECORRID|REPUBLICAD|FE DE ERRATAS)")
# Un bloque de encabezado (título, capítulo, denominaciones y sus notas) es corto.
_MAX_BLOQUE = 15


def _fin_nota(lines: list[str], i: int) -> int:
    """Índice siguiente a la nota que empieza en `i` (envuelta en hasta 3 renglones)."""
    j = i + 1
    while (j < len(lines) and j - i < 3
           and " ".join(lines[i:j]).count("(") > " ".join(lines[i:j]).count(")")
           and lines[j].strip() and not re.search(r"[a-záéíóúñ]", lines[j])
           and not _ARTICULO_RE.match(lines[j])):
        j += 1
    return j


def _preprocess(texto: str) -> str:
    """Prepara el texto para el parser sin tocar el de los artículos:

    - NFC: parte del PDF trae los acentos descompuestos ("ARTÍCULO 90"), y
      así ni el artículo ni el encabezado se reconocían.
    - Quita las notas de reforma que preceden a un artículo o a un encabezado
      (en esta edición la nota va ANTES de lo que anota, así que el parser la
      pegaría al artículo anterior). Las seguidas de texto anotan un párrafo del
      mismo artículo y se quedan.
    - De cada bloque de encabezado deja solo las líneas "TÍTULO ..."/"CAPÍTULO
      ..." y quita denominaciones y notas intercaladas: con ordinales como
      "DECIMOSEGUNDO" el parser no reconoce el bloque y lo pegaba al artículo
      anterior."""
    lines = unicodedata.normalize("NFC", texto).splitlines()
    borrar: set[int] = set()
    i = 0
    while i < len(lines):
        if _NOTA_RE.match(lines[i]):
            j = i
            while j < len(lines) and (_NOTA_RE.match(lines[j]) or not lines[j].strip()):
                j = _fin_nota(lines, j) if lines[j].strip() else j + 1
            if j < len(lines) and (_ARTICULO_RE.match(lines[j]) or _ESTRUCTURA_RE.match(lines[j])):
                borrar.update(range(i, j))
            i = max(j, i + 1)
            continue
        if _ESTRUCTURA_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and j - i <= _MAX_BLOQUE and not _ARTICULO_RE.match(lines[j]):
                j += 1
            if j < len(lines) and _ARTICULO_RE.match(lines[j]):
                borrar.update(k for k in range(i + 1, j) if not _ESTRUCTURA_RE.match(lines[k]))
                i = j
                continue
        i += 1
    return "\n".join(ln for k, ln in enumerate(lines) if k not in borrar)


PERFIL = replace(
    perfil_estatal(
        ambito="san-luis-potosi",
        clave="slp",
        nombre="Constitución Política del Estado Libre y Soberano de San Luis Potosí",
        fuente="Periódico Oficial del Estado de San Luis Potosí — Congreso del Estado de "
               "San Luis Potosí (Instituto de Investigación y Evaluación Legislativa)",
        url_fuente=_INDICE,
        texto_original="1917-10-08",
        label_ordinal="plano",
        header_prefixes=("CONSTITUCIÓN POLÍTICA DEL ESTADO DE SAN LUIS POTOSI",
                         "CONGRESO DEL ESTADO DE SAN LUIS POTOSI",
                         "INSTITUTO DE INVESTIGACIÓN Y EVALUACIÓN LEGISLATIVA"),
        # Cuarta línea del encabezado; su fecha cambia con cada edición.
        page_footer_re=re.compile(r"Última reforma: \d{1,2} de \w+ de \d{4}$"),
        version_de=version_ultima_reforma,   # portada: "Fecha Ultima Reforma: 28 DE SEPTIEMBRE DE 2026"
        preprocess=_preprocess,
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    # Admite los ordinales compuestos ("TÍTULO DECIMOSEGUNDO") que el genérico no reconoce.
    titulo_re=re.compile(
        r"^T[ÍI]TULO\s+(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO|"
        r"D[ÉE]CIMO\w*(?:\s+[A-ZÁÉÍÓÚ]+)?)\s*$"),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
)

# El nombre del PDF lleva la fecha de corte ("(al 28 de septiembre de 2026)").
RESOLVER = {
    "tipo": "indice",
    "index_url": _INDICE,
    "patron": re.compile(
        r'href="(https?://(?:lx\.)?congresosanluis\.gob\.mx/sites/default/files/unpload/pdf/'
        r'Constituci[^"]*Potos[^"]*\.pdf)"'),
    "encoding": "utf-8",
    "orden": "unico",
}

LISTO = True

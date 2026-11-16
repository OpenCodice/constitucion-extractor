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
_NOTA = (r"\((?:[A-ZÁÉÍÓÚÑ]+\s+){0,3}?"
         r"(?:REFORMAD|REFORAD|ADICIONAD|DEROGAD|RECORRID|REPUBLICAD|FE DE ERRATAS)")
_NOTA_RE = re.compile(r"^\s*" + _NOTA)
# La nota de un párrafo o fracción derogados ocupa el lugar del texto que ya no
# está: al final de su artículo, aunque le siga el encabezado del siguiente
# ("(DEROGADO ULTIMO PARRAFO, …)" + "ARTÍCULO 19.-"). No es nota previa.
_NOTAS_PREVIAS_RE = re.compile(r"^\s*(?!\((?=[^)]*DEROGAD)[^)]*(?:P[ÁA]RRAFO|FRACC|INCISO))" + _NOTA)
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
    - En esta edición la nota de reforma va ANTES de lo que anota. Las que
      preceden a un artículo (también las que quedan entre la denominación de
      un encabezado y el artículo) quedan cada una en un renglón para que
      `notas_previas` las lleve al artículo que anotan. Las que preceden a un
      encabezado anotan la estructura y se quitan: el parser las pegaría al
      artículo anterior, y no van al siguiente (`notas_previas_encabezado`)
      porque se intercalan con renglones sueltos de la denominación que
      `cobertura` no tolera entre notas. Las seguidas de texto anotan un párrafo
      del mismo artículo y no se tocan.
    - De cada bloque de encabezado deja solo las líneas "TÍTULO ..."/"CAPÍTULO
      ..." (y las notas del artículo que lo cierra) y quita denominaciones y las
      demás notas: con ordinales como "DECIMOSEGUNDO" el parser no reconoce el
      bloque y lo pegaba al artículo anterior."""
    lines = unicodedata.normalize("NFC", texto).splitlines()
    borrar: set[int] = set()
    unidas: dict[int, str] = {}

    def notas_en(desde: int, hasta: int) -> list[tuple[int, int]]:
        """Notas (inicio, fin) entre `desde` y `hasta`."""
        k, notas = desde, []
        while k < hasta:
            if _NOTA_RE.match(lines[k]):
                fin = min(_fin_nota(lines, k), hasta)
                notas.append((k, fin))
                k = fin
            else:
                k += 1
        return notas

    def unir(notas: list[tuple[int, int]]) -> None:
        for a, b in notas:
            if lines[a].strip():
                # En un solo renglón y párrafo propio: el normalizador no la pega a
                # la nota o al texto vecinos.
                unidas[a] = " ".join(ln.strip() for ln in lines[a:b]) + "\n"
                borrar.update(range(a + 1, b))

    i = 0
    while i < len(lines):
        if _NOTA_RE.match(lines[i]):
            j = i
            while j < len(lines) and (_NOTA_RE.match(lines[j]) or not lines[j].strip()):
                j = _fin_nota(lines, j) if lines[j].strip() else j + 1
            if j < len(lines) and _ARTICULO_RE.match(lines[j]):
                unir(notas_en(i, j))
            elif j < len(lines) and _ESTRUCTURA_RE.match(lines[j]):
                borrar.update(range(i, j))
            i = max(j, i + 1)
            continue
        if _ESTRUCTURA_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and j - i <= _MAX_BLOQUE and not _ARTICULO_RE.match(lines[j]):
                j += 1
            if j < len(lines) and _ARTICULO_RE.match(lines[j]):
                notas = notas_en(i + 1, j)
                en_nota = {k for a, b in notas for k in range(a, b)}
                # Las notas que siguen al último renglón de la estructura son del artículo.
                ultimo = max((k for k in range(i, j) if lines[k].strip() and k not in en_nota),
                             default=i)
                unir([(a, b) for a, b in notas if a > ultimo])
                borrar.update(k for k in range(i + 1, ultimo + 1)
                              if not _ESTRUCTURA_RE.match(lines[k]))
                i = j
                continue
        i += 1
    return "\n".join(unidas.get(k, ln) for k, ln in enumerate(lines) if k not in borrar)


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
        notas_previas=_NOTAS_PREVIAS_RE,
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

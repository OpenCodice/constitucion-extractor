"""Constitución Política del Estado Libre y Soberano de Guerrero."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import _MESES, perfil_estatal

_URL = "https://congresogro.gob.mx/legislacion/CONSTITUCION-GUERRERO-15-06-2022.pdf"

# Sufijos latinos hasta Octies ("Artículo 160 Octies") y encabezados pegados al
# texto ("Artículo 45.-El Congreso..."): el regex genérico solo admite Bis/Ter
# seguidos de espacio y los fundía con el artículo anterior.
_SUFIJOS = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])?(?:\s|$|(?<=[.\-–—]))"

_ARTICULO_RE = re.compile(r"^\s*(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+")
_ESTRUCTURA_RE = re.compile(
    r"^\s*(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|APARTADO|Derogado\s+CAP[ÍI]TULO)\b")
_NOTA_RE = re.compile(r"^\s*\((?:REFORMAD|ADICIONAD|DEROGAD|RECORRID)")
_DECRETO_RE = re.compile(r"^\s*(?:\(?DECRETO\s+(?:No\.\s*)?\d+\)?|D-\s*\d+)\s*$")
_APARTADO_RE = re.compile(r"^\s*APARTADO\s+\S+\s*$")
_DEROGADO_CAP_RE = re.compile(r"^\s*Derogado\s+CAP[ÍI]TULO\b")


def _fin_nota(lines: list[str], i: int) -> int:
    """Índice siguiente a la nota que empieza en `i` (envuelta en hasta 3
    renglones, más la línea suelta "DECRETO 828" que a veces la acompaña)."""
    j = i + 1
    while (j < len(lines) and j - i < 3
           and " ".join(lines[i:j]).count("(") > " ".join(lines[i:j]).count(")")
           and lines[j].strip() and not re.search(r"[a-záéíóúñ]", lines[j])
           and not _ARTICULO_RE.match(lines[j])):
        j += 1
    while j < len(lines) and _DECRETO_RE.match(lines[j]):
        j += 1
    return j


def _preprocess(texto: str) -> str:
    """Quita lo que el PDF intercala ENTRE artículos y el parser pegaría al
    artículo anterior: las notas de reforma, que en esta edición preceden al
    elemento que anotan (artículo, título, capítulo, sección), y los encabezados
    "APARTADO ..." y "Derogado CAPÍTULO ..." que el parser no reconoce como
    estructura. Las notas seguidas de texto (párrafo, fracción) se quedan: anotan
    texto del mismo artículo."""
    lines = texto.splitlines()
    borrar: set[int] = set()
    i = 0
    while i < len(lines):
        if _NOTA_RE.match(lines[i]):
            # Junta notas consecutivas y mira qué viene después de todas ellas.
            j = i
            while j < len(lines) and (_NOTA_RE.match(lines[j]) or not lines[j].strip()):
                j = _fin_nota(lines, j) if lines[j].strip() else j + 1
            if j < len(lines) and (_ARTICULO_RE.match(lines[j]) or _ESTRUCTURA_RE.match(lines[j])):
                borrar.update(range(i, j))
            i = max(j, i + 1)
            continue
        if _APARTADO_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not re.search(r"[a-záéíóúñ]", lines[j]) \
                    and not _NOTA_RE.match(lines[j]) and not _ARTICULO_RE.match(lines[j]):
                j += 1
            borrar.update(range(i, j))
            i = j
            continue
        if _DEROGADO_CAP_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and j - i <= 6 and not _ARTICULO_RE.match(lines[j]):
                j += 1
            if j < len(lines) and _ARTICULO_RE.match(lines[j]):
                borrar.update(range(i, j))
            i = j
            continue
        i += 1
    return "\n".join(ln for k, ln in enumerate(lines) if k not in borrar)


def _version(texto: str) -> Optional[date]:
    """Portada: 'ÚLTIMAS MODIFICACIONES PUBLICADAS ... DE FECHA MARTES 21 DE ABRIL DE 2026'."""
    m = re.search(r"[ÚU]LTIMAS?\s+MODIFICACIONES.*?(\d{1,2})\s+DE\s+(" + "|".join(_MESES) +
                  r")\s+DE\s+(\d{4})", texto, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


PERFIL = replace(
    perfil_estatal(
        ambito="guerrero",
        clave="gro",
        nombre="Constitución Política del Estado Libre y Soberano de Guerrero",
        fuente="Periódico Oficial del Gobierno del Estado de Guerrero — H. Congreso del Estado de Guerrero",
        url_fuente=_URL,
        texto_original="1917-11-03",
        label_ordinal="plano",
        # Pie de cada página: "H. Congreso del Estado de Guerrero", "S.S.P./D.P.L." y el número.
        header_prefixes=("H. Congreso del Estado de Guerrero", "S.S.P./D.P.L."),
        page_footer_re=re.compile(r"\d{1,3}$"),
        # El articulado cierra con "TRANSITORIOS." (con punto), que el genérico no reconoce.
        transitorios_re=re.compile(r"^[ \t]*TRANSITORIOS\.?[ \t]*$", re.MULTILINE),
        version_de=_version,
        preprocess=_preprocess,
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
)

RESOLVER = {"tipo": "directo", "url": _URL}

LISTO = True

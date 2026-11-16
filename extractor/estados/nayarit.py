"""Constitución Política del Estado Libre y Soberano de Nayarit."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import _MESES, perfil_estatal

_URL = ("https://congresonayarit.gob.mx/wp-content/uploads/QUE_HACEMOS/LEGISLACION_ESTATAL/"
        "constitucion/Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Nayarit.pdf")

# Sufijos latinos más allá de Ter y encabezados pegados al texto
# ("ARTÍCULO 45.-El..."): el regex genérico los fundía con el artículo anterior.
_SUFIJOS = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])?(?:\s|$|(?<=[.\-–—]))"

_ARTICULO_RE = re.compile(r"^\s*(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+")
_ESTRUCTURA_RE = re.compile(
    r"^\s*(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|APARTADO|Derogado\s+CAP[ÍI]TULO)\b")
_NOTA_RE = re.compile(r"^\s*\((?:REFORMAD|ADICIONAD|DEROGAD|RECORRID|REPUBLICAD|FE DE ERRATAS)")
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
    """Portada: 'ÚLTIMA ENMIENDA PUBLICADA EN EL PERIÓDICO OFICIAL: 6 DE NOVIEMBRE DE 2026'."""
    m = re.search(r"[ÚU]LTIMA\s+(?:ENMIENDA|REFORMA).*?(\d{1,2})\s+DE\s+(" + "|".join(_MESES) +
                  r")\s+DE\s+(\d{4})", texto, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


PERFIL = replace(
    perfil_estatal(
        ambito="nayarit",
        clave="nay",
        nombre="Constitución Política del Estado Libre y Soberano de Nayarit",
        fuente="Periódico Oficial del Estado de Nayarit — Congreso del Estado de Nayarit",
        url_fuente=_URL,
        texto_original="1918-02-17",
        label_ordinal="plano",
        # Encabezado de cada página; el título sale con las letras duplicadas
        # ("CCOONNSSTTIITTUUCCIIOONN ...") por texto en negrita superpuesto.
        header_prefixes=("CCOONNSSTTIITTUUCCIIOONN", "Poder Legislativo del Estado de Nayarit"),
        # Línea completa: "Secretaría General de Gobierno del Estado." es texto del art. 73.
        page_footer_re=re.compile(r"Secretaría General$"),
        # El PDF trae el título espaciado: "T R A N S I T O R I O S".
        transitorios_re=re.compile(r"^[ \t]*T ?R ?A ?N ?S ?I ?T ?O ?R ?I ?O ?S[ \t]*$", re.MULTILINE),
        version_de=_version,
        preprocess=_preprocess,
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
)

RESOLVER = {"tipo": "directo", "url": _URL}

LISTO = True

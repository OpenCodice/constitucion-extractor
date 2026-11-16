"""Constitución Política del Estado Libre y Soberano de Tlaxcala."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

URL = "https://congresodetlaxcala.gob.mx/archivo/leyes2020/pdf/5_constitucion_pol.pdf"
_SUFIJO = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies)"

# Nota de reforma en renglón propio: "(REFORMADO, P.O. 4 DE FEBRERO DE 1982)".
_NOTA_RE = re.compile(r"^\((?:REFORMAD|ADICIONAD|DEROGAD|REUBICAD)[^)]*\)\.?$")
_ARTICULO_RE = re.compile(r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d")
_ENCABEZADO_RE = re.compile(
    r"^(?:(?:ART[ÍI]CULO|Art[íi]culo)\s+\d+|T[ÍI]TULO\s|CAP[ÍI]TULO\s|SECCI[ÓO]N\s)")

_SOLO_ENCABEZADO_RE = re.compile(
    r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+\d+\s*[oº°]?\s*(?:[- ]\s*" + _SUFIJO + r")?[.\s-]*$")


# "CAPITULO III (DEROGADO, P.O. …)": con la nota en su renglón el motor reconoce
# el encabezado y no lo pega al artículo anterior.
_ENCABEZADO_CON_NOTA_RE = re.compile(
    r"^((?:CAP[ÍI]TULO|T[ÍI]TULO|SECCI[ÓO]N)\s+[IVXLC]+)\s+(\((?:REFORMAD|ADICIONAD|DEROGAD)[^)]*\))$",
    re.MULTILINE)


def _preprocess(texto: str) -> str:
    """Quita las notas que preceden a un encabezado de Título, Capítulo o Sección:
    el PDF las pone ANTES de lo que anotan y quedarían al final del artículo
    anterior. Las que preceden a un artículo se quedan y el motor se las da a ese
    artículo (`notas_previas`); las de un párrafo, como párrafo propio para que
    no se peguen al texto."""
    lineas = _ENCABEZADO_CON_NOTA_RE.sub(r"\1\n\2", texto).split("\n")
    fuera: set[int] = set()
    previas: set[int] = set()
    i = 0
    while i < len(lineas):
        if not _NOTA_RE.match(lineas[i].strip()):
            i += 1
            continue
        j = i
        while j < len(lineas) and _NOTA_RE.match(lineas[j].strip()):
            j += 1
        # "ARTICULO 115.-" seguido de su nota de derogación: la nota es su cuerpo.
        cuerpo = i > 0 and _SOLO_ENCABEZADO_RE.match(lineas[i - 1].strip())
        if j < len(lineas) and _ARTICULO_RE.match(lineas[j].strip()):
            previas.update(range(i + 1 if cuerpo else i, j))
        elif j < len(lineas) and _ENCABEZADO_RE.match(lineas[j].strip()):
            fuera.update(range(i + 1 if cuerpo else i, j))
        i = j
    out = []
    for k, l in enumerate(lineas):
        if k in fuera:
            continue
        # Las que anteceden a un artículo van sin renglones en blanco: el motor
        # ya las separa, y en blanco alargarían el bloque de encabezado
        # (Capítulo + denominación + notas) más de lo que el parser reconoce.
        aparte = _NOTA_RE.match(l.strip()) and k not in previas
        out.append(f"\n{l}\n" if aparte else l)
    return "\n".join(out)


PERFIL = replace(
    perfil_estatal(
        ambito="tlaxcala",
        clave="tla",
        nombre="Constitución Política del Estado Libre y Soberano de Tlaxcala",
        fuente="Periódico Oficial del Gobierno del Estado de Tlaxcala — Congreso del Estado de Tlaxcala",
        url_fuente=URL,
        texto_original="1918-10-02",
        label_ordinal="plano",
        version_de=version_ultima_reforma,
        # Encabezado de cada página; pdfplumber deja el folio en su propio renglón.
        page_footer_re=re.compile(
            r"(?:CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE TLAXCALA\s+Pág\.(?:\s*\d+)?"
            r"|\d{1,3})$"),
        preprocess=_preprocess,
        notas_previas=_NOTA_RE,
    ),
    article_re=re.compile(
        r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+(\d+)\s*[oº°]?\s*(?:[- ]\s*(" + _SUFIJO + r"))?(?:\.\s*-?|\s*-)"),
    article_strip_re=re.compile(
        r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+\d+\s*[oº°]?\s*(?:[- ]\s*" + _SUFIJO + r")?(?:\.\s*-?|\s*-)\.?\s*"),
)

RESOLVER = {"tipo": "directo", "url": URL}

LISTO = True

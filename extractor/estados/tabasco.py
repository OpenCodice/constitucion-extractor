"""Constitución Política del Estado Libre y Soberano de Tabasco."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import perfil_estatal, version_ultima_reforma

_SUFIJO = r"(?i:bis|ter|qu[aá]ter)"

# Marginalia de reforma en renglón propio: "REFORMADO P.O. 8469 SPTO. F 4-NOV-2023",
# "(ADICIONADO 11-NOV-03)", "PÁRRAFO DEROGADO SUP. “C” P. O. 7310 ...".
_NOTA_RE = re.compile(
    r"^\(?(?:P[ÁA]RRAFO\s+)?(?:REFORMAD|ADICIONAD|DEROGAD|REUBICAD|F\.\s*DE\s*E\.)[^\n]*\d")
_ARTICULO_RE = re.compile(r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d")
_ENCABEZADO_RE = re.compile(
    r"^(?:(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+|T[ÍI]TULO\s|CAP[ÍI]TULO\s|SECCI[ÓO]N\s)")


def _preprocess(texto: str) -> str:
    """Quita las notas que preceden a un encabezado de Título, Capítulo o Sección:
    el PDF las pone ANTES de lo que anotan y quedarían al final del artículo
    anterior. Las que preceden a un artículo se quedan y el motor se las da a ese
    artículo (`notas_previas`); las de un párrafo, como párrafo propio para que
    no se peguen al texto."""
    lineas = texto.split("\n")
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
        if j < len(lineas) and _ARTICULO_RE.match(lineas[j].strip()):
            previas.update(range(i, j))
        elif j < len(lineas) and _ENCABEZADO_RE.match(lineas[j].strip()):
            fuera.update(range(i, j))
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


def _version(texto: str) -> Optional[date]:
    """Portada: «Última reforma mediante Decreto 283, publicado en el Periódico
    Oficial… de fecha 26 de agosto de 2026», partida en renglones."""
    return version_ultima_reforma(" ".join(texto.split()))


PERFIL = replace(
    perfil_estatal(
        ambito="tabasco",
        clave="tab",
        nombre="Constitución Política del Estado Libre y Soberano de Tabasco",
        fuente="Periódico Oficial del Estado de Tabasco — H. Congreso del Estado de Tabasco",
        url_fuente=("https://congresotabasco.gob.mx/wp-content/uploads/2026/08/"
                    "Constitucion-Politica-del-Estado-de-Tabasco1.pdf"),
        texto_original="1919-04-05",
        label_ordinal="plano",
        header_prefixes=("Constitución Política del Estado Libre y Soberano de Tabasco",),
        page_footer_re=re.compile(r"\d{1,3}$"),
        preprocess=_preprocess,
        notas_previas=_NOTA_RE,
        version_de=_version,
    ),
    article_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[ -]\s*(" + _SUFIJO + r"))?\s*\.\s*-?"),
    article_strip_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+\s*(?:[ -]\s*" + _SUFIJO + r")?\s*\.\s*-?\s*"),
)

RESOLVER = {
    "tipo": "indice",
    # La ruta lleva el año/mes de subida (/uploads/AAAA/MM/); el nombre es estable.
    # Las copias del hosting viejo viven bajo /wp/wp-content/ y no cuentan.
    "index_url": "https://congresotabasco.gob.mx/leyes/",
    "encoding": "utf-8",
    "patron": re.compile(
        r'href="(https://congresotabasco\.gob\.mx/wp-content/uploads/(\d{4}/\d{2})/'
        r'Constitucion-Politica-del-Estado-de-Tabasco1\.pdf)"'),
    "orden": "fecha",
}

LISTO = True

"""Campeche: Constitución Política del Estado de Campeche."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from dataclasses import replace

from ..perfil import perfil_estatal

_SUFIJO = r"Bis|Ter|Qu[aá]ter|Quinquies"
# Sufijos hasta "quinquies" (art. 101 quinquies), sin espacio tras el guion
# ("ARTÍCULO 101.-DEROGADO.") y numeración decimal: del 88.1 al 88.7 son
# artículos propios ("ARTÍCULO 88.1.-"), no párrafos del 88.
# El sufijo debe ser el grupo 2 (lo lee el parser); el subnúmero va como
# grupo nombrado `sub`, en una alternativa aparte.
ARTICULO_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)(?:\s*[oº°]?\s*((?i:" + _SUFIJO + r"))"
    r"|\.(?P<sub>\d{1,2})(?=\.)|\s*[oº°]?)"
    r"\.?[-–—]?(?:\s|$|(?=[A-ZÁÉÍÓÚÑ]))")
ARTICULO_STRIP_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+(?:\.\d{1,2}(?=\.))?\s*[oº°]?\s*(?i:" + _SUFIJO + r")?"
    r"\.?[-–—]?\s*")

_ENCABEZADO_RE = re.compile(
    r"^(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+(?:[IVXLC]+|[ÚU]NICO)"
    r"(?:\s+(?:BIS|TER|QU[ÁA]TER))?$")
_DENOMINACION_RE = re.compile(r"^[^a-záéíóúñ]+$")
_MAX_BLOQUE = 12

_MES3 = {m: i + 1 for i, m in enumerate(
    ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"])}
_VERSION_RE = re.compile(r"[ÚU]LTIMA REFORMA:.*?P\.\s?O\.\s+(\d{1,2})/([A-Z]{3})/(\d{4})")


def version_encabezado(texto: str) -> Optional[date]:
    """Encabezado: "ÚLTIMA REFORMA: DECRETO 297, P.O. 12/OCT/2026". La portada
    interior da otra fecha ("Última reforma: 1 de octubre de 2026"); se toma la
    del Periódico Oficial, que es la publicación del decreto."""
    m = _VERSION_RE.search(texto)
    if not m or m.group(2) not in _MES3:
        return None
    return date(int(m.group(3)), _MES3[m.group(2)], int(m.group(1)))


_NOTA_RE = re.compile(r"^Nota:")
# "…publicado en el P.O. No." sigue en el renglón de abajo aunque cierre en punto.
_NOTA_ABIERTA_RE = re.compile(r"(?:\bNo|\bN[úu]m|P\.\s?O|P)\.$|[^.]$")


def _compactar_encabezados(lineas: list[str]) -> list[str]:
    """Deja solo el renglón "CAPÍTULO XV TER" de un encabezado que desemboca en
    un artículo, sin su denominación ni su nota. El parser no reconoce los
    capítulos TER/QUÁTER y su denominación se pegaba al artículo anterior."""
    out: list[str] = []
    i = 0
    while i < len(lineas):
        if not _ENCABEZADO_RE.match(lineas[i].strip()):
            out.append(lineas[i])
            i += 1
            continue
        j, en_nota, cabezas = i, False, []
        while j < len(lineas) and j - i <= _MAX_BLOQUE:
            s = lineas[j].strip()
            if ARTICULO_RE.match(s):
                break
            if _ENCABEZADO_RE.match(s):
                cabezas.append(lineas[j])
            elif _NOTA_RE.match(s) or (en_nota and s):
                en_nota = bool(_NOTA_ABIERTA_RE.search(s))
            elif s and not _DENOMINACION_RE.match(s):
                j = -1
                break
            j += 1
        if j == -1 or j >= len(lineas) or j - i > _MAX_BLOQUE:
            out.append(lineas[i])
            i += 1
            continue
        out.extend(cabezas)
        i = j
    return out


def preparar(texto: str) -> str:
    """Compacta los encabezados y deja cada "Nota: Se reformó mediante
    decreto…" en un solo renglón entre renglones en blanco: partida, normalize
    cortaba la nota tras "P.O. No." y la pegaba al párrafo siguiente."""
    # "H. Congreso" a inicio de renglón no es un apartado "H.".
    texto = re.sub(r"\n(H\. Congreso)", r" \1", texto)
    out: list[str] = []
    en_nota = False
    for linea in _compactar_encabezados(texto.split("\n")):
        s = linea.strip()
        if en_nota and s:
            out[-1] += " " + s
        elif _NOTA_RE.match(s):
            out.extend(["", linea])
        else:
            en_nota = False
            out.append(linea)
            continue
        en_nota = bool(_NOTA_ABIERTA_RE.search(s))
        if not en_nota:
            out.append("")
    return "\n".join(out)


_BASE = perfil_estatal(
    ambito="campeche",
    clave="cam",
    nombre="Constitución Política del Estado de Campeche",
    fuente="Periódico Oficial del Estado de Campeche — Congreso del Estado de Campeche",
    url_fuente=("https://legislacion.congresocam.gob.mx/~documents/anticorrupcion/"
                "constitucion-politica-del-estado-de-camp/?layout=file"),
    texto_original="1965-05-29",   # Decreto 190 (P.O. 29-05-1965), el texto más antiguo que cita el PDF
    label_ordinal="plano",         # "ARTÍCULO 1o.-" pero "ARTÍCULO 10.-" sin ordinal
    header_prefixes=(
        "CONSTITUCIÓN POLÍTICA DEL ESTADO DE CAMPECHE",
        "PODER LEGISLATIVO DEL ESTADO DE CAMPECHE",
        "SECRETARÍA GENERAL, DIRECCIÓN DE CONTROL DE PROCESOS LEGISLATIVOS",
        "COMPENDIO JURÍDICO DEL ESTADO, SECCIÓN LEYES",
        "DOCUMENTO PARA CONSULTA, SIN VALIDEZ LEGAL",
    ),
    # Número de página suelto al pie; los numerales del texto llevan punto.
    page_footer_re=re.compile(r"^\d{1,3}$"),
    version_de=version_encabezado,
    preprocess=preparar,
)

PERFIL = replace(
    _BASE,
    article_re=ARTICULO_RE,
    article_strip_re=ARTICULO_STRIP_RE,
    capitulo_re=re.compile(r"^CAP[ÍI]TULO\s+([IVXLC]+|[ÚU]NICO)(\s+(?:BIS|TER|QU[ÁA]TER))?$"),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

"""Aguascalientes: Constitución Política del Estado de Aguascalientes."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..parse import ENCABEZADO_RE
from ..perfil import perfil_estatal

# Las notas "(REFORMADO, P.O. 25 DE ABRIL DE 2025)" van en renglón propio
# ANTES del párrafo que anotan; a veces se parten en dos renglones.
# También las notas del editor "[N. DE E. REUBICADO -ANTES CAPÍTULO ...-, P.O. ...]".
_NOTA_RE = re.compile(
    r"^(?:\((?:[A-ZÁÉÍÓÚÑ]+\s+){0,2}(?:REFORMAD|ADICIONAD|DEROGAD|RECORRID|DECRETO|FE DE|F\. DE E)"
    r"|\[N\. DE E\.)")
# Una nota cierra en el año o en "]"; si no, sigue en el renglón siguiente.
_NOTA_CIERRA_RE = re.compile(r"(?:\d{4}\.?\)?|\])\s*$")
_MAX_RENGLONES_NOTA = 4
_ARTICULO_RE = re.compile(r"^(?:Art[íi]culo|ART[ÍI]CULOS?)\s+\d")


def separar_notas(texto: str) -> str:
    """Aísla cada nota de reforma del cuerpo con renglones en blanco: sin eso,
    la nota se pega al párrafo que sigue (termina en ")", no en punto). Dentro
    de un bloque de encabezado (Título/Capítulo/Sección + denominación) no se
    agregan: el parser solo reconoce bloques cortos."""
    lineas = texto.split("\n")
    out: list[str] = []
    en_encabezado = False
    i = 0
    while i < len(lineas):
        s = lineas[i].strip()
        if ENCABEZADO_RE.match(s):
            en_encabezado = True
        elif _ARTICULO_RE.match(s):
            en_encabezado = False
        if not _NOTA_RE.match(s):
            out.append(lineas[i])
            i += 1
            continue
        j, nota = i, lineas[i]
        while (nota.count("(") + nota.count("[") > nota.count(")") + nota.count("]")
               and not _NOTA_CIERRA_RE.search(nota)
               and j + 1 < len(lineas) and j - i < _MAX_RENGLONES_NOTA):
            j += 1
            nota += lineas[j]
        # Una nota partida en renglones queda en uno solo (el normalizador cortaría
        # en "[N." de "[N. DE E. ...]").
        nota = " ".join(x.strip() for x in lineas[i:j + 1])
        out += [nota] if en_encabezado else ["", nota, ""]
        i = j + 1
    return "\n".join(out)


# Capítulos con ordinal de una palabra que el parser no reconoce como encabezado
# ("CAPITULO UNDECIMO A", "CAPITULO DECIMOCTAVO", "CAPITULO VIGÉSIMO"): sin esto
# su denominación queda dentro del artículo anterior.
_CAPITULO_RE = re.compile(r"^CAP[ÍI]TULO\s+[A-ZÁÉÍÓÚ]+(?:\s+[A-Z])?\.?$")
_MAX_RENGLONES_CAPITULO = 6


def quitar_denominaciones(texto: str) -> str:
    """Tras un capítulo de esos, quita su denominación (y la nota de esta) hasta el
    artículo siguiente, como hace el parser con los encabezados que sí reconoce."""
    lineas = texto.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lineas):
        s = lineas[i].strip()
        out.append(lineas[i])
        if _CAPITULO_RE.match(s) and not ENCABEZADO_RE.match(s):
            fin = next((j for j in range(i + 1, min(i + 1 + _MAX_RENGLONES_CAPITULO, len(lineas)))
                        if _ARTICULO_RE.match(lineas[j].strip())), None)
            if fin is not None:
                i = fin
                continue
        i += 1
    return "\n".join(out)


def preprocesar(texto: str) -> str:
    return separar_notas(quitar_denominaciones(texto))


_VERSION_RE = re.compile(r"Última actualización: (\d{2})/(\d{2})/(\d{4})")


def version_encabezado(texto: str) -> Optional[date]:
    """Fecha del encabezado de página ("Última actualización: 07/09/2026.")."""
    m = _VERSION_RE.search(texto)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


_BASE = perfil_estatal(
    ambito="aguascalientes",
    clave="agu",
    nombre="Constitución Política del Estado de Aguascalientes",
    fuente="Periódico Oficial del Estado de Aguascalientes — Congreso del Estado de Aguascalientes",
    url_fuente="https://congresoags.gob.mx/agenda_legislativa/leyes/descargarPdf/2492",
    texto_original="1917-09-23",
    # Encabezado de cada página en tres renglones; el tercero trae la fecha de
    # actualización y cambia con cada reforma. Se quitan por renglón completo:
    # "CONSTITUCIÓN POLÍTICA DEL ESTADO DE" como prefijo también tocaría citas.
    page_footer_re=re.compile(
        r"(?:CONSTITUCIÓN POLÍTICA DEL ESTADO DE|AGUASCALIENTES|"
        r"Última actualización: \d{2}/\d{2}/\d{4}\.?)$"),
    # El articulado cierra en "ARTICULOS TRANSITORIOS." (con punto).
    transitorios_re=re.compile(
        r"^[ \t]*(?:Art[íi]culos?\s+Transitorios?|TRANSITORIOS?)\.?[ \t]*$",
        re.MULTILINE | re.IGNORECASE),
    version_de=version_encabezado,
    preprocess=preprocesar,
    notas_previas=_NOTA_RE,
)

# Artículos con letra sin guion ("Artículo 2o A.-", "Artículo 7o. A.-", "Artículo
# 55 A. El"). La letra solo cuenta si la sigue el cierre del encabezado: así "Artículo
# 27 C de esta Constitución" (cita partida a inicio de renglón) no abre el 27 C, y
# el segundo "Artículo 59 A (sic).-" del PDF —mismo número y letra que el anterior—
# queda dentro del 59 A en vez de sobrescribir su archivo.
_ART = (r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*[oº°]?\.?\s*"
        r"((?i:Bis|Ter)|[A-Z](?=\s*\.?\s*-|\.\s|\.$))?")
PERFIL = replace(
    _BASE,
    # Todo encabezado cierra en punto o guion; un renglón que empieza con una cita
    # ("Artículo 27 de la Constitución Política...") no abre artículo.
    article_re=re.compile(_ART + r"\s*(?:\.\s*-?|-)(?:\s|$)"),
    article_strip_re=re.compile(_ART + r"\s*\.?\s*-?\s*"),
    # Registra como capítulo también los de ordinal en una palabra (ver arriba).
    capitulo_re=re.compile(
        r"^Cap[íi]tulo\s+([IVXLC]+|[A-ZÁÉÍÓÚ]+(?:\s+[A-Z])?)(\s+Bis)?\.?\s*$", re.IGNORECASE),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

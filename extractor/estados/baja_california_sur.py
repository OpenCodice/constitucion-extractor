"""Baja California Sur: Constitución Política del Estado Libre y Soberano.

El Congreso la publica solo como Word (.doc); la vigilancia lo convierte a PDF
con LibreOffice y este perfil lee ese PDF. Los artículos se encabezan sin la
palabra "Artículo": "1o.-", "10o.-", "11.-", "7o Bis.-", "66 Ter.-".
"""
from __future__ import annotations

import re
from dataclasses import replace

from ..parse import ENCABEZADO_RE
from ..perfil import perfil_estatal, sin_fechas

_URL = "https://www.cbcs.gob.mx/LEYES-BCS/CPoliticaBCS-.doc"

# Encabezado de página del Word, renglón por renglón, y el número de página.
# Son renglones exactos: "California Sur" o "CONSTITUCIÓN POLÍTICA" como prefijo
# se comerían texto legal que empiece así.
_PAGINA_RE = re.compile(
    r"^(?:\d{1,3}|CONSTITUCIÓN POLÍTICA|DEL ESTADO DE BAJA CALIFORNIA SUR|California Sur|"
    r"Oficialía Mayor)$")

# Encabezado exacto "N[o][ Bis|Ter].-": las fracciones van en romanos ("I.-")
# y los numerales internos no llevan ".-" pegado.
_ARTICULO_RE = re.compile(r"^(\d{1,3})o?(?:\s+(Bis|Ter))?\.-(?:\s|$)")

# Los títulos vienen espaciados letra por letra ("T I T U L O S E G U N D O"):
# así no los reconoce el parser y quedan pegados al artículo anterior.
_ESPACIADO_RE = re.compile(r"^[A-ZÁÉÍÓÚ](?: [A-ZÁÉÍÓÚ]){5,}$")
_TITULO_PEGADO_RE = re.compile(
    r"^(T[IÍ]TULO)(PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|OCTAVO|"
    r"NOVENO|D[EÉ]CIMO|UND[EÉ]CIMO)(BIS)?$")
_MAX_RENGLONES_DENOMINACION = 4


def unir_titulos(texto: str) -> str:
    """Reconstruye los títulos espaciados. Del "TITULO UNDECIMO", cuyo ordinal el
    parser no reconoce como encabezado, quita además la denominación hasta el
    artículo siguiente, como hace el parser con los demás títulos."""
    lineas = texto.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lineas):
        s = lineas[i].strip()
        m = _TITULO_PEGADO_RE.match(s.replace(" ", "")) if _ESPACIADO_RE.match(s) else None
        if not m:
            out.append(lineas[i])
            i += 1
            continue
        titulo = " ".join(g for g in m.groups() if g)
        out.append(titulo)
        i += 1
        if not ENCABEZADO_RE.match(titulo):
            fin = next((j for j in range(i, min(i + _MAX_RENGLONES_DENOMINACION, len(lineas)))
                        if _ARTICULO_RE.match(lineas[j].strip())), None)
            if fin is not None:
                i = fin
    return "\n".join(out)


_BASE = perfil_estatal(
    ambito="baja-california-sur",
    clave="bcs",
    nombre="Constitución Política del Estado Libre y Soberano de Baja California Sur",
    fuente=("Boletín Oficial del Gobierno del Estado de Baja California Sur — H. Congreso "
            "del Estado de Baja California Sur (PDF generado del Word oficial)"),
    url_fuente=_URL,
    texto_original="1975-01-15",
    header_prefixes=("H. Congreso del Estado de Baja", "Departamento de Apoyo Parlamentario"),
    page_footer_re=_PAGINA_RE,
    # Portada: "Última reforma publicada BOGE 08-09-2026".
    version_re=re.compile(r"[ÚU]ltima\s+reforma\s+publicada\s+BOGE\s+(\d{2})-(\d{2})-(\d{4})"),
    label_ordinal="federal",
    # El texto no trae notas de reforma por artículo; las fechas del cuerpo
    # ("1 de octubre de 2027") no son reformas.
    fechas_de=sin_fechas,
    preprocess=unir_titulos,
)

PERFIL = replace(
    _BASE,
    article_re=_ARTICULO_RE,
    article_strip_re=re.compile(r"^\d{1,3}o?(?:\s+(?:Bis|Ter))?\.-\s*"),
    # Hay "TITULO UNDECIMO", que el genérico (hasta "Décimo") no reconoce.
    titulo_re=re.compile(
        r"^T[íi]tulo\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[ée]ptimo|"
        r"Octavo|Noveno|D[ée]cimo|Und[ée]cimo)\b.*$", re.IGNORECASE),
    # El Título Octavo Bis tiene "CAPÍTULO ÚNICO"; sin esto sus artículos
    # quedarían en el capítulo X del título anterior.
    capitulo_re=re.compile(r"^Cap[íi]tulo\s+([IVXLC]+|[ÚU]nico)\s*$", re.IGNORECASE),
)

RESOLVER = {"tipo": "directo", "url": _URL, "formato": "doc"}

LISTO = True

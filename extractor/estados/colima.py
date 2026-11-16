"""Colima: Constitución Política del Estado Libre y Soberano de Colima."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from ..parse import ENCABEZADO_RE
from ..perfil import _MESES, perfil_estatal, version_ultima_reforma

# Las notas "(REFORMADA DECRETO 113, P.O. 57, 03 AGOSTO 2019)" van en renglón propio
# ANTES del párrafo que anotan; a veces se parten en dos renglones.
_NOTA_RE = re.compile(
    r"^\((?:[A-ZÁÉÍÓÚÑ]+\s+){0,2}(?:REFORMAD|ADICIONAD|DEROGAD|RECORRID|DECRETO|FE DE|F\. DE E)")
# Una nota cierra en el año; si el paréntesis no cierra ahí, sigue en el renglón siguiente.
_NOTA_CIERRA_RE = re.compile(r"\d{4}\.?\)?\s*$")
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
        while (nota.count("(") > nota.count(")") and not _NOTA_CIERRA_RE.search(nota)
               and j + 1 < len(lineas) and j - i < _MAX_RENGLONES_NOTA):
            j += 1
            nota += lineas[j]
        # Una nota partida en renglones queda en uno solo (el normalizador cortaría
        # en "[N." de "[N. DE E. ...]").
        nota = " ".join(x.strip() for x in lineas[i:j + 1])
        out += [nota] if en_encabezado else ["", nota, ""]
        i = j + 1
    return "\n".join(out)


# Las notas escriben la fecha sin "de" ("03 AGOSTO 2019") casi siempre.
_FECHA_RE = re.compile(
    r"\b(\d{1,2})\s+(?:DE\s+)?(" + "|".join(_MESES) + r")\s+(?:DE\s+|DEL\s+)?(\d{4})\b",
    re.IGNORECASE)


def fechas_notas(texto: str) -> list[date]:
    out: set[date] = set()
    for d, mes, a in _FECHA_RE.findall(texto):
        try:
            out.add(date(int(a), _MESES[mes.lower()], int(d)))
        except ValueError:
            continue
    return sorted(out)


_BASE = perfil_estatal(
    ambito="colima",
    clave="col",
    nombre="Constitución Política del Estado Libre y Soberano de Colima",
    fuente="Periódico Oficial \"El Estado de Colima\" — Dirección de Proceso Legislativo del H. Congreso del Estado de Colima",
    url_fuente=("https://ipecol.col.gob.mx/Documentacion/9824%7CConstituci%C3%B3n%20"
                "Pol%C3%ADtica%20del%20Estado%20Libre%20y%20Soberano%20de%20Colima"),
    # Texto reordenado y consolidado (Decreto 439, P.O. 83 del 27-12-2017).
    texto_original="2017-12-27",
    header_prefixes=(
        "Constitución Política del Estado Libre y Soberano de Colima.",
        "Dirección de Proceso Legislativo del H. Congreso del Estado de Colima"),
    label_ordinal="masc",
    page_footer_re=re.compile(r"\d{1,3}$"),
    fechas_de=fechas_notas,
    version_de=version_ultima_reforma,
    preprocess=separar_notas,
    notas_previas=_NOTA_RE,
)

# El genérico de títulos para en "Décimo"; aquí hay "TÍTULO UNDÉCIMO" y
# "TÍTULO DUODÉCIMO", que sin esto quedan dentro del artículo anterior.
PERFIL = replace(
    _BASE,
    titulo_re=re.compile(
        r"^T[íi]tulo\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[ée]ptimo|"
        r"Octavo|Noveno|D[ée]cimo|Und[ée]cimo|Duod[ée]cimo)\b.*$", re.IGNORECASE),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

"""Chiapas: Constitución Política del Estado Libre y Soberano de Chiapas."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..perfil import _MESES, perfil_estatal

_VERSION_RE = re.compile(
    r"[ÚU]LTIMA\s+REFORMA\s+PUBLICADA.*?FECHA\s+(\d{1,2})\s+DE\s+(\w+)\s+DEL?\s+(\d{4})",
    re.IGNORECASE | re.DOTALL)


def version_portada(texto: str) -> Optional[date]:
    """Portada: "ÚLTIMA REFORMA PUBLICADA MEDIANTE PERIÓDICO OFICIAL NÚMERO 135,
    DE FECHA 30 DE SEPTIEMBRE DEL 2026" (partida en dos renglones)."""
    m = _VERSION_RE.search(texto)
    if not m or m.group(2).lower() not in _MESES:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


# Renglón que solo trae el número de un artículo citado ("...en los términos del
# artículo" / "55."): normalize lo tomaría por un inciso numerado.
_CITA_PARTIDA_RE = re.compile(r"(\bart[íi]culos?)\n(\d{1,3}\.)\n", re.IGNORECASE)


# Nota de reforma entre paréntesis y en mayúsculas, antes del texto que
# reforma: "(REFORMA PUBLICADA MEDIANTE P.O. NUM. 042 DE FECHA 28 DE MAYO DE 2025)".
_NOTA_RE = re.compile(r"^\((?:[A-ZÁÉÍÓÚÑ0-9]|Se deroga)")
_MAX_NOTA = 6


def preparar(texto: str) -> str:
    """Une la cita partida y deja cada nota de reforma en un solo renglón entre
    renglones en blanco: cierra en ")" y, sin esto, normalize la pegaba al
    párrafo que le sigue."""
    texto = _CITA_PARTIDA_RE.sub(r"\1 \2\n", texto)
    out: list[str] = []
    en_nota, n = False, 0
    for linea in texto.split("\n"):
        s = linea.strip()
        if en_nota and s and n < _MAX_NOTA and not _NOTA_RE.match(s):
            out[-1] += " " + s
            n += 1
        elif _NOTA_RE.match(s):
            out.extend(["", linea])
            n = 1
        else:
            if en_nota:
                out.append("")
            en_nota = False
            out.append(linea)
            continue
        en_nota = not s.endswith((")", ")."))
        if not en_nota:
            out.append("")
    return "\n".join(out)


PERFIL = perfil_estatal(
    ambito="chiapas",
    clave="chp",
    nombre="Constitución Política del Estado Libre y Soberano de Chiapas",
    fuente="H. Congreso del Estado de Chiapas (Legislación vigente)",
    url_fuente="https://www.congresochiapas.gob.mx/new/Info-Parlamentaria/LEY_0002.pdf",
    texto_original="2016-12-29",
    label_ordinal="plano",
    version_de=version_portada,
    preprocess=preparar,
    notas_previas=_NOTA_RE,
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

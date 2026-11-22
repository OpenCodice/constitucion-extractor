"""Constitución Política del Estado Libre y Soberano de Querétaro."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..perfil import perfil_estatal

URL = "https://site.legislaturaqueretaro.gob.mx/CloudPLQ/InvEst/Leyes/CON-ID-001.pdf"

# Nota de reforma partida en dos renglones ("(Adición P.\nO. No. 15, 23-II-18)"):
# el punto final del primer renglón se leería como fin de párrafo.
_NOTA_ABIERTA_RE = re.compile(r"(\((?:Ref|Adici[óo]n|Fe de erratas|Derog)[^)\n]*)\n")
# La nota "(Ref. P. O. No. 64, 23-VIII-19)", o un renglón entre paréntesis
# ("(entrará en vigor a partir del año 2021)"), cierra su párrafo.
_NOTA_CIERRE_RE = re.compile(r"(-[IVX]+-\d{2}\)|^\([^)\n]*\))\n", re.MULTILINE)


def _preprocess(texto: str) -> str:
    texto = _NOTA_ABIERTA_RE.sub(r"\1 ", texto)
    return _NOTA_CIERRE_RE.sub(r"\1\n\n", texto)


_ROMANOS = {r: i + 1 for i, r in enumerate(
    ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"])}
# Historial de cambios de la ficha genealógica: «40ª. Reforma Ley que… 15/07/2026 (No.58)».
_REFORMA_RE = re.compile(r"^\d+ª\.?\s*Reforma\b[^\n]*?(\d{2})/(\d{2})/(\d{4})", re.MULTILINE)
# Fecha de una nota de reforma: «(Ref. P. O. No. 64, 23-VIII-19)». Todas son de la
# Constitución de 2008 en adelante.
_NOTA_FECHA_RE = re.compile(r"\b(\d{1,2})-([IVX]{1,4})-(\d{2})\b")


def _version(texto: str) -> Optional[date]:
    """La portada no trae fecha: la versión es la reforma más reciente del
    historial de cambios de la ficha genealógica."""
    fechas = [date(int(a), int(m), int(d)) for d, m, a in _REFORMA_RE.findall(texto)]
    return max(fechas, default=None)


def _fechas(texto: str) -> list[date]:
    out: set[date] = set()
    for d, m, a in _NOTA_FECHA_RE.findall(texto):
        if m in _ROMANOS:
            try:
                out.add(date(2000 + int(a), _ROMANOS[m], int(d)))
            except ValueError:
                continue
    return sorted(out)


PERFIL = perfil_estatal(
    ambito="queretaro",
    clave="que",
    nombre="Constitución Política del Estado Libre y Soberano de Querétaro",
    fuente="Periódico Oficial «La Sombra de Arteaga» — Poder Legislativo del Estado de Querétaro",
    url_fuente=URL,
    texto_original="2008-03-31",
    label_ordinal="plano",
    preprocess=_preprocess,
    fechas_de=_fechas,
    version_de=_version,
    version_paginas=6,
)

RESOLVER = {"tipo": "directo", "url": URL}

LISTO = True

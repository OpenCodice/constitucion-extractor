"""Constitución Política del Estado Libre y Soberano de Querétaro."""
from __future__ import annotations

import re

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


PERFIL = perfil_estatal(
    ambito="queretaro",
    clave="que",
    nombre="Constitución Política del Estado Libre y Soberano de Querétaro",
    fuente="Periódico Oficial «La Sombra de Arteaga» — Poder Legislativo del Estado de Querétaro",
    url_fuente=URL,
    texto_original="2008-03-31",
    label_ordinal="plano",
    preprocess=_preprocess,
)

RESOLVER = {"tipo": "directo", "url": URL}

LISTO = True

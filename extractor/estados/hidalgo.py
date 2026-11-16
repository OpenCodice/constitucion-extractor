"""Constitución Política del Estado de Hidalgo."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

_URL = ("https://www.congreso-hidalgo.gob.mx/biblioteca_legislativa/leyes_cintillo/"
        "Constitucion%20Politica%20del%20Estado%20de%20Hidalgo.pdf")

# Encabezados pegados al texto ("Artículo 5.-La..."), sufijos latinos más allá
# de Ter y de letra ("Artículo 88a.-", derogados): el regex genérico los fundía
# con el artículo anterior.
_SUFIJOS = (r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
            r"|[a-z](?=\.?[-–—])")
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])?(?:\s|$|(?<=[.\-–—]))"

PERFIL = replace(
    perfil_estatal(
        ambito="hidalgo",
        clave="hid",
        nombre="Constitución Política del Estado de Hidalgo",
        fuente="Periódico Oficial del Estado de Hidalgo — Congreso del Estado de Hidalgo "
               "(Instituto de Estudios Legislativos)",
        url_fuente=_URL,
        texto_original="1920-10-01",
        label_ordinal="plano",
        # Encabezado de cada página. Con el punto final: sin él, "Constitución
        # Política del Estado de Hidalgo, otorgan..." (texto del art. 141) caería.
        header_prefixes=("Constitución Política del Estado de Hidalgo.",
                         "Instituto de Estudios Legislativos."),
        page_footer_re=re.compile(r"\d{1,3}$"),
        # El articulado cierra con "TRANSITORIOS:" (con dos puntos).
        transitorios_re=re.compile(r"^[ \t]*TRANSITORIOS:?[ \t]*$", re.MULTILINE),
        version_de=version_ultima_reforma,   # "ÚLTIMA REFORMA PUBLICADA ...: 8 DE JULIO DE 2026."
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
)

RESOLVER = {"tipo": "directo", "url": _URL}

LISTO = True

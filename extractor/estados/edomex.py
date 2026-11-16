"""Constitución Política del Estado Libre y Soberano de México."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

# Un número citado que quedó solo en el renglón siguiente ("…como lo dispone el
# artículo\n72."): el normalizador lo tomaría por el numeral de una lista.
_CITA_PARTIDA_RE = re.compile(r"([a-záéíóúñ])\n(\d{1,3}\.)$", re.MULTILINE)


def unir_citas(texto: str) -> str:
    return _CITA_PARTIDA_RE.sub(r"\1 \2", texto)


PERFIL = replace(
    perfil_estatal(
        ambito="edomex",
        clave="mex",
        nombre="Constitución Política del Estado Libre y Soberano de México",
        fuente="Periódico Oficial «Gaceta del Gobierno» — Gobierno del Estado de México (Legislación vigente)",
        url_fuente=("https://legislacion.edomex.gob.mx/sites/legislacion.edomex.gob.mx/"
                    "files/files/pdf/ley/vig/leyvig001.pdf"),
        texto_original="1917-11-10",
        header_prefixes=(
            "CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE MÉXICO",
            "Publicada en el Periódico Oficial “Gaceta del Gobierno” el 10, 14 y 17 de noviembre de 1917.",
            "Última reforma POGG"),
        label_ordinal="plano",
        # El número de página va suelto en su renglón; ningún renglón legal es solo un número.
        page_footer_re=re.compile(r"\d{1,3}$"),
        version_de=version_ultima_reforma,
        preprocess=unir_citas,
        # El articulado cierra en "T R A N S I T O R I O S", con las letras espaciadas.
        transitorios_re=re.compile(r"^[ \t]*T ?R ?A ?N ?S ?I ?T ?O ?R ?I ?O ?S[ \t]*$", re.MULTILINE),
    ),
    # El encabezado cierra en ".-" o "."; una vez sin espacio tras el guion
    # ("Artículo 84.-Para"), que el genérico no reconoce.
    article_re=re.compile(r"^Art[íi]culo\s+(\d+)\s*((?i:bis|ter))?\s*(?:\.-?|-)"),
    article_strip_re=re.compile(r"^Art[íi]culo\s+\d+\s*(?:(?i:bis|ter))?\s*(?:\.-?|-)\s*"),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente, "via": "mx"}

LISTO = True

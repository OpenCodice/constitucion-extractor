"""Constitución Política del Estado de Tamaulipas."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

PERFIL = replace(
    perfil_estatal(
        ambito="tamaulipas",
        clave="tam",
        nombre="Constitución Política del Estado de Tamaulipas",
        fuente="Periódico Oficial del Estado de Tamaulipas — H. Congreso del Estado de Tamaulipas",
        url_fuente=("https://www.congresotamaulipas.gob.mx/Parlamentario/Archivos/Constituciones/"
                    "Const%20Pol%20del%20Edo%20POE%2012-octubre%202026.pdf"),
        texto_original="1921-02-05",
        label_ordinal="plano",
        version_de=version_ultima_reforma,
        # pdfplumber lee el encabezado espaciado "T R A N S I T O R I O S".
        transitorios_re=re.compile(r"^[ \t]*T ?R ?A ?N ?S ?I ?T ?O ?R ?I ?O ?S[ \t]*$", re.MULTILINE),
        # Encabezado de cada página, con su folio.
        page_footer_re=re.compile(r"Constitución Política del Estado de Tamaulipas\s+Pág\.\s*\d+$"),
        # La marca de agua diagonal (Arial-Black, ~40 pt) se cuela letra por letra
        # en las palabras ("Abastolo"); el texto legal no usa esa fuente.
        filtro_char=lambda c: "Arial-Black" not in c.get("fontname", ""),
    ),
    # "ARTÍCULO 153 Bis. - El …" y "ARTÍCULO 49.-El …": el guion puede venir
    # separado del punto o pegado al texto.
    article_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*[oº°]?\s*((?i:Bis|Ter))?(?:\.?\s*-|\.?(?:\s|$))"),
    article_strip_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+\s*[oº°]?\s*(?i:Bis|Ter)?\.?\s*-?\s*"),
)

RESOLVER = {
    "tipo": "indice",
    # El nombre del PDF lleva la fecha de la reforma; esta página enlaza al vigente.
    "index_url": ("https://www.congresotamaulipas.gob.mx/LegislacionEstatal/Constituciones/"
                  "VerConstitucion.asp?IdConstitucion=1"),
    "encoding": "utf-8",
    "patron": re.compile(r'href="(/Parlamentario/Archivos/Constituciones/[^"]*\.pdf)"'),
    "orden": "unico",
}

LISTO = True

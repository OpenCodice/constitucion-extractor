"""Constitución Política del Estado Libre y Soberano de Sonora."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal

_SUFIJO = r"BIS|TER|QUATER|QUINQUIES|SEXIES|SEPTIES|OCTIES|[A-G]"

PERFIL = replace(
    perfil_estatal(
        ambito="sonora",
        clave="son",
        nombre="Constitución Política del Estado Libre y Soberano de Sonora",
        fuente="Boletín Oficial del Gobierno del Estado de Sonora — H. Congreso del Estado de Sonora",
        url_fuente=("https://gestion.api.congresoson.gob.mx/publico/descarga"
                    "?uuid=30cd30a6-8667-4041-87ad-8ce1112c2be6"),
        texto_original="1917-09-15",
        label_ordinal="plano",
        # pdfplumber lee el encabezado espaciado "T R A N S I T O R I O S".
        transitorios_re=re.compile(r"^[ \t]*T ?R ?A ?N ?S ?I ?T ?O ?R ?I ?O ?S[ \t]*$", re.MULTILINE),
        # Número de página suelto; ningún renglón del texto es solo dígitos.
        page_footer_re=re.compile(r"\d{1,3}$"),
    ),
    # Todo encabezado cierra en ".-"; sin exigirlo, las citas "Artículo 64 de esta
    # Constitución" que abren renglón pasarían el gate monotónico.
    article_re=re.compile(
        r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+(\d+)\s*[oº°]?\.?\s*(?:-\s*|\s+)?(" + _SUFIJO +
        r")?\s*\.?\s*-"),
    article_strip_re=re.compile(
        r"^(?:ART[ÍI]CULO|Art[íi]culo)\s+\d+\s*[oº°]?\.?\s*(?:-\s*|\s+)?(?:" + _SUFIJO +
        r")?\s*\.?\s*-\s*"),
)

RESOLVER = {
    "tipo": "indice",
    # API JSON que alimenta congresoson.gob.mx/leyes; "pdf" es el uuid del vigente.
    "index_url": ("https://gestion.api.congresoson.gob.mx/publico/ley?limite=20&pagina=1"
                  "&buscar=Constituci%C3%B3n%20Pol%C3%ADtica%20del%20Estado"
                  "&ordenar=nombre-asc&expand=vigente,totalVersiones,archivos"),
    "encoding": "utf-8",
    "patron": re.compile(r'"pdf":\s*"([0-9a-f-]{36})"'),
    "orden": "unico",
    "plantilla": "https://gestion.api.congresoson.gob.mx/publico/descarga?uuid={0}",
}

LISTO = True

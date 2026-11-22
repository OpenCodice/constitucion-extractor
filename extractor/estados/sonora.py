"""Constitución Política del Estado Libre y Soberano de Sonora."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import fechas_largas, perfil_estatal

_SUFIJO = r"BIS|TER|QUATER|QUINQUIES|SEXIES|SEPTIES|OCTIES|[A-G]"
# Cada entrada de la lista de reformas que cierra el PDF: «LEY 161; B. O. Edición
# Especial, de fecha 01 de noviembre de 2026, que…», a veces partida en renglones.
_PUBLICACION_RE = re.compile(
    r"^\*?LEY\s+\d+\b.{0,160}?de\s+fecha\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}",
    re.MULTILINE | re.DOTALL)


def _version(texto: str) -> Optional[date]:
    """La portada no trae fecha: la versión es la publicación más reciente de la
    lista de reformas del final del PDF."""
    fechas = [f for m in _PUBLICACION_RE.finditer(texto) for f in fechas_largas(m.group(0))[-1:]]
    return max(fechas, default=None)


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
        version_de=_version,
        version_paginas=None,
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

"""Constitución Política del Estado Libre y Soberano de Veracruz de Ignacio de la Llave."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..perfil import fechas_largas, perfil_estatal

# Las notas "(REFORMADO, G.O. 18 DE MARZO DE 2003)" van en renglón propio ANTES de
# lo que anotan; el PDF trae erratas ("REORMADO", "REFROMADA", "ADICI0NADO").
_NOTA = r"\((?:REFORMAD|REORMAD|REFROMAD|ADICI|DEROGAD|TEXTO VIGENTE POR|SE SUPRIME)"
_NOTA_LINEA_RE = re.compile(r"^(" + _NOTA + r"[^\n]*\)\*?)\n", re.MULTILINE)
# La "Sección Primera" del Capítulo IV se suprimió y quedó sola su denominación,
# sin encabezado que el parser reconozca: va, como la nota que la precede, con el
# artículo 64 que encabeza, no al final del 63.
_NOTAS_PREVIAS_RE = re.compile(_NOTA + r"|DEL CONTROL CONSTITUCIONAL$")


def preprocesar(texto: str) -> str:
    # Cada nota, su párrafo: sin eso se pega al texto que anota (cierra en ")") o
    # al renglón suelto que la precede ("…su negativa;\ny").
    return _NOTA_LINEA_RE.sub(r"\n\1\n\n", texto)


# Encabezado de cada página: "Secretaría General 30 DE OCTUBRE DE 2026".
_VERSION_RE = re.compile(r"^Secretaría General (.+)$", re.MULTILINE)


def version_encabezado(texto: str) -> Optional[date]:
    m = _VERSION_RE.search(texto)
    fechas = fechas_largas(m.group(1)) if m else []
    return fechas[0] if fechas else None


PERFIL = perfil_estatal(
    ambito="veracruz",
    clave="ver",
    nombre="Constitución Política del Estado Libre y Soberano de Veracruz de Ignacio de la Llave",
    fuente="Gaceta Oficial del Estado de Veracruz — H. Congreso del Estado de Veracruz",
    url_fuente="https://www.legisver.gob.mx/leyes/LeyesPDF/CONSTITUCION30102026AI.pdf",
    texto_original="1917-09-25",
    header_prefixes=(
        "H. CONGRESO DEL ESTADO DE VERACRUZ Última Actualización",
        "Coordinación de Investigaciones Legislativas"),
    label_ordinal="plano",
    page_footer_re=re.compile(
        r"(?:CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO|DE VERACRUZ DE IGNACIO DE LA LLAVE"
        r"|Secretaría General \d{1,2} DE [A-Z]+ DE \d{4})$"),
    version_de=version_encabezado,
    preprocess=preprocesar,
    # Los asteriscos de llamada a una "Nota de Editor" vienen en cuerpo grande y
    # pdfplumber los saca a un renglón propio, partiendo el párrafo.
    filtro_char=lambda c: not (c.get("text") == "*" and c.get("size", 0) > 11),
    notas_previas=_NOTAS_PREVIAS_RE,
    notas_previas_encabezado=True,
)

RESOLVER = {
    "tipo": "indice",
    # La lista de leyes enlaza el texto vigente con la fecha DDMMAAAA en el nombre
    # (CONSTITUCION30102026AI.pdf), junto a la Ley de Control Constitucional
    # (LCCONSTITUCIONAL…) y la iniciativa y el dictamen de la reforma integral.
    "index_url": "https://www.legisver.gob.mx/Inicio.php?p=le",
    "encoding": "utf-8",
    "patron": re.compile(
        r"""["'](leyes/LeyesPDF/CONSTITUCI(?:O|Ó|%C3%93)N(\d{8})[A-Z]*\.pdf)["']"""),
    "orden": "ddmmaaaa",
    "via": "mx",
}

LISTO = True

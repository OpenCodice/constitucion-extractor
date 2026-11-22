"""Perfil de fuente — todo lo que varía entre un documento legal y otro.

El extractor es UN motor + N perfiles. Un `PerfilFuente` reúne las constantes,
las regex de segmentación y los patrones de reforma propios de cada documento
(la CPEUM federal, la constitución de un estado, etc.). El motor downstream
(normalize → segments → passages → build) es agnóstico a la fuente: opera sobre
`Article[]` y lee de un perfil lo poco que cambia.

Escalera de excepciones (de la más barata a la más potente):

  Nivel 1 — solo config:   override de regex/flags en el `PerfilFuente`.
  Nivel 2 — hook puntual:   un callable opcional (`preprocess`, ...) en el perfil.
  Nivel 3 — segmentador propio: `estrategia` selecciona un segmentador a la
            medida que igual emite `Article[]` (la CPEUM es justo esto).

El contrato estable entre niveles es `Article[]`: pase lo que pase arriba, el
downstream solo ve artículos válidos + su perfil.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional


# --- Extractores de fechas de reforma (capa 3, best-effort, nunca cita) -------

# Federal (DOF): "... DOF 04-12-2006, 10-06-2011" — varias fechas por cláusula.
_DOF_CLAUSE_RE = re.compile(r"DOF\s+(\d{2}-\d{2}-\d{4}(?:\s*,\s*\d{2}-\d{2}-\d{4})*)")
_DOF_DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")

# Estatal típico: "Periódico Oficial ... 14 de junio de 2016".
_MESES = {m: i + 1 for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"])}
_FECHA_LARGA_RE = re.compile(
    r"(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")\s+de\s+(\d{4})", re.IGNORECASE)


def fechas_dof(text: str) -> list[date]:
    """Fechas de reforma estilo DOF presentes en `text`, únicas y ordenadas."""
    out: set[date] = set()
    for clause in _DOF_CLAUSE_RE.findall(text):
        for d, mo, y in _DOF_DATE_RE.findall(clause):
            out.add(date(int(y), int(mo), int(d)))
    return sorted(out)


def fechas_largas(text: str) -> list[date]:
    """Fechas estilo 'DD de mes de YYYY' (periódicos oficiales estatales)."""
    out: set[date] = set()
    for d, mo, y in _FECHA_LARGA_RE.findall(text):
        try:
            out.add(date(int(y), _MESES[mo.lower()], int(d)))
        except ValueError:
            # Erratas del propio PDF ("31 de junio"): no son una fecha que citar.
            continue
    return sorted(out)


def sin_fechas(text: str) -> list[date]:
    """Fuente sin provenance de reforma por-artículo (capa 3 vacía)."""
    return []


def version_ultima_reforma(text: str) -> Optional[date]:
    """Versión del PDF = fecha de 'Última reforma publicada ... el DD de mes de
    YYYY' (portada de los periódicos/gacetas estatales, p.ej. CDMX)."""
    m = re.search(
        r"[ÚU]ltima\s+reforma[^\n]*?(\d{1,2})\s+de\s+(" + "|".join(_MESES) +
        r")\s+de\s+(\d{4})", text, re.IGNORECASE)
    if not m:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


@dataclass(frozen=True)
class PerfilFuente:
    """Todo lo específico de una fuente. Los defaults son federales (CPEUM)."""

    # --- identidad / provenance -------------------------------------------
    ambito: str            # "federal", "jalisco", "cdmx" — partición del corpus
    clave: str             # prefijo de id estatal: "jal", "cmx" ("" para federal)
    nombre: str
    fuente: str
    url_fuente: str
    texto_original: str    # fecha del texto original para bloques sin reforma

    # --- segmentación (capa 1) --------------------------------------------
    estrategia: str        # "cpeum" | "generico" (qué segmentador usar)
    gate: str              # "estricto" (num==esperado) | "monotonico" (num>último)
    label_ordinal: str     # "federal" (1o.) | "masc" (1º) | "plano" (1)
    article_re: re.Pattern
    article_strip_re: re.Pattern   # para quitar el encabezado al normalizar el cuerpo
    titulo_re: re.Pattern
    capitulo_re: re.Pattern
    transitorios_re: re.Pattern
    version_re: Optional[re.Pattern]
    header_prefixes: tuple[str, ...]
    page_footer_re: Optional[re.Pattern]

    # --- reformas (capa 3, best-effort) -----------------------------------
    fechas_de: Callable[[str], list[date]]
    reform_note_start_re: re.Pattern   # detecta una nota de reforma al pie

    # Versión del PDF a partir de su portada (None → se usa version_re numérico,
    # o se pasa explícita por CLI si la fuente no la trae). Ver `version_date`.
    version_de: Optional[Callable[[str], Optional[date]]] = None
    # Páginas, desde la primera, que recibe `version_de` (None = todas): hay PDF
    # sin fecha en la portada que la traen en su tabla de reformas.
    version_paginas: Optional[int] = 1

    # --- gate de validación (validate.py) ---------------------------------
    n_articulos: Optional[int] = None       # cuenta esperada (None = no exigir)
    leak_markers: tuple[str, ...] = ()      # marcas de fuga de encabezado/pie
    leak_re: Optional[re.Pattern] = None    # fuga del pie "N de TOTAL" en el cuerpo
    # Mobiliario de página aprendido por `verificar` (fuente/ruido.json).
    ruido_res: tuple[re.Pattern, ...] = ()

    # --- hooks opcionales (Nivel 2) ---------------------------------------
    preprocess: Optional[Callable[[str], str]] = None
    # Qué caracteres del PDF se leen (p. ej. fuera la marca de agua, que
    # pdfplumber mezcla letra por letra con el texto). None = todos.
    filtro_char: Optional[Callable[[dict], bool]] = None
    # Fuentes que ponen la nota de reforma ANTES de lo que anota: un renglón que
    # sea nota según esta regex y quede justo antes de "Artículo N" abre el
    # artículo N en vez de cerrar el anterior (ver `parse_text`). None = no.
    notas_previas: Optional[re.Pattern] = None
    # Con `notas_previas`: también las notas antes de un bloque de encabezado
    # (Título/Capítulo/Sección) y dentro de él van al artículo que lo cierra.
    notas_previas_encabezado: bool = False
    # Fuentes que listan las reformas aparte del articulado (una tabla al final)
    # en vez de anotarlas en él: del texto completo, clave de artículo → fechas.
    # Se suman a las de `fechas_de`.
    reformas_de: Optional[Callable[[str], dict[str, list[date]]]] = None

    def prefijo_id(self, base: str) -> str:
        """Id namespaced por ámbito. Federal queda SIN prefijo (compat)."""
        return base if self.ambito == "federal" else f"{self.clave}:{base}"

    def etiqueta(self, number: int, suffix: str = "") -> str:
        """Etiqueta legal del artículo según el estilo ordinal de la fuente."""
        if self.label_ordinal == "federal":
            num = f"{number}o." if number <= 9 else f"{number}."
        elif self.label_ordinal == "masc":
            num = f"{number}º"
        else:  # "plano"
            num = f"{number}"
        suf = f" {suffix}" if suffix else ""
        return f"Artículo {num}{suf}"


# Patrón que nunca coincide (para fuentes sin notas de reforma inline).
_NUNCA_RE = re.compile(r"(?!x)x")


# ====================================================================== CPEUM
# Perfil federal. Reproduce EXACTAMENTE el comportamiento previo del extractor:
# las regex son las que vivían como globales en parse/normalize/passages.

CPEUM = PerfilFuente(
    ambito="federal",
    clave="",
    nombre="Constitución Política de los Estados Unidos Mexicanos",
    fuente="Diario Oficial de la Federación — CPEUM, H. Cámara de Diputados",
    url_fuente="https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf",
    texto_original="1917-02-05",
    estrategia="cpeum",
    gate="estricto",
    label_ordinal="federal",
    article_re=re.compile(r"^Artículo\s+(\d+)\s*[oº°]?\s*(Bis|Ter)?\.?-?(?:\s|$)"),
    article_strip_re=re.compile(r"^Artículo\s+\d+\s*[oº°]?\s*(?:Bis|Ter)?\.?-?\s*"),
    titulo_re=re.compile(
        r"^T[íi]tulo\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|"
        r"Séptimo|Octavo|Noveno|Décimo)\b.*$"),
    capitulo_re=re.compile(r"^Cap[íi]tulo\s+([IVXLC]+)(\s+Bis)?\s*$"),
    transitorios_re=re.compile(
        r"^[ \t]*(?:Artículos?\s+Transitorios?|ARTÍCULOS?\s+TRANSITORIOS?|"
        r"TRANSITORIOS?)[ \t]*$", re.MULTILINE),
    version_re=re.compile(
        r"[ÚU]ltimas?\s+[Rr]eformas?\s+(?:publicadas\s+)?DOF\s+(\d{2})-(\d{2})-(\d{4})"),
    header_prefixes=(
        "CONSTITUCIÓN POLÍTICA", "CÁMARA DE DIPUTADOS",
        "Secretaría General", "Secretaría de Servicios"),
    page_footer_re=re.compile(r"^\d{1,4}\s+de\s+\d{3,4}$"),
    fechas_de=fechas_dof,
    reform_note_start_re=re.compile(
        r"^(?:Párrafo|Fracción|Inciso|Apartado|Artículo|Reforma|Adicion|"
        r"Reformad|Recorrid|Denominación|Fe de|Adicionad)\b.*DOF\s+\d{2}-\d{2}-\d{4}"),
    n_articulos=136,
    leak_markers=("CÁMARA DE DIPUTADOS", "Secretaría de Servicios"),
    leak_re=re.compile(r"\b\d{1,3} de \d{3}\b"),
)


def perfil_estatal(
    *, ambito: str, clave: str, nombre: str, fuente: str, url_fuente: str,
    texto_original: str,
    header_prefixes: tuple[str, ...] = (),
    version_re: Optional[re.Pattern] = None,
    transitorios_re: Optional[re.Pattern] = None,   # override (Nivel 1) si el genérico falla
    label_ordinal: str = "masc",
    fechas_de: Callable[[str], list[date]] = fechas_largas,
    reform_note_start_re: re.Pattern = _NUNCA_RE,
    n_articulos: Optional[int] = None,
    page_footer_re: Optional[re.Pattern] = None,   # override (Nivel 1) si el PDF
                                                   # trae números de página sueltos
    version_de: Optional[Callable[[str], Optional[date]]] = None,
    version_paginas: Optional[int] = 1,
    preprocess: Optional[Callable[[str], str]] = None,
    filtro_char: Optional[Callable[[dict], bool]] = None,
    notas_previas: Optional[re.Pattern] = None,
    notas_previas_encabezado: bool = False,
    reformas_de: Optional[Callable[[str], dict[str, list[date]]]] = None,
) -> PerfilFuente:
    """Construye un perfil estatal genérico (Nivel 1).

    Diferencias estructurales frente al federal, ya absorbidas aquí:
    - Gate MONOTÓNICO: tolera huecos por derogación (un solo artículo derogado
      ya no detiene el parseo, como pasaba con el gate estricto federal).
    - Regex IGNORECASE: artículos/títulos/capítulos en MAYÚSCULAS (CDMX) o con
      ordinal masculino "1º" (Jalisco).
    - Reformas: por defecto sin notas inline (los PDFs estatales suelen llevar
      la historia de reformas en sección aparte; capa 3 best-effort).
    """
    return PerfilFuente(
        ambito=ambito, clave=clave, nombre=nombre, fuente=fuente,
        url_fuente=url_fuente, texto_original=texto_original,
        estrategia="generico", gate="monotonico", label_ordinal=label_ordinal,
        # Encabezado en Title-case ("Artículo") o MAYÚSCULAS ("ARTÍCULO"), pero
        # NO minúscula ("artículo 51 de la Ley...") que son CITAS dentro del
        # cuerpo: con el gate monotónico una cita "artículo 51" saltaría `last`
        # a 51 y descartaría 37 artículos reales. (Lo atrapó el gate de validate.)
        # Tras el número, guion, semirraya o raya ("155.–"): los PDF los mezclan.
        article_re=re.compile(
            r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*[oº°]?\s*((?i:Bis|Ter))?\.?[-–—]?(?:\s|$)"),
        article_strip_re=re.compile(
            r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+\s*[oº°]?\s*(?i:Bis|Ter)?\.?[-–—]?\s*"),
        titulo_re=re.compile(
            r"^T[íi]tulo\s+(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|"
            r"S[ée]ptimo|Octavo|Noveno|D[ée]cimo)\b.*$", re.IGNORECASE),
        capitulo_re=re.compile(
            r"^Cap[íi]tulo\s+([IVXLC]+)(\s+(?:Bis|Ter|Qu[áa]ter|(?-i:[A-Z])))?\.?\s*$", re.IGNORECASE),
        transitorios_re=transitorios_re or re.compile(
            r"^[ \t]*(?:Art[íi]culos?\s+Transitorios?|TRANSITORIOS?)[ \t]*$",
            re.MULTILINE | re.IGNORECASE),
        version_re=version_re,
        header_prefixes=header_prefixes,
        page_footer_re=page_footer_re,
        fechas_de=fechas_de,
        reform_note_start_re=reform_note_start_re,
        version_de=version_de,
        version_paginas=version_paginas,
        n_articulos=n_articulos,
        # si el encabezado repetido se cuela en el cuerpo, que el gate lo atrape
        leak_markers=header_prefixes,
        preprocess=preprocess,
        filtro_char=filtro_char,
        notas_previas=notas_previas,
        notas_previas_encabezado=notas_previas_encabezado,
        reformas_de=reformas_de,
    )


def pagina(page, perfil: "PerfilFuente"):
    """La página de pdfplumber tal como la lee este perfil (con `filtro_char`)."""
    if perfil.filtro_char is None:
        return page
    filtro = perfil.filtro_char
    return page.filter(lambda o: o.get("object_type") != "char" or filtro(o))

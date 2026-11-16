"""Chihuahua: Constitución Política del Estado Libre y Soberano de Chihuahua."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import perfil_estatal

_VERSION_RE = re.compile(r"[ÚU]ltima reforma POE (\d{4})\.(\d{2})\.(\d{2})")


def version_encabezado(texto: str) -> Optional[date]:
    """Encabezado de página: "Última reforma POE 2026.10.17/No. 83"."""
    m = _VERSION_RE.search(texto)
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


# El encabezado de página suma una línea por cada acción de inconstitucionalidad
# pendiente y la fecha de la última reforma: cambia de una versión a otra, así
# que se reconoce por forma (renglón completo), no por texto fijo.
_RUIDO = (
    re.compile(r"^Acci[óo]n (?:de )?Inconstitucionalidad [\d/]+(?: y)?$"),
    re.compile(r"^(?:y su acumulada|y sus acumuladas|Acumuladas?) [\d/, y]+$"),
    re.compile(r"^[ÚU]ltima reforma POE \d{4}\.\d{2}\.\d{2}/No\. \d+$"),
)


_SUFIJO = r"Bis|Ter|Quater|Quinquies"
# Hay sufijos hasta QUINQUIES (art. 10); sin ellos el 10 QUATER y el 10
# QUINQUIES quedaban dentro del 10 TER.
ARTICULO_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*[oº°]?\s*((?i:" + _SUFIJO + r"))?\.?[-–—]?(?:\s|$)")
ARTICULO_STRIP_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+\s*[oº°]?\s*(?i:" + _SUFIJO + r")?\.?[-–—]?\s*")
_ENCABEZADO_RE = re.compile(r"^(?:T[ÍI]TULO|CAP[ÍI]TULO)\s+[IVXLC]+\b")
# Las notas reales ocupan a lo más tres renglones; alguna no cierra el corchete.
_MAX_NOTA = 4


def separar_notas(texto: str) -> str:
    """Deja cada nota "[Artículo reformado mediante Decreto …]" en un solo
    renglón entre renglones en blanco: cierra en "]", no en punto, y sin esto
    normalize la pegaba al párrafo siguiente."""
    out: list[str] = []
    en_nota, n = False, 0
    for linea in texto.split("\n"):
        s = linea.strip()
        if (en_nota and s and n < _MAX_NOTA and not s.startswith("[")
                and not ARTICULO_RE.match(s) and not _ENCABEZADO_RE.match(s)):
            out[-1] += " " + s
            n += 1
        elif s.startswith("["):
            out.extend(["", linea])
            n = 1
        else:
            if en_nota:
                out.append("")
            en_nota = False
            out.append(linea)
            continue
        en_nota = not s.endswith("]")
        if not en_nota:
            out.append("")
    return "\n".join(out)


_BASE = perfil_estatal(
    ambito="chihuahua",
    clave="chh",
    nombre="Constitución Política del Estado Libre y Soberano de Chihuahua",
    fuente="H. Congreso del Estado de Chihuahua (Biblioteca Legislativa)",
    url_fuente=("https://www.congresochihuahua.gob.mx/biblioteca/constitucion/"
                "archivosConstitucion/actual.pdf"),
    texto_original="1950-06-17",
    label_ordinal="plano",         # "ARTICULO 1º." pero "ARTICULO 10." sin ordinal
    header_prefixes=(
        "H. Congreso del Estado Constitución Política",
        "Secretaría de Asuntos Legislativos y Jurídicos del Estado Libre y Soberano",
        "Biblioteca Legislativa “Carlos Montemayor Aceves”",
        # Pie de la portada (solo en la página 1).
        "Edificio Legislativo", "Libertad No.9 Col. Centro", "C.P. 31000 Chihuahua",
        "Tel: (614)", "http://congresochihuahua.gob.mx",
    ),
    page_footer_re=re.compile(r"^\d{1,3} de \d{1,3}$"),
    version_de=version_encabezado,
    preprocess=separar_notas,
)

PERFIL = replace(
    _BASE, ruido_res=_RUIDO, article_re=ARTICULO_RE, article_strip_re=ARTICULO_STRIP_RE,
    # Títulos en romano: "TITULO III".
    titulo_re=re.compile(r"^T[ÍI]TULO\s+[IVXLC]+$", re.IGNORECASE),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

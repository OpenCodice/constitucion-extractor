"""Yucatán: Constitución Política del Estado de Yucatán."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from dataclasses import replace

from ..perfil import _MESES, perfil_estatal

_SUFIJO = r"Bis|Ter|Quater|Quinquies|Sexies|Septies|Octies|Nonies"
# Hay sufijos hasta "Nonies" (art. 75 Quater … 75 Nonies), no solo Bis/Ter.
ARTICULO_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*[oº°]?\s*((?i:" + _SUFIJO + r"))?\.?[-–—]?(?:\s|$)")
ARTICULO_STRIP_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+\s*[oº°]?\s*(?i:" + _SUFIJO + r")?\.?[-–—]?\s*")

_ORDINAL = (r"(?:[IVXLC]+|PRIMER[OA]|SEGUND[OA]|TERCER[OA]|CUART[OA]|QUINT[OA]|"
            r"SEXT[OA]|S[ÉE]PTIM[OA]|OCTAV[OA]|NOVEN[OA]|D[ÉE]CIM[OA]|UND[ÉE]CIM[OA]|"
            r"DUOD[ÉE]CIM[OA]|[ÚU]NIC[OA]|PRELIMINAR)")
_ENCABEZADO_RE = re.compile(
    r"^(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+" + _ORDINAL + r"(?:\s+BIS)?$", re.IGNORECASE)

# Nota de reforma en renglón propio: "Párrafo adicionado D.O. 12-09-2022",
# también "DO 09-02-2023/ recorrido D.O. 24-10-2025" o "D.O. 9-junio-2020".
_NOTA_RE = re.compile(
    r"^(?:P[áa]rrafos?|Fracci[óo]n(?:es)?|Incisos?|Art[íi]culo|Cap[íi]tulo|Base|"
    r"Apartado|T[íi]tulo|Secci[óo]n|Denominaci[óo]n|Numeral|Proemio)\b"
    r".*(?:\bD\.?O\.?\s+\d|\d{1,2}-\d{2}-\d{4}\s*$)")
_FECHA_DO_RE = re.compile(r"\bD\.?O\.?\s+(\d{1,2})-(\d{2})[-/](\d{4})")
_VERSION_RE = re.compile(
    r"[ÚU]ltima\s+reforma\s+D\.O\.\s+(\d{1,2})\s*[-/]\s*(\w+)\s*[-/]\s*(\d{4})",
    re.IGNORECASE)


def fechas_do(texto: str) -> list[date]:
    """Fechas de las notas "… D.O. DD-MM-AAAA" del Diario Oficial del Estado."""
    out: set[date] = set()
    for d, m, y in _FECHA_DO_RE.findall(texto):
        try:
            out.add(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return sorted(out)


def version_portada(texto: str) -> Optional[date]:
    """Portada: "Última reforma D.O. 04-septiembre-2026"."""
    m = _VERSION_RE.search(texto)
    if not m or m.group(2).lower() not in _MESES:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


_MAX_BLOQUE = 12


def _compactar_encabezados(lineas: list[str]) -> list[str]:
    """Deja solo los renglones "TÍTULO QUINTO" / "CAPÍTULO I" de una cadena de
    encabezados que desemboca en un artículo, sin su denominación ni su nota.
    El parser solo reconoce el bloque si el ordinal está en su lista (no trae
    "UNDÉCIMO") y si el artículo llega en pocas líneas; si no, la denominación
    se pegaba al final del artículo anterior."""
    out: list[str] = []
    i = 0
    while i < len(lineas):
        if not _ENCABEZADO_RE.match(lineas[i].strip()):
            out.append(lineas[i])
            i += 1
            continue
        j, cabezas = i, []
        while j < len(lineas) and j - i <= _MAX_BLOQUE:
            s = lineas[j].strip()
            if ARTICULO_RE.match(s):
                break
            if _ENCABEZADO_RE.match(s):
                cabezas.append(lineas[j])
            elif s and not _NOTA_RE.match(s) and re.search(r"[.;:,]$", s):
                j = -1
                break
            j += 1
        if j == -1 or j >= len(lineas) or j - i > _MAX_BLOQUE:
            out.append(lineas[i])
            i += 1
            continue
        out.extend(cabezas)
        i = j
    return out


def preparar(texto: str) -> str:
    """Compacta los encabezados y aísla cada nota de reforma con renglones en
    blanco: la nota no cierra en punto y, sin eso, se pega al párrafo siguiente."""
    # Un renglón que empieza con decimal ("0.70% del presupuesto…") continúa la
    # frase; normalize lo tomaría por un numeral "0.".
    texto = re.sub(r"\n(\d+\.\d)", r" \1", texto)
    out: list[str] = []
    for linea in _compactar_encabezados(texto.split("\n")):
        if _NOTA_RE.match(linea.strip()):
            out.extend(["", linea, ""])
        else:
            out.append(linea)
    return "\n".join(out)


_BASE = perfil_estatal(
    ambito="yucatan",
    clave="yuc",
    nombre="Constitución Política del Estado de Yucatán",
    fuente=("H. Congreso del Estado de Yucatán (Secretaría General del Poder Legislativo, "
            "Unidad de Servicios Técnico-Legislativos)"),
    url_fuente="https://www.congresoyucatan.gob.mx/storage/documentos/constitucion.pdf",
    texto_original="1918-01-14",
    label_ordinal="plano",
    header_prefixes=(
        "CONSTITUCIÓN POLÍTICA DEL ESTADO DE YUCATÁN",
        "H. Congreso del Estado de Yucatán",
        "Secretaría General del Poder Legislativo",
        "Unidad de Servicios Técnico-Legislativos",
    ),
    # Número de página suelto al pie; los numerales del texto llevan punto.
    page_footer_re=re.compile(r"^\d{1,3}$"),
    fechas_de=fechas_do,
    reform_note_start_re=_NOTA_RE,
    version_de=version_portada,
    preprocess=preparar,
)

PERFIL = replace(
    _BASE,
    article_re=ARTICULO_RE,
    article_strip_re=ARTICULO_STRIP_RE,
    titulo_re=re.compile(r"^T[ÍI]TULO\s+" + _ORDINAL + r"(?:\s+BIS)?$", re.IGNORECASE),
    capitulo_re=re.compile(r"^CAP[ÍI]TULO\s+" + _ORDINAL + r"(\s+BIS)?$", re.IGNORECASE),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

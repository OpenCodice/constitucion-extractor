"""Registro de fuentes conocidas (ámbito → PerfilFuente).

Cada constitución estatal es UN perfil declarativo (Nivel 1). Si un estado
resulta irregular, su perfil sube de nivel: hook (`preprocess`) o, en el
extremo, una `estrategia` con segmentador propio. El gate de `validate.py`
es quien delata cuándo un perfil no basta.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .estados import cargar_estados
from .perfil import (_MESES, CPEUM, PerfilFuente, perfil_estatal, sin_fechas,
                     version_ultima_reforma)

# Jalisco no anota las reformas en el texto: las lista al final, en la "TABLA
# DE REFORMAS Y ADICIONES", un decreto por entrada:
#   "29842/LXIV/25.- Se reforman los artículos 9, 21, 35, 74, 97, 106 y 107 Ter,
#    de la Constitución Política del Estado de Jalisco.- Oct. 16 de 2025, sec. III."
# Las fechas que cita el articulado no son reformas.
_JAL_TABLA_RE = re.compile(
    r"^TABLA DE REFORMAS Y ADICIONES\s*$(.*?)(?=^TABLA DE |\Z)", re.MULTILINE | re.DOTALL)
_JAL_DECRETO_RE = re.compile(
    r"^\d{4,5}(?:/[A-Z]+/?\d+)?(?:\s+y\s+Acuerdo|[.,]\s*-?\s*(?:Se|Reforma|Adiciona|"
    r"Modifica|Decreto|que|Deroga|Aprueba)\b)", re.IGNORECASE)
# Lo que no es un decreto de reforma cierra la entrada anterior: acuerdos que
# declaran aprobada una minuta, fes de erratas, aclaraciones, notas del editor.
_JAL_OTRA_RE = re.compile(r"^(?:ACUERDO|FE DE ERRATAS|A\.L\.|\(N\.\s*de\s*E)", re.IGNORECASE)
_JAL_MES_CORTO = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
                  "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12}
_JAL_FECHA_RE = re.compile(
    r"\b(?P<mc>" + "|".join(sorted(_JAL_MES_CORTO, key=len, reverse=True)) +
    r")\.?\s*-?\s*(?P<dc>\d{1,2})\s*[º°]?\s*\.?\s*de\s+(?P<ac>\d{4})"
    r"|\b(?P<dl>\d{1,2})\s*[º°]?\s*\.?\s*de\s+(?P<ml>" + "|".join(_MESES) +
    r")\s+(?:de\s+)?(?P<al>\d{4})", re.IGNORECASE)
# El texto vigente viene del decreto 15424 (P.O. 13 de julio de 1994), que
# reescribió los artículos 1 a 67 y añadió del 68 al 112: los decretos
# anteriores numeran artículos que ya no son los de hoy.
_JAL_TEXTO_VIGENTE = date(1994, 7, 13)
_JAL_ART_RE = re.compile(r"\bart(?:[íi]culos?|s?\.)", re.IGNORECASE)
# El tramo de una entrada que reforma otro ordenamiento ("… 30 de la Ley
# Orgánica del Poder Ejecutivo") no es de la Constitución.
_JAL_ORDENAMIENTO_RE = re.compile(
    r"\b(?:de\s+(?:la|el|esta)|del)\s+(Constituci[óo]n|Ley|C[óo]digo|Reglamento|Estatuto)\b",
    re.IGNORECASE)
_JAL_RANGO_RE = re.compile(r"\b(?:del\s+)?(\d{1,3})\s+(?:al?)\s+(\d{1,3})\b")
_JAL_NUM_RE = re.compile(
    r"(?<![\w/])(\d{1,3})(?![\d/])\s*[º°]?\.?\s*(?:-?\s*(bis|ter|qu[áa]ter)\b)?",
    re.IGNORECASE)
_JAL_NO_ARTICULO_RE = re.compile(
    r"(?:decreto|n[úu]mero|No\.|sec\.|Núm\.|acuerdo(?:\s+legislativo)?)\s*$", re.IGNORECASE)


def _fecha_jal(m: re.Match) -> Optional[date]:
    try:
        if m.group("mc"):
            return date(int(m.group("ac")), _JAL_MES_CORTO[m.group("mc").lower()],
                        int(m.group("dc")))
        return date(int(m.group("al")), _MESES[m.group("ml").lower()], int(m.group("dl")))
    except ValueError:
        return None


def _clave_jal(numero: str, sufijo: str | None) -> str:
    clave = f"{int(numero):03d}"
    if sufijo:
        clave += "-" + sufijo.lower().replace("á", "a")
    return clave


def _articulos_jal(descripcion: str) -> set[str]:
    """Claves de los artículos de la Constitución que cita la descripción de un
    decreto. Solo cuenta lo que sigue a "artículo(s)"/"art(s)." y no lo que
    toca a otra ley."""
    claves: set[str] = set()
    inicio = 0
    tramos = []
    for m in _JAL_ORDENAMIENTO_RE.finditer(descripcion):
        tramos.append((descripcion[inicio:m.start()], m.group(1).lower().startswith("constituci")))
        inicio = m.end()
    tramos.append((descripcion[inicio:], True))
    for tramo, de_la_constitucion in tramos:
        if not de_la_constitucion:
            continue
        a = _JAL_ART_RE.search(tramo)
        if not a:
            continue
        tramo = tramo[a.start():]
        for r in _JAL_RANGO_RE.finditer(tramo):
            desde, hasta = int(r.group(1)), int(r.group(2))
            if desde < hasta <= desde + 120:
                claves.update(f"{n:03d}" for n in range(desde, hasta + 1))
        for n in _JAL_NUM_RE.finditer(tramo):
            if not _JAL_NO_ARTICULO_RE.search(tramo[:n.start()]):
                claves.add(_clave_jal(n.group(1), n.group(2)))
    return claves


def reformas_tabla_jalisco(texto: str) -> dict[str, list[date]]:
    """Artículo → fechas de publicación de los decretos que lo reforman, según
    la tabla de reformas del final del PDF."""
    tabla = _JAL_TABLA_RE.search(texto)
    if not tabla:
        return {}
    entradas: list[str] = []
    actual: list[str] | None = None
    for linea in tabla.group(1).splitlines():
        s = linea.strip()
        if _JAL_DECRETO_RE.match(s):
            actual = [s]
            entradas.append(actual)          # type: ignore[arg-type]
        elif _JAL_OTRA_RE.match(s):
            actual = None
        elif actual is not None and s:
            actual.append(s)
    out: dict[str, set[date]] = {}
    for entrada in entradas:
        texto_entrada = " ".join(entrada)
        m = _JAL_FECHA_RE.search(texto_entrada)
        fecha = _fecha_jal(m) if m else None
        if fecha is None or fecha < _JAL_TEXTO_VIGENTE:
            continue
        for clave in _articulos_jal(texto_entrada[:m.start()]):
            out.setdefault(clave, set()).add(fecha)
    return {k: sorted(v) for k, v in out.items()}


JALISCO = perfil_estatal(
    ambito="jalisco",
    clave="jal",
    nombre="Constitución Política del Estado de Jalisco",
    fuente="Periódico Oficial del Estado de Jalisco — Congreso del Estado de Jalisco",
    url_fuente=(
        "https://congresoweb.congresojal.gob.mx/bibliotecavirtual/legislacion/"
        "Constitución/Documentos_PDF-Constitución/"
        "Constitución Política del Estado de Jalisco-180423.pdf"),
    texto_original="1917-08-02",   # vigencia del texto original
    header_prefixes=(),            # no repite encabezado por página
    label_ordinal="masc",          # "Artículo 1º"
    fechas_de=sin_fechas,
    reformas_de=reformas_tabla_jalisco,
)

# CDMX. La Consejería Jurídica publica el texto vigente con una nota al margen
# por cada cambio, después de lo que anota: "Numeral reformado G.O. CDMX
# 23/12/24" (también "G.O.CDMX", "CDMX." y la errata "refirmado"). Las
# ediciones de 2019 del Congreso la ponían dentro del texto: "(REFORMADO G.O.
# CDMX 26 DE JULIO DE 2019)".
_CDMX_NOTA = (r"(?:P[áa]rrafo|Numeral|Inciso|Fracci[óo]n|Apartado|Art[íi]culo|"
              r"T[íi]tulo|Transitorio|Base|Denominaci[óo]n)\s+\w+[oa]\s+"
              r"G\.\s?O\.\s?CDMX\.?\s*\d{1,2}/\d{1,2}/\d{2,4}")
_CDMX_NOTA_EN_RENGLON_RE = re.compile(_CDMX_NOTA, re.IGNORECASE)
_CDMX_FECHA_NOTA_RE = re.compile(r"G\.\s?O\.\s?CDMX\.?\s*(\d{1,2})/(\d{1,2})/(\d{2,4})")
_CDMX_NOTA_TEXTO_RE = re.compile(
    r"\((?:REFORMAD|ADICIONAD|DEROGAD|FE DE ERRATAS)[^)]*G\.\s?O\.[^)]*\)", re.IGNORECASE)
_CDMX_FECHA_LARGA_RE = re.compile(
    r"(\d{1,2})\s+DE\s+(" + "|".join(_MESES) + r")\s+DE\s+(\d{4})", re.IGNORECASE)


# "TÍTULO SEGUNDO CARTA / DE DERECHOS": la denominación empieza en el renglón
# del título, y el parser solo reconoce el bloque de encabezado si el título
# va solo en el suyo (si no, "DE DERECHOS" se pega al artículo anterior).
_CDMX_TITULO_CON_DENOMINACION_RE = re.compile(
    r"^(T[ÍI]TULO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|"
    r"OCTAVO|NOVENO|D[ÉE]CIMO))\s+(\S.*)$")


def separar_notas_cdmx(texto: str) -> str:
    """Cada nota al margen en su propio párrafo. Sin renglón en blanco, el
    normalizador la uniría a lo que sigue (solo cierra una nota en una fecha
    "DD-MM-AAAA"). Si comparte renglón con el texto ("Derogado. Párrafo
    derogado G.O. …") o con otra nota, se separa. También deja el título solo
    en su renglón."""
    out: list[str] = []
    for linea in texto.split("\n"):
        linea = _CDMX_TITULO_CON_DENOMINACION_RE.sub(r"\1\n\2", linea)
        partes = _CDMX_NOTA_EN_RENGLON_RE.split(linea)
        notas = _CDMX_NOTA_EN_RENGLON_RE.findall(linea)
        if not notas:
            out.append(linea)
            continue
        for texto_previo, nota in zip(partes, notas):
            if texto_previo.strip():
                out.append(texto_previo.rstrip())
            out += ["", nota, ""]
        if partes[-1].strip():
            out.append(partes[-1].strip())
    return "\n".join(out)


def fechas_cdmx(texto: str) -> list[date]:
    """Fechas de las notas de reforma, no de cualquier fecha que cite el texto."""
    out: set[date] = set()
    for d, m, a in _CDMX_FECHA_NOTA_RE.findall(texto):
        anio = int(a) + 2000 if len(a) == 2 else int(a)
        try:
            out.add(date(anio, int(m), int(d)))
        except ValueError:
            continue
    for nota in _CDMX_NOTA_TEXTO_RE.findall(texto):
        for d, mes, a in _CDMX_FECHA_LARGA_RE.findall(nota):
            try:
                out.add(date(int(a), _MESES[mes.lower()], int(d)))
            except ValueError:
                continue
    return sorted(out)


def version_cdmx(texto: str) -> Optional[date]:
    """La portada de la Consejería parte "Última reforma publicada en la G.O.
    CDMX / el 8 de octubre de 2026" en dos renglones."""
    return version_ultima_reforma(" ".join(texto.split()))


CDMX = perfil_estatal(
    ambito="cdmx",
    clave="cmx",
    nombre="Constitución Política de la Ciudad de México",
    fuente="Gaceta Oficial de la Ciudad de México — Consejería Jurídica y de Servicios Legales",
    url_fuente="https://data.consejeria.cdmx.gob.mx/index.php/leyes/constitucion",
    texto_original="2017-02-05",
    header_prefixes=("CONSTITUCIÓN POLÍTICA DE LA CIUDAD",
                     "CONSEJERÍA JURÍDICA Y DE SERVICIOS LEGALES"),
    label_ordinal="plano",         # "Artículo 1" (sin ordinal)
    version_de=version_cdmx,     # portada: "Última reforma ... el DD de mes de YYYY"
    fechas_de=fechas_cdmx,
    reform_note_start_re=re.compile(_CDMX_NOTA, re.IGNORECASE),
    preprocess=separar_notas_cdmx,
    # Excepción Nivel 1: el genérico ^TRANSITORIOS$ no corta en CDMX y el art. 71
    # se traga todo el cierre (transitorios + promulgación + historial de
    # decretos). El articulado termina en el heading "ARTÍCULOS TRANSITORIOS"
    # (transitorios originales de la Constitución). Se admite también la variante
    # "TRANSITORIOS DEL DECRETO POR EL QUE SE EXPIDE..." de otras ediciones.
    transitorios_re=re.compile(
        r"^(?:ART[ÍI]CULOS?\s+TRANSITORIOS\s*$|TR[AÁ]NSITORIOS\s+DEL\s+DECRETO\b)",
        re.MULTILINE),
    # El PDF vigente trae el número de página suelto en su propia línea ("3").
    # Los ítems del articulado llevan punto ("3."), así que solo-dígitos = página.
    page_footer_re=re.compile(r"\d{1,3}$"),
)

# Ámbito → perfil. La clave es lo que se pasa por CLI con --perfil.
FUENTES: dict[str, PerfilFuente] = {
    "cpeum": CPEUM,
    "jalisco": JALISCO,
    "cdmx": CDMX,
}
# El resto de los estados: un módulo por estado en `extractor/estados/`, cada uno
# con su `PERFIL`. Así agregar o ajustar un estado no toca el de otro.
FUENTES.update(cargar_estados())


def perfil_por_nombre(nombre: str) -> PerfilFuente:
    if nombre not in FUENTES:
        disponibles = ", ".join(FUENTES)
        raise SystemExit(f"perfil desconocido: {nombre!r}. Disponibles: {disponibles}")
    return FUENTES[nombre]

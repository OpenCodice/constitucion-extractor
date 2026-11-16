"""Baja California: Constitución Política del Estado Libre y Soberano de Baja California."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..perfil import perfil_estatal

_MES3 = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5,
         "jun": 6, "jul": 7, "ago": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11,
         "dic": 12, "dec": 12}
_VERSION_RE = re.compile(r"[ÚU]ltima Reforma P\.O\..*?(\d{1,2})-([A-Za-z]{3})-(\d{4})")


def version_encabezado(texto: str) -> Optional[date]:
    """Encabezado: "Última Reforma P.O. No. 50, Sección II, 04-Sep-2026"."""
    m = _VERSION_RE.search(texto)
    if not m or m.group(2).lower() not in _MES3:
        return None
    return date(int(m.group(3)), _MES3[m.group(2).lower()], int(m.group(1)))


# El encabezado "Dirección de Procesos Parlamentarios / Coordinación de Registro
# Parlamentario" va en diagonal y pdfplumber lo entrega en pedazos de una a tres
# letras, uno por renglón, en todas las páginas. Ningún renglón del articulado
# es tan corto (los incisos llevan paréntesis o punto).
_RUIDO = (re.compile(r"^(?:[A-Za-zÁÉÍÓÚáéíóú]{1,3}|[a-zó] [a-zó]|i o y|\.)$"),)

# Anotación al margen en renglón propio: "Párrafo Reformado", "Fracción
# Adicionada", "Denominación del Capítulo Modificado".
_NOTA_RE = re.compile(
    r"^(?:P[áa]rrafo|Fracci[óo]n|Inciso|Art[íi]culo|Apartado|Base|Numeral|"
    r"Cap[íi]tulo|T[íi]tulo|Secci[óo]n|Denominaci[óo]n)(?: del Cap[íi]tulo)?"
    r" (?:Reformad|Adicionad|Derogad|Recorrid|Modificad)[oa]s?\b[^.;:]*$")


def separar_notas(texto: str) -> str:
    """Aísla cada anotación al margen con renglones en blanco: no cierra en
    punto y, sin esto, normalize la pegaba al párrafo siguiente."""
    out: list[str] = []
    for linea in texto.split("\n"):
        if _NOTA_RE.match(linea.strip()):
            out.extend(["", linea, ""])
        else:
            out.append(linea)
    return "\n".join(out)


_BASE = perfil_estatal(
    ambito="baja-california",
    clave="bcn",
    nombre="Constitución Política del Estado Libre y Soberano de Baja California",
    fuente="H. Congreso del Estado de Baja California",
    url_fuente=("https://www.congresobc.gob.mx/Documentos/ProcesoParlamentario/Leyes/"
                "TOMO_I/20260904_CONSTBC.PDF"),
    texto_original="1953-08-16",
    label_ordinal="plano",
    header_prefixes=(
        "H. Congreso del Estado de Baja California.",
        "Actualización Legislativa.",
        "Última Reforma P.O. No.",
    ),
    page_footer_re=re.compile(
        r"^Constitución Política del Estado Libre y Soberano de Baja California\. Página \d+$"),
    # El articulado cierra en "TRANSITORIOS:" (con dos puntos).
    transitorios_re=re.compile(r"^[ \t]*TRANSITORIOS?:?[ \t]*$", re.MULTILINE),
    version_de=version_encabezado,
    preprocess=separar_notas,
)

PERFIL = replace(_BASE, ruido_res=_RUIDO)

_INDICE = "https://www.congresobc.gob.mx/TrabajoLegislativo/Leyes"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
PATRON = re.compile(r'href="\.\./(Documentos/ProcesoParlamentario/Leyes/TOMO_I/(\d{8})_CONSTBC\.PDF)"')
_OCULTO_RE = re.compile(r'<input[^>]*name="(__[A-Z]+)"[^>]*value="([^"]*)"')


def campos_ocultos(html: str) -> dict[str, str]:
    """__VIEWSTATE y compañía del formulario ASP.NET."""
    return dict(_OCULTO_RE.findall(html))


def elegir_pdf(html: str) -> str:
    """URL del PDF de la Constitución con la fecha (AAAAMMDD) más reciente."""
    ms = PATRON.findall(html)
    if not ms:
        raise SystemExit(f"no se encontró el PDF de la Constitución en {_INDICE}")
    return "https://www.congresobc.gob.mx/" + max(ms, key=lambda m: m[1])[0]


def resolver() -> str:
    """El listado muestra por defecto las leyes vigentes; la Constitución solo
    aparece tras el postback que elige el grupo 4 del desplegable."""
    with urlopen(Request(_INDICE, headers={"User-Agent": _UA}), timeout=60) as r:
        html = r.read().decode("utf-8", errors="replace")
    datos = campos_ocultos(html)
    datos.update({"__EVENTTARGET": "ctl00$MainContent$ddl_legislatura",
                  "__EVENTARGUMENT": "", "ctl00$MainContent$ddl_legislatura": "4"})
    req = Request(_INDICE, data=urlencode(datos).encode(), headers={"User-Agent": _UA})
    with urlopen(req, timeout=60) as r:
        return elegir_pdf(r.read().decode("utf-8", errors="replace"))


RESOLVER = {"tipo": "funcion", "funcion": resolver}

LISTO = True

"""Guanajuato: Constitución Política del Estado Libre y Soberano de Guanajuato."""
from __future__ import annotations

import re
from datetime import date
from typing import Callable, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ..parse import ENCABEZADO_RE
from ..perfil import perfil_estatal

# Las notas "(REFORMADO, P.O. 13 DE NOVIEMBRE DE 2015)" van en renglón propio
# ANTES del párrafo que anotan; a veces se parten en dos renglones.
_NOTA_RE = re.compile(
    r"^\((?:[A-ZÁÉÍÓÚÑ]+\s+){0,2}(?:REFORMAD|ADICIONAD|DEROGAD|RECORRID|DECRETO|FE DE|F\. DE E)")
# Una nota cierra en el año; si el paréntesis no cierra ahí, sigue en el renglón siguiente.
_NOTA_CIERRA_RE = re.compile(r"\d{4}\.?\)?\s*$")
_MAX_RENGLONES_NOTA = 4
_ARTICULO_RE = re.compile(r"^(?:Art[íi]culo|ART[ÍI]CULOS?)\s+\d")


def separar_notas(texto: str) -> str:
    """Aísla cada nota de reforma del cuerpo con renglones en blanco: sin eso,
    la nota se pega al párrafo que sigue (termina en ")", no en punto). Dentro
    de un bloque de encabezado (Título/Capítulo/Sección + denominación) no se
    agregan: el parser solo reconoce bloques cortos."""
    lineas = texto.split("\n")
    out: list[str] = []
    en_encabezado = False
    i = 0
    while i < len(lineas):
        s = lineas[i].strip()
        if ENCABEZADO_RE.match(s):
            en_encabezado = True
        elif _ARTICULO_RE.match(s):
            en_encabezado = False
        if not _NOTA_RE.match(s):
            out.append(lineas[i])
            i += 1
            continue
        j, nota = i, lineas[i]
        while (nota.count("(") > nota.count(")") and not _NOTA_CIERRA_RE.search(nota)
               and j + 1 < len(lineas) and j - i < _MAX_RENGLONES_NOTA):
            j += 1
            nota += lineas[j]
        # Una nota partida en renglones queda en uno solo (el normalizador cortaría
        # en "[N." de "[N. DE E. ...]").
        nota = " ".join(x.strip() for x in lineas[i:j + 1])
        out += [nota] if en_encabezado else ["", nota, ""]
        i = j + 1
    return "\n".join(out)


# Encabezado de cada página: "... Reforma: P.O. Número 154; Segunda Parte; Decreto:204; 04-08-2026".
_VERSION_RE = re.compile(r"Reforma:[^\n]*?(\d{2})-(\d{2})-(\d{4})\s*$", re.MULTILINE)


def version_encabezado(texto: str) -> Optional[date]:
    m = _VERSION_RE.search(texto)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


PERFIL = perfil_estatal(
    ambito="guanajuato",
    clave="gua",
    nombre="Constitución Política del Estado Libre y Soberano de Guanajuato",
    fuente="Periódico Oficial del Gobierno del Estado de Guanajuato — H. Congreso del Estado de Guanajuato",
    url_fuente=("https://congreso-gto.s3.amazonaws.com/uploads/reforma/pdf/3731/"
                "CPELYSG_REF_04Agosto2026.pdf"),
    texto_original="1917-10-18",
    header_prefixes=(
        "Constitución Política del Estado Libre y Soberano de Guanajuato",
        "H. CONGRESO DEL ESTADO DE GUANAJUATO Expidió:",
        "Secretaría General Publicada:",
        "Instituto de Investigaciones Legislativas Reforma:"),
    label_ordinal="plano",
    page_footer_re=re.compile(r"Página \d+ de \d+$"),
    # El articulado cierra en "Artículos transitorios." (con punto).
    transitorios_re=re.compile(
        r"^[ \t]*(?:Art[íi]culos?\s+Transitorios?|TRANSITORIOS?)\.?[ \t]*$",
        re.MULTILINE | re.IGNORECASE),
    version_de=version_encabezado,
    preprocess=separar_notas,
    notas_previas=_NOTA_RE,
)

_BUCKET = "https://congreso-gto.s3.amazonaws.com/"
_PREFIJO = "uploads/reforma/pdf/"
# congresogto.gob.mx no responde fuera de México (tampoco desde GitHub Actions),
# pero su bucket S3, donde vive el texto consolidado de cada reforma
# (uploads/reforma/pdf/<id>/<nombre>.pdf), se puede listar. El id crece con cada
# reforma de cualquier ley y en una carpeta puede haber varias subidas.
_CLAVE_RE = re.compile(r"^uploads/reforma/pdf/(\d+)/([^/]+\.pdf)$")
# Los nombres de la Constitución: CPELYSG_REF_04Agosto2026, CPG_REF_27Mayo2026
# (CPEG_ es el Código Penal). Otras subidas solo llevan un UUID.
_NOMBRE_RE = re.compile(r"^(?:CPELYSG|CPG)_")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$")
# Un PDF con nombre UUID se reconoce por su título de documento (Word lo guarda
# sin comprimir en el diccionario Info y en el XMP): "CPG".
_TITULO_RE = re.compile(rb"/Title\s*\((?:CPELYSG|CPG)\)|<dc:title>.{0,80}?>(?:CPELYSG|CPG)<", re.DOTALL)
# Texto vigente al dar de alta el estado (REF 04-08-2026); nunca se busca más atrás.
_ID_MINIMO = 3731
_MAX_DESCARGAS = 30
_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def _get(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": _UA}), timeout=60) as r:
        return r.read()


def objetos_de_listado(xml: bytes) -> tuple[list[tuple[str, str]], bool]:
    """(clave, fecha de modificación) de una página de ListObjects y si hay más."""
    raiz = ElementTree.fromstring(xml)
    objetos = [(c.findtext(f"{_NS}Key"), c.findtext(f"{_NS}LastModified"))
               for c in raiz.iter(f"{_NS}Contents")]
    return objetos, raiz.findtext(f"{_NS}IsTruncated") == "true"


def listar_bucket() -> list[tuple[str, str]]:
    objetos: list[tuple[str, str]] = []
    marcador = ""
    while True:
        pagina, mas = objetos_de_listado(_get(
            f"{_BUCKET}?prefix={quote(_PREFIJO)}&marker={quote(marcador)}"))
        objetos += pagina
        if not mas or not pagina:
            return objetos
        marcador = pagina[-1][0]


def elegir_del_bucket(objetos: list[tuple[str, str]],
                      descargar: Callable[[str], bytes]) -> str:
    """URL del texto vigente: de la reforma más reciente a la más vieja (y, en una
    carpeta, de la subida más reciente a la más vieja), el primer PDF que sea la
    Constitución por su nombre o, si el nombre es un UUID, por su título."""
    candidatos = []
    for clave, modificado in objetos:
        m = _CLAVE_RE.match(clave or "")
        if m and int(m.group(1)) >= _ID_MINIMO:
            candidatos.append((int(m.group(1)), modificado or "", m.group(2), clave))
    descargas = 0
    for _, _, nombre, clave in sorted(candidatos, reverse=True):
        url = _BUCKET + quote(clave)
        if _NOMBRE_RE.match(nombre):
            return url
        if _UUID_RE.match(nombre):
            descargas += 1
            if descargas > _MAX_DESCARGAS:
                break
            if _TITULO_RE.search(descargar(url)):
                return url
    raise SystemExit(f"no se encontró el PDF de la Constitución en {_BUCKET}{_PREFIJO}")


def resolver() -> str:
    return elegir_del_bucket(listar_bucket(), _get)


RESOLVER = {"tipo": "funcion", "funcion": resolver}

LISTO = True

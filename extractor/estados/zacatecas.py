"""Zacatecas: Constitución Política del Estado Libre y Soberano de Zacatecas."""
from __future__ import annotations

import re
from dataclasses import replace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ..perfil import perfil_estatal, version_ultima_reforma

# Todo encabezado de artículo cierra en punto ("Artículo 1°.", "Artículo 34 Bis.");
# sin exigirlo, la cita "Artículo 130 de la Constitución..." del art. 118, partida
# al inicio de renglón, abría un artículo 130 y se comía del 119 al 129.
ARTICULO_RE = re.compile(
    r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*[oº°]?\s*((?i:Bis|Ter))?\s*\.[-–—]?(?:\s|$)")

_ORDINAL = (r"(?:[IVXLC]+|PRIMER[OA]|SEGUND[OA]|TERCER[OA]|CUART[OA]|QUINT[OA]|"
            r"SEXT[OA]|S[ÉE]PTIM[OA]|OCTAV[OA]|NOVEN[OA]|D[ÉE]CIM[OA]|[ÚU]NIC[OA])")
_ENCABEZADO_RE = re.compile(
    r"^(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+" + _ORDINAL + r"(?:\s+BIS)?$")

# Nota de reforma en renglón propio: "Párrafo reformado POG 8 de abril de 2026
# (Decreto 324)". Las que no caben siguen en el renglón de abajo, que empieza con
# la fecha ("23 de mayo de 2020 (Decreto 390)") o con "y …"/"derogado …".
_NOTA_RE = re.compile(
    r"^(?:P[áa]rrafo|Fracci[óo]n|Inciso|Art[íi]culo|Proemio|Denominaci[óo]n|"
    r"Cap[íi]tulo|Apartado|T[íi]tulo|Numeral|Secci[óo]n|Se hace|Se reforma)\b"
    r".*(?:\bPOG\b|\(Decreto|Fe de Erratas)")
_NOTA_SIGUE_RE = re.compile(r"^(?:\d{1,3}\)|\d{1,2} de |y |derogad).*(?:\(Decreto|Erratas)")
_DENOMINACION_RE = re.compile(r"^[^a-záéíóúñ]+$")
_MAX_BLOQUE = 20


def _es_nota(s: str, en_nota: bool) -> bool:
    return bool(_NOTA_RE.match(s) or (en_nota and _NOTA_SIGUE_RE.match(s)))


def _compactar_encabezados(lineas: list[str]) -> list[str]:
    """Deja solo los renglones "TÍTULO II" / "CAPÍTULO ÚNICO" de una cadena de
    encabezados que desemboca en un artículo. El parser descarta la denominación
    y su nota solo si el artículo llega en pocas líneas; aquí se apilan hasta
    tres encabezados con su denominación y su nota, y sin compactar ese bloque
    se pegaba al final del artículo anterior."""
    out: list[str] = []
    i = 0
    while i < len(lineas):
        if not _ENCABEZADO_RE.match(lineas[i].strip()):
            out.append(lineas[i])
            i += 1
            continue
        j, en_nota, cabezas = i, False, []
        while j < len(lineas) and j - i <= _MAX_BLOQUE:
            s = lineas[j].strip()
            if ARTICULO_RE.match(s):
                break
            if _ENCABEZADO_RE.match(s):
                cabezas.append(lineas[j])
                en_nota = False
            elif _es_nota(s, en_nota):
                en_nota = True
            elif not s or _DENOMINACION_RE.match(s):
                en_nota = False
            else:
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
    out: list[str] = []
    en_nota = False
    for linea in _compactar_encabezados(texto.split("\n")):
        s = linea.strip()
        if _es_nota(s, en_nota):
            if not en_nota:
                out.append("")
            out.append(linea)
            en_nota = True
            continue
        if en_nota:
            out.append("")
        en_nota = False
        out.append(linea)
    return "\n".join(out)


_BASE = perfil_estatal(
    ambito="zacatecas",
    clave="zac",
    nombre="Constitución Política del Estado Libre y Soberano de Zacatecas",
    fuente="Poder Legislativo del Estado de Zacatecas (Congreso del Estado, LXV Legislatura)",
    url_fuente="https://www.congresozac.gob.mx/65/ley&cual=333&tipo=pdf",
    texto_original="1998-07-11",
    label_ordinal="plano",         # "Artículo 1°." pero "Artículo 10." sin ordinal
    page_footer_re=re.compile(r"^Página \d+ de \d+$"),
    version_de=version_ultima_reforma,
    preprocess=preparar,
)

PERFIL = replace(
    _BASE,
    article_re=ARTICULO_RE,
    # Títulos en romano ("TÍTULO II") y capítulos en ordinal ("CAPÍTULO ÚNICO").
    titulo_re=re.compile(r"^T[ÍI]TULO\s+" + _ORDINAL + r"$", re.IGNORECASE),
    capitulo_re=re.compile(r"^CAP[ÍI]TULO\s+" + _ORDINAL + r"(\s+BIS)?$", re.IGNORECASE),
)

# La ruta lleva el número de legislatura (/65/ = LXV, 2024-2027) y cambia con
# cada legislatura; las que aún no existen responden 404 o una página HTML.
URL_LEGISLATURA = "https://www.congresozac.gob.mx/{}/ley&cual=333&tipo=pdf"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def resolver(legislaturas=range(68, 64, -1)) -> str:
    """URL de la legislatura más reciente que sirve el PDF."""
    for n in legislaturas:
        url = URL_LEGISLATURA.format(n)
        try:
            with urlopen(Request(url, headers={"User-Agent": _UA}), timeout=60) as r:
                if r.read(5) == b"%PDF-":
                    return url
        except HTTPError:
            continue
    raise SystemExit("ninguna legislatura de congresozac.gob.mx sirve el PDF de la Constitución")


RESOLVER = {"tipo": "funcion", "funcion": resolver}

LISTO = True

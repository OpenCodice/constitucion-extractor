"""Constitución Política del Estado de Sinaloa."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

URL = "https://gaceta.congresosinaloa.gob.mx:3001/pdfs/leyes/Ley_9.pdf"

# Nota al pie del título (pág. 2): no es texto de ningún artículo.
_NOTA_TITULO_RE = re.compile(
    r"^\* Constitución Política del Estado de Sinaloa\. Expedida.*?de 1922\.\n", re.M | re.S)
# Abreviaturas de las notas de reforma al final del renglón ("(Ref.", "No.");
# sin unirlas, el punto se lee como fin de párrafo y la nota queda partida.
_ABREV_FINAL_RE = re.compile(r"(\((?:Ref|Adic|Der)\.|\bNo\.|\bP\.O\.|\bDec\.)\n")
# Una nota "(Ref. … de 2026.)" cierra su párrafo aunque no termine en punto.
_CIERRE_NOTA_RE = re.compile(r"\.\)\n")
# Un renglón que empieza con el año que cierra una nota ("2026.)") parece un
# numeral "N." y abriría párrafo propio; igual "artículo\n138.".
_ANIO_PARTIDO_RE = re.compile(r"\n(?=\d{4}\.?\)|\d{4}\)\.)|(?<=\b[Aa]rt[íi]culo)\n(?=\d)")


def _preprocess(texto: str) -> str:
    texto = _NOTA_TITULO_RE.sub("", texto, count=1)
    texto = _ABREV_FINAL_RE.sub(r"\1 ", texto)
    texto = _ANIO_PARTIDO_RE.sub(" ", texto)
    return _CIERRE_NOTA_RE.sub(".)\n\n", texto)


PERFIL = replace(
    perfil_estatal(
        ambito="sinaloa",
        clave="sin",
        nombre="Constitución Política del Estado de Sinaloa",
        fuente="Periódico Oficial «El Estado de Sinaloa» — H. Congreso del Estado de Sinaloa",
        url_fuente=URL,
        texto_original="1922-06-22",
        label_ordinal="plano",       # el PDF usa "1º" hasta el 9 y "10." después
        version_de=version_ultima_reforma,
        # Las reformas posteriores llevan su propio "TRANSITORIOS DE LAS REFORMAS:".
        transitorios_re=re.compile(r"^[ \t]*TRANSITORIOS:[ \t]*$", re.MULTILINE),
        # El número de página va suelto al pie; los incisos del texto nunca son solo dígitos.
        page_footer_re=re.compile(r"\d{1,3}$"),
        preprocess=_preprocess,
    ),
    # Encabezados abreviados ("Art. 4º Bis A.", "Art. 121.Los"); "Artículo N" es cita.
    article_re=re.compile(
        r"^Art\.\s+(\d+)\s*[oº°]?\.?\s*(Bis(?: [A-Z])?|Ter)?\.?-?(?:\s|$|(?=[A-ZÁÉÍÓÚ]))"),
    article_strip_re=re.compile(
        r"^Art\.\s+\d+\s*[oº°]?\.?\s*(?:Bis(?: [A-Z])?|Ter)?\.?-?\s*"),
)

RESOLVER = {"tipo": "directo", "url": URL}

LISTO = True

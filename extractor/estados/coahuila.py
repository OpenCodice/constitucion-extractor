"""Coahuila: Constitución Política del Estado de Coahuila de Zaragoza."""
from __future__ import annotations

import re
from dataclasses import replace

from ..parse import ENCABEZADO_RE
from ..perfil import perfil_estatal, version_ultima_reforma

# Las notas "(REFORMADO, P.O. 13 DE OCTUBRE DE 2001)" van en renglón propio
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


# El Título Séptimo subdivide la Sección III en "APARTADO PRIMERO." + denominación,
# que el parser no reconoce como encabezado y dejaría dentro del artículo anterior.
_APARTADO_RE = re.compile(r"^APARTADO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO)\.?$")
_MAX_RENGLONES_APARTADO = 6


def quitar_apartados(texto: str) -> str:
    """Quita el bloque "APARTADO ..." + denominación que precede a un artículo,
    con la nota que lo antecede: es estructura, no texto de ningún artículo (como
    los Capítulos), y la nota se tomaría como del artículo siguiente."""
    lineas = texto.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lineas):
        if _APARTADO_RE.match(lineas[i].strip()):
            fin = next((j for j in range(i + 1, min(i + 1 + _MAX_RENGLONES_APARTADO, len(lineas)))
                        if _ARTICULO_RE.match(lineas[j].strip())), None)
            if fin is not None:
                while out and _NOTA_RE.match(out[-1].strip()):
                    out.pop()
                i = fin
                continue
        out.append(lineas[i])
        i += 1
    return "\n".join(out)


def preprocesar(texto: str) -> str:
    return separar_notas(quitar_apartados(texto))


_BASE = perfil_estatal(
    ambito="coahuila",
    clave="coa",
    nombre="Constitución Política del Estado de Coahuila de Zaragoza",
    fuente="Periódico Oficial del Estado de Coahuila de Zaragoza — Congreso del Estado de Coahuila de Zaragoza",
    url_fuente="https://www.congresocoahuila.gob.mx/transparencia/03/Leyes_Coahuila/coa01.pdf",
    texto_original="1918-02-19",
    label_ordinal="masc",
    # El número de página va suelto en su renglón; ningún renglón legal es solo un número.
    page_footer_re=re.compile(r"\d{1,3}$"),
    version_de=version_ultima_reforma,
    preprocess=preprocesar,
    notas_previas=_NOTA_RE,
)

# Artículos con letra tras guion ("Artículo 7º- A.", "Artículo 158-Ñ.") además de
# Bis; el PDF escribe una vez "ARTÍCULOS 88." por errata.
_ART = (r"^(?:Art[íi]culo|ART[ÍI]CULOS?)\s+(\d+)\s*[oº°]?"
        r"(?:\s*-\s*(?=[A-ZÑ]\.)|\s+(?=(?i:Bis|Ter)\b))?")
PERFIL = replace(
    _BASE,
    article_re=re.compile(_ART + r"((?i:Bis|Ter)|[A-ZÑ](?=\.))?\.?-?(?:\s|$)"),
    article_strip_re=re.compile(_ART + r"(?:(?i:Bis|Ter)|[A-ZÑ](?=\.))?\.?-?\s*"),
)

RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

LISTO = True

"""Constitución Política del Estado Libre y Soberano de Guerrero."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Optional

from ..perfil import _MESES, perfil_estatal

_URL = "https://congresogro.gob.mx/legislacion/CONSTITUCION-GUERRERO-15-06-2022.pdf"

# Sufijos latinos hasta Octies ("Artículo 160 Octies") y encabezados pegados al
# texto ("Artículo 45.-El Congreso..."): el regex genérico solo admite Bis/Ter
# seguidos de espacio y los fundía con el artículo anterior.
_SUFIJOS = r"(?i:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)"
_ENCABEZADO = r"^(?:Art[íi]culo|ART[ÍI]CULO)\s+(\d+)\s*(?:[oº°]\.?)?\s*(" + _SUFIJOS + r")?"
_CIERRE = r"(?:\s*\.\s*[-–—]?|\s*[-–—])?(?:\s|$|(?<=[.\-–—]))"

_ARTICULO_RE = re.compile(r"^\s*(?:Art[íi]culo|ART[ÍI]CULO)\s+\d+")
_ESTRUCTURA_RE = re.compile(
    r"^\s*(?:T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|APARTADO|Derogado\s+CAP[ÍI]TULO)\b")
_NOTA = r"\((?:REFORMAD|ADICIONAD|DEROGAD|RECORRID)"
_NOTA_RE = re.compile(r"^\s*" + _NOTA)
_DECRETO_RE = re.compile(r"^\s*(?:\(?DECRETO\s+(?:No\.\s*)?\d+\)?|D-\s*\d+)\s*$")
_APARTADO_RE = re.compile(r"^\s*APARTADO\s+\S+\s*$")
_DEROGADO_CAP_RE = re.compile(r"^\s*Derogado\s+CAP[ÍI]TULO\b")
# La nota de un párrafo o fracción derogados ocupa el lugar del texto que ya no
# está: al final de su artículo, aunque le siga el encabezado del siguiente
# ("(DEROGADO ULTIMO PARRAFO, …)" + "ARTÍCULO 19.-"). No es nota previa.
_NOTAS_PREVIAS_RE = re.compile(
    r"^\s*(?!\((?=[^)]*DEROGAD)[^)]*(?:P[ÁA]RRAFO|FRACC|INCISO))" + _NOTA + "|" + _DECRETO_RE.pattern)


def _fin_nota(lines: list[str], i: int) -> int:
    """Índice siguiente a la nota que empieza en `i` (envuelta en hasta 3
    renglones, más la línea suelta "DECRETO 828" que a veces la acompaña)."""
    j = i + 1
    while (j < len(lines) and j - i < 3
           and " ".join(lines[i:j]).count("(") > " ".join(lines[i:j]).count(")")
           and lines[j].strip() and not re.search(r"[a-záéíóúñ]", lines[j])
           and not _ARTICULO_RE.match(lines[j])):
        j += 1
    while j < len(lines) and _DECRETO_RE.match(lines[j]):
        j += 1
    return j


def _preprocess(texto: str) -> str:
    """Prepara lo que el PDF intercala ENTRE artículos. En esta edición las
    notas de reforma preceden al elemento que anotan:

    - Las que preceden a un artículo (también las que quedan entre la
      denominación de un encabezado y el artículo) quedan cada una en un renglón,
      con su "DECRETO 828" suelto, para que `notas_previas` las lleve al
      artículo que anotan.
    - Las que preceden a un título, capítulo o sección anotan la estructura y se
      quitan: el parser las pegaría al artículo anterior. No van al artículo
      siguiente (`notas_previas_encabezado`) porque muchas cierran en "DECRETO
      828" y `cobertura` solo tolera la denominación entre notas que cierran en
      paréntesis.
    - Las seguidas de texto (párrafo, fracción) no se tocan: anotan texto del
      mismo artículo.
    - Quita los encabezados "APARTADO ..." y "Derogado CAPÍTULO ...", que el
      parser no reconoce como estructura y pegaría al artículo anterior."""
    lines = texto.splitlines()
    borrar: set[int] = set()
    unidas: dict[int, str] = {}
    i = 0
    while i < len(lines):
        if _NOTA_RE.match(lines[i]):
            # Junta notas consecutivas y mira qué viene después de todas ellas.
            j, notas = i, []
            while j < len(lines) and (_NOTA_RE.match(lines[j]) or _DECRETO_RE.match(lines[j])
                                      or not lines[j].strip()):
                fin = _fin_nota(lines, j) if _NOTA_RE.match(lines[j]) else j + 1
                notas.append((j, fin))
                j = fin
            if j < len(lines) and _ARTICULO_RE.match(lines[j]):
                for a, b in notas:
                    if lines[a].strip():
                        # En un solo renglón y párrafo propio: el normalizador no la pega a
                        # la nota o al texto vecinos.
                        unidas[a] = " ".join(ln.strip() for ln in lines[a:b]) + "\n"
                        borrar.update(range(a + 1, b))
            elif j < len(lines) and _ESTRUCTURA_RE.match(lines[j]):
                borrar.update(range(i, j))
            i = max(j, i + 1)
            continue
        if _APARTADO_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not re.search(r"[a-záéíóúñ]", lines[j]) \
                    and not _NOTA_RE.match(lines[j]) and not _ARTICULO_RE.match(lines[j]):
                j += 1
            borrar.update(range(i, j))
            i = j
            continue
        if _DEROGADO_CAP_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and j - i <= 6 and not _ARTICULO_RE.match(lines[j]):
                j += 1
            if j < len(lines) and _ARTICULO_RE.match(lines[j]):
                borrar.update(range(i, j))
            i = j
            continue
        i += 1
    return "\n".join(unidas.get(k, ln) for k, ln in enumerate(lines) if k not in borrar)


def _version(texto: str) -> Optional[date]:
    """Portada: 'ÚLTIMAS MODIFICACIONES PUBLICADAS ... DE FECHA MARTES 21 DE ABRIL DE 2026'."""
    m = re.search(r"[ÚU]LTIMAS?\s+MODIFICACIONES.*?(\d{1,2})\s+DE\s+(" + "|".join(_MESES) +
                  r")\s+DE\s+(\d{4})", texto, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return date(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))


PERFIL = replace(
    perfil_estatal(
        ambito="guerrero",
        clave="gro",
        nombre="Constitución Política del Estado Libre y Soberano de Guerrero",
        fuente="Periódico Oficial del Gobierno del Estado de Guerrero — H. Congreso del Estado de Guerrero",
        url_fuente=_URL,
        texto_original="1917-11-03",
        label_ordinal="plano",
        # Pie de cada página: "H. Congreso del Estado de Guerrero", "S.S.P./D.P.L." y el número.
        header_prefixes=("H. Congreso del Estado de Guerrero", "S.S.P./D.P.L."),
        page_footer_re=re.compile(r"\d{1,3}$"),
        # El articulado cierra con "TRANSITORIOS." (con punto), que el genérico no reconoce.
        transitorios_re=re.compile(r"^[ \t]*TRANSITORIOS\.?[ \t]*$", re.MULTILINE),
        version_de=_version,
        preprocess=_preprocess,
        notas_previas=_NOTAS_PREVIAS_RE,
    ),
    article_re=re.compile(_ENCABEZADO + _CIERRE),
    article_strip_re=re.compile(_ENCABEZADO + _CIERRE + r"\s*"),
)

RESOLVER = {"tipo": "directo", "url": _URL}

LISTO = True

"""Constitución Política del Estado Libre y Soberano de Michoacán de Ocampo."""
from __future__ import annotations

import re
from dataclasses import replace

from ..perfil import perfil_estatal, version_ultima_reforma

_SUFIJO = r"(?i:bis|ter|qu[aá]ter|quinquies)|[A-F](?=\.)"

_NOTA = r"\((?:REFORMAD|ADICIONAD|DEROGAD|REUBICAD|F\. DE E)"
# Nota partida en dos renglones ("(ADICIONADO CON … P.O.\n23 DE MAYO DE 2006)",
# "(REFORMADO, …) (F. DE E., P.O. 26 DE\nSEPTIEMBRE DE 2006)").
_NOTA_PARTIDA_RE = re.compile(
    r"^(" + _NOTA + r"[^()\n]*(?:\)\s*\([^()\n]*)*)\n([^()\n]*\))$", re.MULTILINE)
# Nota en renglón propio: se deja como párrafo propio para que no se pegue al
# texto que anota.
_NOTA_ANTES_DE_TEXTO_RE = re.compile(r"^(" + _NOTA + r"[^)\n]*\))\n", re.MULTILINE)


def _preprocess(texto: str) -> str:
    texto = _NOTA_PARTIDA_RE.sub(r"\1 \2", texto)
    return _NOTA_ANTES_DE_TEXTO_RE.sub(r"\1\n\n", texto)


PERFIL = replace(
    perfil_estatal(
        ambito="michoacan",
        clave="mic",
        nombre="Constitución Política del Estado Libre y Soberano de Michoacán de Ocampo",
        fuente="Periódico Oficial del Gobierno del Estado de Michoacán — H. Congreso del Estado de Michoacán de Ocampo",
        url_fuente=("https://congresomich.site/wp-content/uploads/2026/04/"
                    "20251202_CONSTITUCION-POLITI_122754923.pdf"),
        texto_original="1918-02-07",
        label_ordinal="plano",
        version_de=version_ultima_reforma,
        # Pie de cada página: fecha y hora de impresión más el número de página.
        page_footer_re=re.compile(r"\d{2}/\d{2}/\d{4} \d{1,2}:\d{2} [ap]\. ?m\. \d{1,3}$"),
        # Los transitorios originales abren con "Artículos Transitorios." (con punto).
        transitorios_re=re.compile(r"^[ \t]*Art[íi]culos\s+Transitorios\.?[ \t]*$", re.MULTILINE),
        preprocess=_preprocess,
        # Cada nota "(REFORMADO, P.O. …)" precede a lo que anota, también las de
        # los Títulos y Capítulos: van con el artículo siguiente.
        notas_previas=re.compile(_NOTA),
        notas_previas_encabezado=True,
    ),
    # El encabezado cierra en "." o "-": "Artículo 1º.-", "Artículo 2° bis.-",
    # "Artículo 3°.", y una vez "Artículo. 43.-".
    article_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\.?\s+(\d+)\s*[oº°]?\s*(" + _SUFIJO + r")?\s*(?:\.\s*-?|-)"),
    article_strip_re=re.compile(
        r"^(?:Art[íi]culo|ART[ÍI]CULO)\.?\s+\d+\s*[oº°]?\s*(?:" + _SUFIJO + r")?\s*(?:\.\s*-?|-)\s*"),
)

RESOLVER = {
    "tipo": "indice",
    # "Normatividad Aplicable" enlaza el texto vigente (fecha AAAAMMDD en el nombre)
    # junto con los decretos de reforma sueltos y la constitución federal.
    "index_url": "https://congresomich.site/normatividad-aplicable/",
    "encoding": "utf-8",
    "patron": re.compile(
        r'Constitución Política del Estado de Michoacán de Ocampo</h6>.*?Texto vigente:.*?'
        r'href="(https://congresomich\.site/wp-content/uploads/[^"]+\.pdf)"', re.S),
    "orden": "unico",
}

LISTO = True

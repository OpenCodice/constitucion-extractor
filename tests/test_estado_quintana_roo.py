"""Perfil y resolver de Quintana Roo, sin PDF."""
from __future__ import annotations

from datetime import date

from extractor.estados.quintana_roo import PERFIL, RESOLVER
from extractor.parse import parse_text
from scripts.resolver_pdf import elegir

_BASE = "https://documentos.congresoqroo.gob.mx/leyes/"
# Fragmento real: versiones de 2018 con fecha DDMMAAAA, decretos sueltos y textos íntegros.
HTML = "".join(f'<a href="{_BASE}{n}">x</a>' for n in [
    "L176-XV-30072018-760.pdf",
    "L176-XVIII-20260604-CN1820260604006-Constitución.pdf",
    "L176-XVIII-20260622-CN1820260622007-Constitución-(1).pdf",
    "L176-XVIII-20260311-CN1820260311005-Constitución.pdf",
    "L176-XVIII-20250818-CN1820250818004-declaratoria.pdf",
])


def test_resolver_elige_el_texto_integro_mas_reciente():
    url = elegir(HTML, RESOLVER["patron"], RESOLVER["index_url"], RESOLVER["orden"])
    assert "20260622" in url and "Constituci%C3%B3n-%281%29.pdf" in url


def test_quita_el_indice_de_contenido():
    txt = "\n".join([
        "ÍNDICE DE CONTENIDO",
        "TITULO PRIMERO .......................................... 12",
        "Artículo 1º .............................................. 12",
        "Artículo 2º .............................................. 12",
        "Decreto por el que se promulga la Constitución.",
        "Artículo 1º.- Quintana Roo constituye un Estado Libre.",
        "Artículo reformado POE 19-03-2025",
        "Artículo 2º.- De conformidad al pacto federal.",
    ])
    arts = parse_text(txt, perfil=PERFIL)
    assert [a.number for a in arts] == [1, 2]
    assert arts[0].body.startswith("Artículo 1º.- Quintana Roo")
    assert arts[0].reform_dates == [date(2025, 3, 19)]


def test_version_de_la_portada():
    assert PERFIL.version_de("QUINTANA ROO\nUltima reforma publicada POE 22-06-2026") == date(2026, 6, 22)

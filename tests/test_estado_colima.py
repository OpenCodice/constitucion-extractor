"""Colima: encabezados de página, notas sin "de" en la fecha y títulos undécimo (sin PDF)."""
from datetime import date

from extractor.build import render_markdown
from extractor.estados.colima import PERFIL, fechas_notas
from extractor.parse import _strip_headers, parse_text

PAGINA = "\n".join([
    "Constitución Política del Estado Libre y Soberano de Colima.",
    "Dirección de Proceso Legislativo del H. Congreso del Estado de Colima",
    "En caso de no proporcionar los auxilios, las personas serán sancionadas.",
    "TÍTULO UNDÉCIMO",
    "CAPÍTULO I",
    "(REFORMADO DECRETO NO. 355, P.O. 71, SUP. 3, 04 NOVIEMBRE 2023)",
    "DE LAS RESPONSABILIDADES DE LAS PERSONAS SERVIDORAS",
    "PÚBLICAS",
    "Artículo 119",
    "(ADICIONADA DECRETO NO. 318, P.O. 51, SUPL. 11, 30 MAYO 2026",
    "Para los efectos de las responsabilidades se reputarán servidores públicos.",
    "118",
])


def test_quita_encabezado_y_numero_de_pagina():
    limpio = _strip_headers(PAGINA, PERFIL)
    assert "Dirección de Proceso" not in limpio
    assert "\n118" not in limpio


def test_titulo_undecimo_no_entra_al_cuerpo():
    texto = "Artículo 118\n" + _strip_headers(PAGINA, PERFIL)
    a118, a119 = parse_text(texto, perfil=PERFIL)
    assert "TÍTULO" not in a118.body
    assert a119.titulo == "TÍTULO UNDÉCIMO"


def test_nota_sin_parentesis_de_cierre_no_se_traga_el_parrafo():
    texto = "Artículo 118\n" + _strip_headers(PAGINA, PERFIL)
    md = render_markdown(parse_text(texto, perfil=PERFIL)[1], perfil=PERFIL)
    assert "30 MAYO 2026\n\nPara los efectos" in md


def test_fechas_de_las_notas():
    assert fechas_notas("(REFORMADA DECRETO 113, P.O. 57, 03 AGOSTO 2019)") == [date(2019, 8, 3)]
    assert fechas_notas("P.O. NÚM. 63, SUPL. 7, 04 DE JULIO DE 2026.") == [date(2026, 7, 4)]

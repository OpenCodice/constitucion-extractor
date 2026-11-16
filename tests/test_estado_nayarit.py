"""Perfil de Nayarit, sin PDF."""
from __future__ import annotations

from datetime import date

from extractor.estados.nayarit import PERFIL
from extractor.parse import _strip_headers, parse_text


def test_encabezado_de_pagina():
    pagina = "\n".join([
        "CCOONNSSTTIITTUUCCIIOONN PPOOLLIITTIICCAA DDEELL EESSTTAADDOO",
        "Poder Legislativo del Estado de Nayarit",
        "Secretaría General",
        "Secretaría General de Gobierno del Estado.",
    ])
    assert _strip_headers(pagina, PERFIL).splitlines() == [
        "Secretaría General de Gobierno del Estado."]


def test_nota_previa_va_con_su_articulo_y_corte_espaciado():
    txt = "\n".join([
        "ARTÍCULO 1.- El Estado es Libre y Soberano.",
        "CAPITULO II",
        "DEL TERRITORIO DEL ESTADO",
        "(REFORMADO, P.O. 13 DE DICIEMBRE DE 1989)",
        "ARTÍCULO 3.- El territorio del Estado:",
        "(REFORMADO, P.O. 9 DE FEBRERO DE 1930)",
        "ARTÍCULO 139.- Los Poderes del Estado.",
        "                T R A N S I T O R I O S",
        "ARTÍCULO 1o. Esta Constitución se promulgará.",
    ])
    arts = parse_text(txt, perfil=PERFIL)
    assert [a.number for a in arts] == [1, 3, 139]
    assert "1989" not in arts[0].body and "1930" not in arts[1].body
    assert "promulgará" not in arts[-1].body


def test_version_de_la_portada():
    portada = "ÚLTIMA ENMIENDA PUBLICADA EN EL PERIÓDICO OFICIAL: 6 DE\nNOVIEMBRE DE 2026."
    assert PERFIL.version_de(portada) == date(2026, 11, 6)

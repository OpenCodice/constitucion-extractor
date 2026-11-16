"""Durango: encabezado de página cambiante, sufijos Quáter/Quintus y notas (sin PDF)."""
from datetime import date

from extractor.build import render_markdown
from extractor.estados.durango import PERFIL, version_portada
from extractor.parse import _strip_headers, parse_text

PORTADA = ("CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE DURANGO\n"
           "FECHA DE ÚLTIMA REFORMA:\n"
           "DEC. 426 P.O. 44 BIS DEL 31 DE MAYO DE 2026.\n")


def test_version_de_la_portada():
    assert version_portada(PORTADA) == date(2026, 5, 31)


def test_quita_el_encabezado_de_pagina():
    assert _strip_headers(PORTADA + "Texto legal.\n90", PERFIL).strip() == "Texto legal."


def test_sufijos_y_citas():
    texto = "\n".join([
        "ARTÍCULO 163 TER.- El Comité.",
        "ARTÍCULO 163 QUÁTER.- El Consejo Coordinador.",
        "ARTÍCULO 163 QUINTUS.- El Consejo de Participación.",
        "ARTÍCULO 164.- - El día.",
        "ARTÍCULO 170 de esta Constitución no abre artículo.",
        "ARTÍCULO 165.- El órgano.",
    ])
    arts = parse_text(texto, perfil=PERFIL)
    assert [a.key for a in arts] == ["163-ter", "163-quater", "163-quintus", "164", "165"]
    assert render_markdown(arts[3], perfil=PERFIL).startswith("# Artículo 164\n\nEl día.")


def test_nota_sin_punto_no_se_pega_al_parrafo():
    texto = ("ARTÍCULO 71.- Las y los diputados son inviolables.\n"
             "REFORMADO POR DEC. 585 P.O. 11 EXT. DEL 24 DE MAYO DE 2022\n"
             "El Presidente del Congreso velará por el respeto al fuero.\n")
    md = render_markdown(parse_text(texto, perfil=PERFIL)[0], perfil=PERFIL)
    assert "DE 2022\n\nEl Presidente" in md

"""Perfil de Tlaxcala: notas de reforma en renglón propio y encabezado de página."""
from extractor.estados import tlaxcala
from extractor.parse import parse_text

P = tlaxcala.PERFIL


def test_notas_y_derogados():
    texto = ("ARTICULO 48.- Todo proyecto de Ley que fuere desechado no podrá volver a presentarse.\n"
             "ARTICULO 48-BIS.-\n"
             "(DEROGADO, P.O. 18 DE MAYO DE 2001)\n"
             "(REFORMADO, P.O. 4 DE FEBRERO DE 1982)\n"
             "ARTICULO 49.- El Gobernador deberá sancionar los proyectos.\n"
             "(ADICIONADO, P.O. 1 DE AGOSTO DE 2008)\n"
             "Segundo párrafo del 49.\n"
             "CAPITULO III (DEROGADO, P.O. 30 DE JUNIO DE 2025)\n"
             "ARTICULO 97.- (DEROGADO, P.O. 30 DE JUNIO DE 2025)\n"
             "ARTÍCULO 97 QUÁTER. La persona titular.\n")
    arts = parse_text(texto, perfil=P)
    assert [a.key for a in arts] == ["048", "048-bis", "049", "097", "097-quater"]
    assert arts[1].body.strip().endswith("(DEROGADO, P.O. 18 DE MAYO DE 2001)")
    assert "1982" not in arts[1].body
    assert "(ADICIONADO, P.O. 1 DE AGOSTO DE 2008)" in arts[2].body
    assert "CAPITULO" not in arts[2].body


def test_encabezado_de_pagina():
    for linea in ["CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE TLAXCALA Pág.",
                  "CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO DE TLAXCALA   Pág.   2", "77"]:
        assert P.page_footer_re.match(linea)

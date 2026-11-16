"""Perfil de Morelos: asterisco de "reformado" en artículos y encabezados."""
from extractor.estados import morelos
from extractor.parse import parse_text

P = morelos.PERFIL


def test_encabezados_con_asterisco_y_sufijos():
    texto = ("ARTICULO *85.- Texto del ochenta y cinco.\n"
             "CAPITULO *VII\nDE LA PROTECCION DEL AMBIENTE\n"
             "ARTICULO *85-D.- Toda persona tiene derecho.\n"
             "*CAPITULO III TER\nDEL TRIBUNAL DE DISCIPLINA JUDICIAL\n"
             "ARTÍCULO *105 TER.- El Tribunal de Disciplina Judicial.\n"
             "ARTICULO *133-bis Tienen obligación de presentar declaraciones.\n"
             "ARTÍCULO 134.- Texto.\n")
    arts = parse_text(texto, perfil=P)
    assert [a.key for a in arts] == ["085", "085-d", "105-ter", "133-bis", "134"]
    assert "CAPITULO" not in arts[0].body and "CAPITULO" not in arts[1].body
    assert not P.article_re.match("Artículo 133 de esta Constitución")


def test_version_del_encabezado():
    assert str(morelos._version("Consejería Jurídica ... Última Reforma: 27-01-2026")) == "2026-01-27"


def test_encabezado_y_pie():
    assert P.page_footer_re.match("2 de 130")
    assert "Aprobación 1930/11/20".startswith(P.header_prefixes)

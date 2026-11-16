"""Perfil del Estado de México: encabezados, transitorios espaciados y citas partidas (sin PDF)."""
from extractor.build import render_markdown
from extractor.estados import edomex
from extractor.parse import parse_text

P = edomex.PERFIL

TEXTO = "\n".join([
    "TITULO PRIMERO",
    "Del Estado de México como Entidad Política",
    "Artículo 1.- El Estado de México es parte integrante de la Federación.",
    "Artículo 19. Los recursos cuya captación y administración corresponda a las autoridades.",
    "Artículo 74.- Si la falta temporal se convierte en absoluta, se procederá como lo dispone el artículo",
    "72.",
    "Artículo 83 Bis.- La Fiscalía General de Justicia será responsable.",
    "Artículo 84.-Para ser Fiscal General de Justicia se requiere:",
    "I. Ser ciudadano del Estado;",
    "Artículo 130 bis. El Sistema Estatal Anticorrupción es la instancia de coordinación.",
    "Artículo 149.- Esta Constitución no perderá su fuerza y vigencia.",
    "T R A N S I T O R I O S",
    "PRIMERO.- Publíquese el presente decreto en la Gaceta del Gobierno.",
    "Artículo 150.- No es un artículo.",
]) + "\n"


def test_claves_y_fin_del_articulado():
    claves = [a.key for a in parse_text(TEXTO, perfil=P)]
    assert claves == ["001", "019", "074", "083-bis", "084", "130-bis", "149"]


def test_cita_partida_no_es_numeral():
    art = parse_text(TEXTO, perfil=P)[2]
    assert render_markdown(art, perfil=P).endswith("como lo dispone el artículo 72.\n")


def test_encabezado_sin_espacio_y_pie():
    art = parse_text(TEXTO, perfil=P)[4]
    assert "Para ser Fiscal General de Justicia se requiere:" in render_markdown(art, perfil=P)
    assert P.page_footer_re.match("44")
    assert "Última reforma POGG 25 de septiembre de 2026.".startswith(P.header_prefixes)
    assert edomex.RESOLVER == {"tipo": "directo", "url": P.url_fuente, "via": "mx"}

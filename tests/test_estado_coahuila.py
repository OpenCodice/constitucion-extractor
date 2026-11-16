"""Coahuila: encabezados con letra, notas antes del párrafo y apartados (sin PDF)."""
from extractor.build import render_markdown
from extractor.estados.coahuila import PERFIL, RESOLVER
from extractor.parse import parse_text

TEXTO = "\n".join([
    "Artículo 7º. Dentro del territorio del Estado, toda persona gozará de los derechos.",
    "(REFORMADO, P.O. 01 DE SEPTIEMBRE DE 2026) (DECRETO 193, ADICIONADO RECORRIÉNDOSE LAS SUBSECUENTES, P.O. 21 DE",
    "ENERO DE 2022)",
    "Las personas son iguales ante la ley.",
    "Artículo 7º- A. Toda persona tiene derecho a la vida.",
    "Artículo 7º- Ñ. Toda persona goza de los derechos.",
    "(ADICIONADO, P.O. 20 DE MARZO DE 2001)",
    "APARTADO SEGUNDO",
    "La Hacienda Municipal.",
    "(ADICIONADO, P.O. 20 DE MARZO DE 2001)",
    "Artículo 27 Bis. La renovación del Poder Judicial del Estado.",
    "ARTÍCULOS 88. Los reglamentos serán refrendados.",
    "Artículo 155. A los Municipios corresponde la hacienda.",
]) + "\n"


def test_claves_y_sufijos():
    claves = [a.key for a in parse_text(TEXTO, perfil=PERFIL)]
    assert claves == ["007", "007-a", "007-ñ", "027-bis", "088", "155"]


def test_nota_partida_queda_en_su_propio_parrafo():
    art = parse_text(TEXTO, perfil=PERFIL)[0]
    md = render_markdown(art, perfil=PERFIL)
    assert ("\n\n(REFORMADO, P.O. 01 DE SEPTIEMBRE DE 2026) (DECRETO 193, ADICIONADO "
            "RECORRIÉNDOSE LAS SUBSECUENTES, P.O. 21 DE ENERO DE 2022)\n\nLas personas") in md


def test_apartado_no_entra_al_cuerpo():
    arts = {a.key: a for a in parse_text(TEXTO, perfil=PERFIL)}
    assert "APARTADO" not in arts["007-ñ"].body
    assert "Hacienda Municipal" not in arts["007-ñ"].body


def test_letra_solo_tras_guion():
    # "Artículo 155. A los..." no es un artículo 155 A.
    assert parse_text(TEXTO, perfil=PERFIL)[-1].suffix == ""


def test_resolver_directo():
    assert RESOLVER == {"tipo": "directo", "url": PERFIL.url_fuente}

"""Numeración decimal de artículos ("Artículo 88.1"), opcional por perfil.

Un perfil la activa capturando el grupo nombrado `sub` en su `article_re`; sin
ese grupo el parser se comporta como siempre.
"""
import re
from dataclasses import replace

from extractor.build import render_markdown
from extractor.parse import Article, parse_text
from extractor.perfil import perfil_estatal

_BASE = perfil_estatal(ambito="prueba", clave="pru", nombre="Prueba", fuente="Prueba",
                       url_fuente="https://example.org", texto_original="2000-01-01",
                       label_ordinal="plano")
CON_SUB = replace(
    _BASE,
    article_re=re.compile(r"^ARTÍCULO\s+(\d+)(?:\s*((?i:Bis))|\.(?P<sub>\d{1,2})(?=\.))?\.?-?(?:\s|$)"),
    article_strip_re=re.compile(r"^ARTÍCULO\s+\d+(?:\.\d{1,2}(?=\.))?\s*(?i:Bis)?\.?-?\s*"),
)

TEXTO = ("ARTÍCULO 88.- Corresponde al Pleno del Tribunal.\n"
         "ARTÍCULO 88.1.- La Autoridad Electoral Jurisdiccional es el órgano especializado.\n"
         "ARTÍCULO 88.2.- Estará conformada por tres magistraturas.\n"
         "ARTÍCULO 89.- Otro artículo.\n")


def test_subnumeros_son_unidades_propias():
    arts = parse_text(TEXTO, perfil=CON_SUB)
    assert [a.key for a in arts] == ["088", "088-1", "088-2", "089"]
    assert [a.label for a in arts] == [
        "Artículo 88", "Artículo 88.1", "Artículo 88.2", "Artículo 89"]


def test_cuerpo_sin_el_encabezado_decimal():
    a = parse_text(TEXTO, perfil=CON_SUB)[1]
    assert render_markdown(a, perfil=CON_SUB) == (
        "# Artículo 88.1\n\nLa Autoridad Electoral Jurisdiccional es el órgano especializado.\n")


def test_sin_grupo_sub_nada_cambia():
    arts = parse_text(TEXTO.replace("88.1.-", "88.1"), perfil=_BASE)
    assert [a.key for a in arts] == ["088", "089"]
    assert all(a.subnumero == "" for a in arts)


def test_clave_y_etiqueta_con_ordinal_federal():
    a = Article(number=5, subnumero="3", label_ordinal="federal")
    assert (a.key, a.label) == ("005-3", "Artículo 5.3")
    assert Article(number=5, label_ordinal="federal").label == "Artículo 5o."

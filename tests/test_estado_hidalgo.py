"""Perfil de Hidalgo, sin PDF."""
from __future__ import annotations

from datetime import date

from extractor.estados.hidalgo import PERFIL
from extractor.parse import _strip_headers, parse_text


def test_sufijos_de_letra():
    txt = "\n".join([
        "Artículo 88.- (DEROGADO, P.O. 1 DE OCTUBRE DE 1987)",
        "Artículo 88 Bis.- (DEROGADO, P.O. 1 DE OCTUBRE DE 1987)",
        "Artículo 88a.- (DEROGADO, P.O. 1 DE OCTUBRE DE 1987)",
        "Artículo 88b.- (DEROGADO, P.O. 1 DE OCTUBRE DE 1987)",
        "Artículo 89.- Texto.",
    ])
    claves = [a.key for a in parse_text(txt, perfil=PERFIL)]
    assert claves == ["088", "088-bis", "088-a", "088-b", "089"]


def test_ordinal_no_es_sufijo():
    arts = parse_text("Artículo 1o.- Uno.\nArtículo 2o.- Dos.", perfil=PERFIL)
    assert [a.key for a in arts] == ["001", "002"]


def test_encabezado_de_pagina_sin_borrar_texto_parecido():
    pagina = "\n".join([
        "Constitución Política del Estado de Hidalgo.",
        "Instituto de Estudios Legislativos.",
        "Constitución Política del Estado de Hidalgo, otorgan a los Municipios, se ejercerá",
        "37",
    ])
    assert _strip_headers(pagina, PERFIL).splitlines() == [
        "Constitución Política del Estado de Hidalgo, otorgan a los Municipios, se ejercerá"]


def test_corta_en_transitorios_y_version():
    arts = parse_text("Artículo 159.- Último.\n      TRANSITORIOS:\nArtículo 1o.- X.", perfil=PERFIL)
    assert [a.number for a in arts] == [159]
    portada = "ÚLTIMA REFORMA PUBLICADA EN ALCANCE UNO DEL PERIÓDICO OFICIAL: 8 DE JULIO DE 2026."
    assert PERFIL.version_de(portada) == date(2026, 7, 8)

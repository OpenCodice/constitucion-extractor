"""Aguascalientes: encabezados con letra, capítulos con ordinal de una palabra (sin PDF)."""
from datetime import date

from extractor.estados.aguascalientes import PERFIL, version_encabezado
from extractor.parse import _strip_headers, parse_text

TEXTO = "\n".join([
    "Artículo 2o.- En el Estado de Aguascalientes el respeto a la dignidad humana.",
    "Artículo 2o A.- El Estado reconoce a los pueblos indígenas.",
    "Artículo 7o. A.- El Estado garantiza el derecho.",
    "Artículo 27 C de esta Constitución, constituirán créditos fiscales.",
    "Artículo 50.- Las ausencias del Secretario General de Gobierno.",
    "(ADICIONADO CON LOS ARTÍCULOS QUE LO INTEGRAN, P.O. 8 DE AGOSTO",
    "DE 2023)",
    "CAPITULO UNDECIMO A",
    "Del Tribunal de Justicia Administrativa",
    "(ADICIONADO, P.O. 8 DE AGOSTO DE 2023)",
    "Artículo 50 A.- El Tribunal de Justicia Administrativa es un órgano.",
    "Artículo 55 A. El Tribunal de Disciplina Judicial.",
    "Artículo 59 A.- Para proteger los derechos de las mujeres.",
    "Artículo 59 A (sic).- El Ministerio Público se organizará.",
]) + "\n"


def test_claves():
    claves = [a.key for a in parse_text(TEXTO, perfil=PERFIL)]
    assert claves == ["002", "002-a", "007-a", "050", "050-a", "055-a", "059-a"]


def test_cita_no_abre_articulo_y_duplicado_no_sobrescribe():
    arts = {a.key: a for a in parse_text(TEXTO, perfil=PERFIL)}
    assert "Artículo 27 C de esta" in arts["007-a"].body
    assert "El Ministerio Público" in arts["059-a"].body


def test_capitulo_de_una_palabra():
    arts = {a.key: a for a in parse_text(TEXTO, perfil=PERFIL)}
    assert "Tribunal de Justicia Administrativa" not in arts["050"].body
    assert arts["050-a"].capitulo == "CAPITULO UNDECIMO A"


def test_encabezado_de_pagina():
    pagina = ("CONSTITUCIÓN POLÍTICA DEL ESTADO DE\nAGUASCALIENTES\n"
              "Última actualización: 07/09/2026.\nTexto legal.")
    assert _strip_headers(pagina, PERFIL).strip() == "Texto legal."
    assert version_encabezado(pagina) == date(2026, 9, 7)

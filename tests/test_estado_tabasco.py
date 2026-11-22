"""Perfil de Tabasco: marginalia de reforma antes de cada artículo; resolver por índice."""
from datetime import date
import importlib.util
from pathlib import Path

from extractor.estados import tabasco
from extractor.parse import parse_text

P = tabasco.PERFIL
_MOD = Path(__file__).resolve().parent.parent / "scripts" / "resolver_pdf.py"
_spec = importlib.util.spec_from_file_location("resolver_pdf", _MOD)
resolver_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver_pdf)


def test_notas_antes_del_articulo_no_se_pegan_al_anterior():
    texto = ("Artículo 1.- El Estado de Tabasco es parte integrante de la Federación.\n"
             "(ADICIONADO 11-NOV-03)\n"
             "El Territorio del Estado es el que le pertenece.\n"
             "REFORMADO P.O. 8469 SPTO. F 4-NOV-2023\n"
             "(REFORMADO, 11-NOV.-03)\n"
             "Artículo 2.- El Estado se constituye como un Estado Social.\n"
             "Articulo 63 Quater. El Tribunal.\n")
    arts = parse_text(texto, perfil=P)
    assert [a.key for a in arts] == ["001", "002", "063-quater"]
    assert "(ADICIONADO 11-NOV-03)" in arts[0].body
    assert "4-NOV-2023" not in arts[0].body


def test_resolver_ignora_hosting_viejo():
    r = tabasco.RESOLVER
    html = ('<a href="https://congresotabasco.gob.mx/wp/wp-content/uploads/2024/01/'
            'Constitucion-Politica-del-Estado-de-Tabasco1.pdf">viejo</a>'
            '<a href="https://congresotabasco.gob.mx/wp-content/uploads/2026/08/'
            'Constitucion-Politica-del-Estado-de-Tabasco1.pdf">Descargar</a>')
    assert resolver_pdf.elegir(html, r["patron"], r["index_url"], r["orden"]) == (
        "https://congresotabasco.gob.mx/wp-content/uploads/2026/08/"
        "Constitucion-Politica-del-Estado-de-Tabasco1.pdf")


def test_version_de_la_portada_partida_en_renglones():
    portada = ("Constitución Política del Estado Libre y Soberano de Tabasco\n"
               "Última reforma mediante Decreto 283, publicado en el Periódico Oficial del Estado número 8762\n"
               "Suplemento “L” de fecha 26 de agosto de 2026, mediante el cual se reforman los artículos 8 ter,\n"
               "Reforma mediante Decreto 231, publicado en el Periódico Oficial del Estado número 8701 "
               "Suplemento “L” de fecha 24 de enero de 2026\n")
    assert P.version_de(portada) == date(2026, 8, 26)
    assert P.version_paginas == 1

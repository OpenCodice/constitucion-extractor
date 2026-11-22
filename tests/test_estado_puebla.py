"""Perfil de Puebla: llamadas de nota en superíndice y notas al pie de página."""
from datetime import date
import importlib.util
from pathlib import Path

from extractor.estados import puebla

P = puebla.PERFIL
_MOD = Path(__file__).resolve().parent.parent / "scripts" / "resolver_pdf.py"
_spec = importlib.util.spec_from_file_location("resolver_pdf", _MOD)
resolver_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver_pdf)


def test_filtro_quita_superindices():
    assert not P.filtro_char({"size": 8.04})       # llamada "386" pegada a "Artículo 142"
    assert not P.filtro_char({"size": 6.48})
    assert P.filtro_char({"size": 12.0}) and P.filtro_char({"size": 9.96})


def test_pie_de_pagina():
    for l in ["23", "Párrafo reformado el 5/jun/2025.", "13/abr/2009.",
              "Artículo reformado el 17/feb/1995, el 14/ feb/1997, el 22/sep/2000 y el",
              "Párrafo adicionado el 26/jun//2018."]:
        assert P.page_footer_re.match(l), l
    for l in ["Artículo 142", "El pueblo ejerce su soberanía por medio de los Poderes del Estado, en",
              "a) Los actos preliminares al inicio del proceso electoral, así como las"]:
        assert not P.page_footer_re.match(l), l


def test_resolver_ignora_constituciones_historicas():
    r = puebla.RESOLVER
    html = ('<a href="/media/k2/attachments/Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Puebla_de_1825.pdf">1825</a>'
            '<a href="/media/k2/attachments/Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Puebla_TEV_06032026.pdf">vigente</a>')
    assert resolver_pdf.elegir(html, r["patron"], r["index_url"], r["orden"]) == (
        "https://ojp.puebla.gob.mx/media/k2/attachments/"
        "Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Puebla_TEV_06032026.pdf")


def test_version_de_la_tabla_de_reformas():
    texto = ("Constitución Política del Estado Libre y Soberano de Puebla\nREFORMAS\n"
             "Publicación Extracto del texto\n02/oct/1917 Que la Legislatura del Estado\n"
             "05/jun/2025 ÚNICO. Se reforman las fracciones VII y XI del artículo\n"
             "6/mar/2026 ÚNICO. Se reforma el primer párrafo de la fracción VII y\n"
             "14\nCONTENIDO\nPárrafo reformado el 15/mar/2099.\n")
    assert P.version_de(texto) == date(2026, 3, 6)
    assert P.version_de("REFORMAS\n6/mar/2026 ÚNICO.") is None      # sin el índice que la cierra

"""Perfil de Sonora: sufijos latinos y con letra; citas que abren renglón; resolver por API."""
from datetime import date
import importlib.util
from pathlib import Path

from extractor.estados import sonora

P = sonora.PERFIL
_MOD = Path(__file__).resolve().parent.parent / "scripts" / "resolver_pdf.py"
_spec = importlib.util.spec_from_file_location("resolver_pdf", _MOD)
resolver_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver_pdf)


def test_encabezados():
    for linea, num, suf in [("ARTÍCULO 1°.- Los Derechos", 1, None), ("ARTÍCULO 1º BIS.- El Estado", 1, "BIS"),
                            ("ARTICULO 148-A.- Se deroga.", 148, "A"), ("Artículo 105 A.- En el", 105, "A"),
                            ("ARTÍCULO 67 QUINQUIES.- El Estado", 67, "QUINQUIES"), ("ARTICULO 10.- Los", 10, None)]:
        m = P.article_re.match(linea)
        assert m and int(m.group(1)) == num and m.group(2) == suf
    assert not P.article_re.match("Artículo 64 de esta Constitución.")


def test_transitorios_espaciados():
    assert P.transitorios_re.search("ARTICULO 166.- Se deroga.\nT R A N S I T O R I O S\n")


def test_resolver_api():
    r = sonora.RESOLVER
    js = ('{"resultado":[{"idLey":243,"archivos":{"doc":"58d4df06-1f07-41a6-adc5-3dbeb90320ea",'
          '"pdf":"30cd30a6-8667-4041-87ad-8ce1112c2be6","archivos":[]}}]}')
    url = resolver_pdf.elegir(js, r["patron"], r["index_url"], r["orden"], r["plantilla"])
    assert url == ("https://gestion.api.congresoson.gob.mx/publico/descarga"
                   "?uuid=30cd30a6-8667-4041-87ad-8ce1112c2be6")


def test_version_de_la_lista_de_reformas():
    texto = ("Estados Unidos Mexicanos, de la Ley 288, publicada en el B. O. 13, sección II,\n"
             "de fecha 13 de agosto de 2027, que no abre renglón.\n"
             "LEY 29.- B.O. No. 50 de fecha 19 de diciembre de 1923, que reforma la fracción XXIV.\n"
             "FE DE ERRATAS. De Ley 102, B. O. 5, sección IV, de fecha 16 de enero de 2030.\n"
             "LEY 158; B. O. 43, sección II, de fecha 28 de mayo de 2026, que se reforman.\n"
             "LEY 161; B. O. Edición Especial, de\nfecha 01 de noviembre de 2026, que se REFORMA.\n")
    assert P.version_de(texto) == date(2026, 11, 1)
    assert P.version_paginas is None
    assert P.version_de("Sin lista de reformas.") is None

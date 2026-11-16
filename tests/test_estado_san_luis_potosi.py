"""Perfil y resolver de San Luis Potosí, sin PDF."""
from __future__ import annotations

from extractor.estados.san_luis_potosi import PERFIL, RESOLVER
from extractor.normalize import normalize_body
from extractor.parse import parse_text
from scripts.resolver_pdf import elegir

_PDF = ("http://congresosanluis.gob.mx/sites/default/files/unpload/pdf/Constituci%C3%B3n%20"
        "Pol%C3%ADtica%20del%20Estado%20de%20Luis%20Potos%C3%AD%20%28al%2028%20de%20"
        "septiembre%20de%202026%29.pdf")
HTML = (f'<a href="{_PDF}">Constitución</a><a href="{_PDF}">Descargar</a>'
        '<a href="http://congresosanluis.gob.mx/sites/default/files/unpload/pdf/'
        'Ley%20Organica%20del%20Municipio%20Libre.pdf">Ley</a>')


def test_resolver_toma_solo_la_constitucion():
    assert elegir(HTML, RESOLVER["patron"], RESOLVER["index_url"], RESOLVER["orden"]) == _PDF


def test_acentos_descompuestos_y_notas_previas():
    # "ARTÍCULO": parte del PDF trae la tilde como carácter combinante.
    txt = "\n".join([
        "ARTICULO 89. El personal de las instituciones.",
        "(TÍTULO Y CAPÍTULO ADICIONADOS EN EL P.O. EL 20 DE NOVIEMBRE DE 1996",
        "REFORMADOS EN EL P.O.DEL EDO EL 19 DICIEMBRE DE 2024)",
        "TÍTULO OCTAVO",
        "DEL PODER JUDICIAL",
        "(ADICIONADO, P.O. 20 DE NOVIEMBRE DE 1996)",
        "CAPÍTULO I",
        "Disposiciones Generales",
        "(REFORADO P.O. 19 DICIEMBRE 2024)",
        "ARTÍCULO 90. El Poder Judicial del Estado.",
        "(REFORMADO P.O. 19 DICIEMBRE 2024)",
        "El Poder Judicial contará con apoyo.",
    ])
    a89, a90 = parse_text(txt, perfil=PERFIL)
    assert a89.body.strip() == "ARTICULO 89. El personal de las instituciones."
    assert a90.titulo == "TÍTULO OCTAVO" and a90.capitulo == "CAPÍTULO I"
    assert "(REFORMADO P.O. 19 DICIEMBRE 2024)" in a90.body


def test_titulo_con_ordinal_compuesto():
    txt = "\n".join([
        "ARTÍCULO 122 TER.- El Fiscal General presentará un informe.",
        "TÍTULO DECIMOSEGUNDO",
        "(REFORMADA SU DENOMINACION, P.O. 02 DE OCTUBRE DE 2017)",
        "DE LA JUSTICIA ADMINISTRATIVA",
        "(ADICIONADO, P.O. 20 DE NOVIEMBRE DE 1996)",
        "CAPÍTULO ÚNICO",
        "ARTÍCULO 123.- El Tribunal Estatal de Justicia Administrativa.",
    ])
    a, b = parse_text(txt, perfil=PERFIL)
    assert "TÍTULO" not in a.body and "JUSTICIA ADMINISTRATIVA" not in a.body
    assert b.titulo == "TÍTULO DECIMOSEGUNDO"


def test_notas_del_articulo_abren_su_articulo():
    # Las notas entre la denominación y el artículo (la envuelta, en un renglón)
    # van al inicio del artículo; las del título y del capítulo se quitan.
    txt = "\n".join([
        "ARTICULO 89. El personal de las instituciones.",
        "(TÍTULO ADICIONADO, P.O. 20 DE NOVIEMBRE DE 1996)",
        "TÍTULO OCTAVO",
        "DEL PODER JUDICIAL",
        "(ADICIONADO, P.O. 20 DE NOVIEMBRE DE 1996)",
        "CAPÍTULO I",
        "Disposiciones Generales",
        "(REFORMADO, P.O. 26 DE JULIO DE 2005)",
        "(ARTÍCULO REFORMADO EN EL P.O. DEL EDO. EL 20 DE",
        "NOVIEMBRE DE 1996)",
        "ARTÍCULO 90. El Poder Judicial del Estado.",
        "(REFORMADO, P.O. 1 DE ABRIL DE 2001)",
        "ARTÍCULO 91. Texto del noventa y uno.",
    ])
    a89, a90, a91 = parse_text(txt, perfil=PERFIL)
    assert a89.body.strip() == "ARTICULO 89. El personal de las instituciones."
    assert normalize_body(a90.body, a90.label, perfil=PERFIL).split("\n\n") == [
        "(REFORMADO, P.O. 26 DE JULIO DE 2005)",
        "(ARTÍCULO REFORMADO EN EL P.O. DEL EDO. EL 20 DE NOVIEMBRE DE 1996)",
        "El Poder Judicial del Estado."]
    assert normalize_body(a91.body, a91.label, perfil=PERFIL).split("\n\n") == [
        "(REFORMADO, P.O. 1 DE ABRIL DE 2001)", "Texto del noventa y uno."]

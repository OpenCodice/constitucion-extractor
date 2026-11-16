"""Perfil y resolver de Oaxaca, sin PDF."""
from __future__ import annotations

from datetime import date

from extractor.estados.oaxaca import PERFIL, RESOLVER
from extractor.parse import parse_text
from scripts.resolver_pdf import elegir

# Fragmento real del índice de legislación estatal (enlace relativo).
HTML = (
    '<a href="../../docs66.congresooaxaca.gob.mx/legislacion_estatal/'
    'Constitucion_Politica_del_Estado_Libre_y_Soberano_de_Oaxaca_(Dto_ref_1596_aprob_LXVI_'
    'legis_14_julio_2026_PO_31_11a_secc_1_agosto_2026).pdf">Constitución</a>'
    '<a href="../../docs66.congresooaxaca.gob.mx/legislacion_estatal/'
    'Ley_de_Ingresos_del_Estado_de_Oaxaca.pdf">Ley</a>'
)


def test_resolver_resuelve_el_enlace_relativo():
    url = elegir(HTML, RESOLVER["patron"], RESOLVER["index_url"], RESOLVER["orden"])
    assert url.startswith("https://www.congresooaxaca.gob.mx/docs66.congresooaxaca.gob.mx/")
    assert "Ley_de_Ingresos" not in url and "%28Dto_ref_1596" in url


def test_nota_que_empieza_como_encabezado_no_abre_articulo():
    txt = "\n".join([
        "Artículo 114 BIS. El Tribunal Electoral del Estado.",
        "Artículo 114 bis adicionado mediante decreto Número 1263 aprobado el 30 de junio del 2015",
        "Artículo 114 TER. La organización de las elecciones.",
        "Artículo 114 QUÁTER.- DEROGADO.",
    ])
    arts = parse_text(txt, perfil=PERFIL)
    assert [a.key for a in arts] == ["114-bis", "114-ter", "114-quater"]
    assert "adicionado mediante" in arts[0].body


def test_version_es_la_fecha_de_publicacion():
    portada = ("Última reforma: Decreto número 1596, aprobado por la LXVI Legislatura del Estado el "
               "14 de julio\ndel 2026, publicado en el Periódico Oficial número 31 Décima primera "
               "sección, de fecha 1 de\nagosto del 2026.")
    assert PERFIL.version_de(portada) == date(2026, 8, 1)
    assert PERFIL.fechas_de("publicado el 30 de junio del 2015") == [date(2015, 6, 30)]

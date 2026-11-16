"""Perfil de Guerrero, sin PDF: encabezados pegados, sufijos largos y notas previas."""
from __future__ import annotations

from datetime import date

from extractor.estados.guerrero import PERFIL
from extractor.normalize import normalize_body
from extractor.parse import parse_text


def test_encabezado_pegado_y_sufijos_largos():
    txt = "\n".join([
        "Artículo 44. Uno.",
        "Artículo 45.-El Congreso del Estado se integra por 28 Diputadas.",
        "Artículo 160 Quater. La ley señalará.",
        "Artículo 160 Quinquies. El Tribunal desahogará.",
    ])
    claves = [a.key for a in parse_text(txt, perfil=PERFIL)]
    assert claves == ["044", "045", "160-quater", "160-quinquies"]


def test_nota_previa_al_articulo_no_se_pega_al_anterior():
    # La nota anota al artículo siguiente; la que precede a una fracción se queda.
    txt = "\n".join([
        "Artículo 9. Texto del nueve:",
        "(REFORMADA, P.O. EDICIÓN 43 ALCANCE III, DE FECHA VIERNES 30 DE MAYO DE 2025)",
        "I. Fracción reformada.",
        "",
        "(REFORMADO PRIMER PÁRRAFO, P.O. EDICIÓN 51 ALCANCE I, VIERNES 27 DE JUNIO DE 2025)",
        "DECRETO 828",
        "APARTADO SEGUNDO",
        "DERECHOS, OBLIGACIONES Y PROHIBICIONES",
        "Artículo 10. Texto del diez.",
    ])
    a9, a10 = parse_text(txt, perfil=PERFIL)
    assert "30 DE MAYO DE 2025" in a9.body
    assert "27 DE JUNIO" not in a9.body and "APARTADO" not in a9.body
    assert "DECRETO 828" not in a9.body
    assert a10.body.startswith("Artículo 10.")


def test_corta_en_transitorios_con_punto():
    txt = "Artículo 200. Último.\n                TRANSITORIOS.\nArtículo 1°. Publíquese."
    arts = parse_text(txt, perfil=PERFIL)
    assert [a.number for a in arts] == [200]


def test_version_de_la_portada():
    portada = ("ÚLTIMAS MODIFICACIONES PUBLICADAS EN EL PERIÓDICO OFICIAL DEL GOBIERNO\n"
               "DEL ESTADO DE GUERRERO, P.O. EDICÍÓN No. 32 ALCANCE IV, DE FECHA MARTES 21\n"
               "DE ABRIL DE 2026.")
    assert PERFIL.version_de(portada) == date(2026, 4, 21)


def test_nota_previa_abre_su_articulo():
    # La nota (envuelta en dos renglones, más su "DECRETO 828" suelto) que precede
    # al artículo queda al inicio de ese artículo; la que precede al encabezado
    # anota la estructura y no va a ningún artículo.
    txt = "\n".join([
        "Artículo 70. Texto del setenta.",
        "(REFORMADO, P.O. EDICIÓN 51 ALCANCE I, VIERNES 27 DE JUNIO DE 2025) DECRETO 828",
        "TÍTULO SEXTO",
        "PODER EJECUTIVO",
        "(REFORMADO PRIMER PÁRRAFO, P.O. EDICIÓN 51 ALCANCE I, VIERNES 27 DE",
        "JUNIO DE 2025)",
        "DECRETO 828",
        "Artículo 71. El Poder Ejecutivo se deposita en un sólo individuo.",
    ])
    a70, a71 = parse_text(txt, perfil=PERFIL)
    assert a70.body.strip() == "Artículo 70. Texto del setenta."
    assert normalize_body(a71.body, a71.label, perfil=PERFIL).split("\n\n") == [
        "(REFORMADO PRIMER PÁRRAFO, P.O. EDICIÓN 51 ALCANCE I, VIERNES 27 DE JUNIO DE 2025) "
        "DECRETO 828",
        "El Poder Ejecutivo se deposita en un sólo individuo."]

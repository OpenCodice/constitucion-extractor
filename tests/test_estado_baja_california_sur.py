"""Baja California Sur: encabezados "1o.-" sin "Artículo", títulos espaciados y
encabezado de página del PDF convertido del Word (sin PDF)."""
from datetime import date

from extractor.estados.baja_california_sur import PERFIL, RESOLVER
from extractor.parse import _strip_headers, parse_text

ENCABEZADO = [
    "CONSTITUCIÓN POLÍTICA",
    "DEL ESTADO DE BAJA CALIFORNIA SUR",
    "H. Congreso del Estado de Baja Última Reforma BOGE. 72 Extraordinario 08-Septiembre-2026",
    "California Sur",
    "Oficialía Mayor",
    "Departamento de Apoyo Parlamentario",
]


def _texto(*renglones: str) -> str:
    return _strip_headers("\n".join(renglones), PERFIL)


def test_quita_encabezado_y_numero_de_pagina_pero_no_el_texto():
    limpio = _texto("sea sustentable e integral y regular el proceso", "1", *ENCABEZADO,
                    "compartido y que mediante la competitividad,",
                    "IV.- Oficialía Mayor.")
    assert limpio.splitlines() == ["sea sustentable e integral y regular el proceso",
                                   "compartido y que mediante la competitividad,",
                                   "IV.- Oficialía Mayor."]


def test_encabezados_de_articulo_y_fracciones():
    arts = parse_text(_texto(
        "6o.- Es función del Estado.",
        "7o.- En el Estado todas las personas:",
        "I.- Fracción en romanos.",
        "1.- Un numeral interno.",
        "7o Bis.- El Estado tiene una composición pluricultural.",
        "10o.- La educación.",
        "66 Ter.- La Auditoría Superior.",
        "85.-",
        "A. El Ministerio Público.",
    ), perfil=PERFIL)
    assert [(a.number, a.suffix) for a in arts] == [
        (6, ""), (7, ""), (7, "Bis"), (10, ""), (66, "Ter"), (85, "")]
    assert "I.- Fracción" in arts[1].body and "1.- Un numeral" in arts[1].body


def test_titulo_espaciado_no_queda_en_el_articulo_anterior():
    a160, a161 = parse_text(_texto(
        "160 Ter.- La ley señalará los casos de prescripción.",
        "T I T U L O D E C I M O",
        "PREVENCIONES GENERALES",
        "CAPITULO I",
        "161.- Todos los funcionarios.",
    ), perfil=PERFIL)
    assert "PREVENCIONES" not in a160.body and "T I T" not in a160.body
    assert a161.titulo == "TITULO DECIMO"


def test_denominacion_del_titulo_undecimo_no_queda_en_el_articulo_anterior():
    a165, a166 = parse_text(_texto(
        "165.- Todos los profesionistas.",
        "T I T U L O U N D E C I M O",
        "DE LA REFORMA E INVIOLABILIDAD DE LA CONSTITUCION",
        "166.- La presente Constitución puede ser adicionada y reformada.",
    ), perfil=PERFIL)
    assert "REFORMA E INVIOLABILIDAD" not in a165.body
    assert a166.titulo == "TITULO UNDECIMO"


def test_capitulo_unico_del_titulo_octavo_bis():
    _, a155b = parse_text(_texto(
        "155.- La Ley.",
        "T Í T U L O O C T A V O B I S",
        "DE LAS RELACIONES JURÍDICAS DE TRABAJO",
        "CAPÍTULO ÚNICO",
        "155 Bis.- Las relaciones de trabajo.",
    ), perfil=PERFIL)
    assert a155b.titulo == "TÍTULO OCTAVO BIS" and a155b.capitulo == "CAPÍTULO ÚNICO"


def test_version_de_la_portada():
    m = PERFIL.version_re.search("TEXTO VIGENTE\nÚltima reforma publicada BOGE 08-09-2026\n")
    assert date(int(m.group(3)), int(m.group(2)), int(m.group(1))) == date(2026, 9, 8)


def test_resolver_word_oficial():
    assert RESOLVER == {"tipo": "directo", "formato": "doc",
                        "url": "https://www.cbcs.gob.mx/LEYES-BCS/CPoliticaBCS-.doc"}

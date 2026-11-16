"""Perfil de Chihuahua: pruebas sin PDF."""
from datetime import date

from extractor.estados import chihuahua as c
from extractor.parse import _strip_headers, parse_text

PAGINA = """H. Congreso del Estado Constitución Política
Secretaría de Asuntos Legislativos y Jurídicos del Estado Libre y Soberano
Biblioteca Legislativa “Carlos Montemayor Aceves” de Chihuahua
Acción Inconstitucionalidad 163/2023
y su acumulada 164/2023
Acción de Inconstitucionalidad 96/2026 y
Acumuladas 97/2026, 99/2026 y 103/2026
Última reforma POE 2026.10.17/No. 83
ARTICULO 3º. El territorio del Estado es el que de hecho ha poseído.
2 de 207"""


def test_encabezado_variable_y_pie_fuera():
    assert _strip_headers(PAGINA, c.PERFIL).strip() == (
        "ARTICULO 3º. El territorio del Estado es el que de hecho ha poseído.")


def test_version_del_encabezado():
    assert c.version_encabezado(PAGINA) == date(2026, 10, 17)


def test_nota_sin_cerrar_no_se_traga_el_articulo_siguiente():
    texto = ("ARTÍCULO 10 QUINQUIES. Texto.\n"
             "[Artículo adicionado mediante Decreto No. LXVIII/RFCNT/0552/2026 VIII P.E. publicado en el P.O.E. No.\n"
             "83 del 17 de octubre de 2026\nTITULO III\nDE LA POBLACIÓN\nCAPITULO I\n"
             "DE LOS HABITANTES DEL ESTADO\nARTICULO 11. Son habitantes.\n")
    arts = parse_text(texto, perfil=c.PERFIL)
    assert [a.key for a in arts] == ["010-quinquies", "011"]
    assert "POBLACIÓN" not in arts[0].body

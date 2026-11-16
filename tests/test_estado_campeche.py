"""Perfil de Campeche: pruebas sin PDF."""
from datetime import date

from extractor.estados import campeche as c
from extractor.parse import parse_text


def test_version_del_encabezado():
    assert c.version_encabezado(
        "PODER LEGISLATIVO DEL ESTADO DE CAMPECHE ÚLTIMA REFORMA: DECRETO 297, P.O. 12/OCT/2026"
    ) == date(2026, 10, 12)


def test_nota_partida_tras_no_queda_en_un_renglon():
    texto = ("ARTÍCULO 88.- Texto.\n"
             "Nota: Se reformó mediante decreto No. 309, publicado en el P. O. del Estado No.\n"
             "3617 de fecha 6 de noviembre de 1985.\nSigue.\n")
    out = c.preparar(texto)
    assert "Estado No. 3617 de fecha 6 de noviembre de 1985.\n\n" in out


def test_derogado_sin_espacio_y_sufijo_con_tilde():
    texto = ("ARTÍCULO 100.- Texto.\nARTÍCULO 101.-DEROGADO.\n"
             "ARTÍCULO 101 bis.- Uno.\nARTÍCULO 101 quáter.- Dos.\n")
    arts = parse_text(texto, perfil=c.PERFIL)
    assert [a.key for a in arts] == ["100", "101", "101-bis", "101-quater"]


def test_capitulo_ter_no_se_pega_al_articulo_anterior():
    texto = ("ARTÍCULO 76 Bis.- Texto.\nCAPÍTULO XV TER\n"
             "DEL CENTRO DE CONCILIACIÓN LABORAL DEL ESTADO DE CAMPECHE\n"
             "Nota: Se adicionó mediante decreto No. 274, publicado en el P. O. No. 0726 de fecha 13 de julio de 2018.\n"
             "ARTÍCULO 76 Ter.- La función conciliatoria.\n")
    arts = parse_text(texto, perfil=c.PERFIL)
    assert "CONCILIACIÓN" not in arts[0].body
    assert arts[1].capitulo == "CAPÍTULO XV TER"


def test_articulos_con_numeracion_decimal():
    texto = ("ARTÍCULO 88.- Corresponde al Pleno.\nCAPÍTULO XVI BIS\n"
             "DE LA AUTORIDAD ELECTORAL JURISDICCIONAL DEL ESTADO DE CAMPECHE\n"
             "Nota: Se adicionó mediante decreto No. 139, publicado en el P. O. No. 5511 de fecha 24 de junio de 2014.\n"
             "ARTÍCULO 88.1.- La Autoridad Electoral.\nARTÍCULO 88.2.- Estará conformada.\n"
             "ARTÍCULO 89.- Otro.\n")
    arts = parse_text(texto, perfil=c.PERFIL)
    assert [(a.key, a.label) for a in arts] == [
        ("088", "Artículo 88"), ("088-1", "Artículo 88.1"),
        ("088-2", "Artículo 88.2"), ("089", "Artículo 89")]
    assert "AUTORIDAD" not in arts[0].body

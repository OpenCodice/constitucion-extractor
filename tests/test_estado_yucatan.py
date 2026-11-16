"""Perfil de Yucatán: pruebas sin PDF."""
from datetime import date

from extractor.estados import yucatan as y
from extractor.parse import parse_text


def test_version_de_la_portada():
    assert y.version_portada("Última reforma D.O. 04-septiembre-2026") == date(2026, 9, 4)


def test_fechas_de_las_notas():
    assert y.fechas_do("Párrafo reformado DO 22-04-2019, 14-11-2019\n"
                       "Párrafo adicionado D.O. 12-09-2022") == [date(2019, 4, 22), date(2022, 9, 12)]


def test_sufijos_hasta_nonies():
    texto = ("Artículo 75 Ter.- Uno.\nArtículo 75 Quater.- Dos.\n"
             "Artículo 75 Nonies.- Tres.\nArtículo 76.- Cuatro.\n")
    assert [a.key for a in parse_text(texto, perfil=y.PERFIL)] == [
        "075-ter", "075-quater", "075-nonies", "076"]


def test_encabezado_undecimo_y_denominacion_fuera_del_cuerpo():
    texto = ("Artículo 101.- Texto del artículo.\nPárrafo reformado D.O. 20-03-2017\n"
             "TITULO UNDÉCIMO\nDisposiciones Generales\nArtículo 102.- Las facultades.\n")
    arts = parse_text(texto, perfil=y.PERFIL)
    assert "Disposiciones" not in arts[0].body
    assert arts[1].titulo == "TITULO UNDÉCIMO"


def test_decimal_a_inicio_de_renglon_continua_la_frase():
    out = y.preparar("no podrá exceder del\n0.70% del presupuesto")
    assert "exceder del 0.70%" in out

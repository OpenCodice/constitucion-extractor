"""Perfil de Querétaro: notas de reforma al final del párrafo, a veces partidas."""
from datetime import date

from extractor.estados import queretaro


def test_notas_cierran_parrafo_y_se_unen():
    t = queretaro._preprocess(
        "a su nacimiento. (Adición P.\nO. No. 15, 23-II-18)\nToda persona tiene derecho\n"
        "(entrará en vigor a partir del año 2021)\nEl derecho de solicitar")
    assert t == ("a su nacimiento. (Adición P. O. No. 15, 23-II-18)\n\nToda persona tiene derecho\n"
                 "(entrará en vigor a partir del año 2021)\n\nEl derecho de solicitar")


def test_version_del_historial_de_cambios():
    texto = ("Fecha de publicación original (3) 31/03/2008 (No. 18)\n"
             "Nueva publicación Realizada en cumplimiento a la sentencia relativa a 31/12/2008 (No. 76)\n"
             "1ª Reforma Ley que reforma el artículo 2 de la Constitución 18/09/2009 (No. 68)\n"
             "Fe de erratas Oficio DALJ/2589/15/LVII, emitido por el Presidente 10/04/2027 (No. 17)\n"
             "39ª. Reforma Ley que reforma, adiciona y deroga diversas 30/04/2026 (No.35)\n"
             "40ª. Reforma Ley que reforma y adiciona diversas disposiciones 15/07/2026 (No.58)\n")
    assert queretaro.PERFIL.version_de(texto) == date(2026, 7, 15)


def test_fechas_de_las_notas():
    cuerpo = ("Toda persona. (Ref. P. O. No. 64, 23-VIII-19)\n\nEl derecho. (Adición P. O. No. 15, 23-II-18)\n\n"
              "De Querétaro. (Fe de erratas P. O. No. 21, 11-IV-08) y el 31-XIII-20 no es fecha.")
    assert queretaro.PERFIL.fechas_de(cuerpo) == [date(2008, 4, 11), date(2018, 2, 23), date(2019, 8, 23)]

"""Perfil de Querétaro: notas de reforma al final del párrafo, a veces partidas."""
from extractor.estados import queretaro


def test_notas_cierran_parrafo_y_se_unen():
    t = queretaro._preprocess(
        "a su nacimiento. (Adición P.\nO. No. 15, 23-II-18)\nToda persona tiene derecho\n"
        "(entrará en vigor a partir del año 2021)\nEl derecho de solicitar")
    assert t == ("a su nacimiento. (Adición P. O. No. 15, 23-II-18)\n\nToda persona tiene derecho\n"
                 "(entrará en vigor a partir del año 2021)\n\nEl derecho de solicitar")

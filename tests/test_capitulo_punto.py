from extractor.fuentes import perfil_por_nombre


def test_capitulo_con_punto_final():
    perfil = perfil_por_nombre("coahuila")
    assert perfil.capitulo_re.match("CAPITULO I.")
    assert perfil.capitulo_re.match("CAPÍTULO II")
    assert not perfil.capitulo_re.match("Capítulo I de la ley.")

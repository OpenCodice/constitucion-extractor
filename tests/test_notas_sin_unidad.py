from extractor.normalize import normalize_body

CUERPO = """Artículo 73. El Congreso tiene facultad:
VI. Derogada;
Fracción reformada DOF 20-08-1928 (2 reformas), 15-12-1934. Fe de erratas DOF 14-03-1951.
Reformada DOF 08-10-1974, 06-12-1977. Derogada DOF 22-08-1996
2a. En caso de epidemias de carácter grave, la Secretaría de Salud dictará las medidas preventivas.
Base reformada DOF 02-08-2007
3a. La autoridad sanitaria será ejecutiva.
Encabezado de inciso reformado DOF 27-06-1990
22. Servicios de banca y crédito.
Numeral adicionado DOF 27-06-1990
"""


def test_la_nota_que_no_nombra_parrafo_ni_fraccion_es_nota():
    bloques = normalize_body(CUERPO, "Artículo 73").split("\n\n")
    for nota in ("Reformada DOF 08-10-1974, 06-12-1977. Derogada DOF 22-08-1996",
                 "Base reformada DOF 02-08-2007",
                 "Encabezado de inciso reformado DOF 27-06-1990",
                 "Numeral adicionado DOF 27-06-1990"):
        assert f"_{nota}_" in bloques
    assert "3a. La autoridad sanitaria será ejecutiva." in bloques


def test_un_parrafo_que_empieza_con_reformas_no_es_nota():
    cuerpo = "Artículo 1. Primero.\nReformas a esta Constitución se publicarán en el Diario Oficial.\n"
    assert "_" not in normalize_body(cuerpo, "Artículo 1")

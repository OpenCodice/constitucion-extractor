"""Perfil de Zacatecas: pruebas sin PDF."""
from extractor.estados import zacatecas as z
from extractor.parse import parse_text


def test_cita_a_inicio_de_renglon_no_abre_articulo():
    texto = ("Artículo 118. El Estado tiene al Municipio Libre conforme a la Ley del\n"
             "Artículo 130 de la Constitución Política de los Estados Unidos Mexicanos;\n"
             "Artículo 119. El Ayuntamiento es el órgano supremo.\n")
    arts = parse_text(texto, perfil=z.PERFIL)
    assert [a.number for a in arts] == [118, 119]


def test_nota_de_reforma_queda_en_su_propio_bloque():
    texto = ("Artículo 1°. Primer párrafo del artículo\n"
             "Párrafo reformado POG 12 de julio de 2014 (Decreto 177) y\n"
             "23 de mayo de 2020 (Decreto 390)\n"
             "Segundo párrafo.\n")
    out = z.preparar(texto)
    assert "\n\nPárrafo reformado POG 12 de julio de 2014 (Decreto 177) y\n23 de mayo" in out
    assert "(Decreto 390)\n\nSegundo párrafo." in out


def test_encabezados_apilados_no_se_pegan_al_articulo_anterior():
    texto = ("Artículo 19. Las leyes determinarán el fallo respectivo.\n"
             "CAPÍTULO SÉPTIMO\nDE LAS PERSONAS EXTRANJERAS\n"
             "Denominación reformada POG 16 de septiembre de 2026 (Decreto 370)\n"
             "TÍTULO II\nDE LOS DERECHOS HUMANOS\n"
             "Título reformado POG 3 de noviembre de 2012 (Decreto 419)\n"
             "CAPÍTULO ÚNICO\nDE LOS DERECHOS HUMANOS Y SUS GARANTÍAS\n"
             "Artículo 20. Son personas extranjeras.\n")
    arts = parse_text(texto, perfil=z.PERFIL)
    assert "EXTRANJERAS" not in arts[0].body
    assert arts[1].titulo == "TÍTULO II" and arts[1].capitulo == "CAPÍTULO ÚNICO"


def test_resolver_arma_la_url_de_la_legislatura():
    assert z.URL_LEGISLATURA.format(65) == z.PERFIL.url_fuente

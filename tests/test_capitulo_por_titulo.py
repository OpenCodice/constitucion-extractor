"""Al registrar un Título nuevo el capítulo vigente se reinicia: un artículo de
un Título sin capítulos no hereda el capítulo del Título anterior (Baja
California Sur, art. 36 Bis, en el Título Quinto, heredaba "CAPITULO III")."""
from extractor.parse import parse_text
from extractor.perfil import perfil_estatal

PERFIL = perfil_estatal(
    ambito="prueba", clave="prb", nombre="Constitución de Prueba",
    fuente="Periódico Oficial de Prueba", url_fuente="https://example.test",
    texto_original="1900-01-01",
)

TEXTO = "\n".join([
    "TITULO CUARTO",
    "CAPITULO III",
    "DE LOS DIPUTADOS",
    "Artículo 36.- Los diputados son inviolables.",
    "TITULO QUINTO",
    "DE LA SOBERANIA",
    "Artículo 36 Bis.- La soberanía reside en el pueblo.",
    "CAPITULO I",
    "DEL PODER",
    "Artículo 37.- El poder se divide.",
    "TITULO QUINTO",
    "Artículo 38.- El mismo Título repetido no reinicia el capítulo.",
]) + "\n"


def test_titulo_nuevo_reinicia_el_capitulo():
    arts = {a.key: a for a in parse_text(TEXTO, perfil=PERFIL)}
    assert (arts["036"].titulo, arts["036"].capitulo) == ("TITULO CUARTO", "CAPITULO III")
    assert (arts["036-bis"].titulo, arts["036-bis"].capitulo) == ("TITULO QUINTO", "")
    assert (arts["037"].titulo, arts["037"].capitulo) == ("TITULO QUINTO", "CAPITULO I")
    assert (arts["038"].titulo, arts["038"].capitulo) == ("TITULO QUINTO", "CAPITULO I")


def test_el_texto_no_cambia():
    arts = {a.key: a for a in parse_text(TEXTO, perfil=PERFIL)}
    assert arts["036-bis"].body == "Artículo 36 Bis.- La soberanía reside en el pueblo."

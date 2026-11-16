"""Las claves de artículo son nombres de archivo portátiles."""
from extractor.parse import Article


def _clave(sufijo):
    return Article(number=7, suffix=sufijo).key


def test_sin_acentos_ni_espacios():
    assert _clave("Quáter") == "007-quater"
    assert _clave("Bis A") == "007-bis-a"


def test_la_enie_se_conserva():
    # En Coahuila "7 Ñ" sigue a "7 N": serían el mismo archivo.
    assert _clave("Ñ") == "007-ñ"
    assert _clave("N") == "007-n"

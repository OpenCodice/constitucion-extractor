"""Un renglón que cierra en ";" no corta el párrafo si el siguiente arranca en
minúscula (continuación de la misma fracción); sí lo corta ante un elemento de
lista o un párrafo nuevo. Y "2026." al inicio de renglón no es un numeral."""
from extractor.normalize import normalize_body

ENC = "Artículo 5.-"


def parrafos(*renglones: str) -> list[str]:
    return normalize_body("\n".join((ENC,) + renglones), ENC).split("\n\n")


def test_minuscula_tras_punto_y_coma_sigue_el_parrafo():
    # Veracruz, art. 5, fracc. VIII.
    assert parrafos(
        "VIII. Garantizar la participación efectiva de las mujeres indígenas, en",
        "condiciones de igualdad, en los procesos de desarrollo de sus pueblos y comunidades;",
        "su acceso a la educación, así como a la propiedad y posesión de la tierra.",
        "IX. Garantizar la red de comunicaciones.",
    ) == [
        "VIII. Garantizar la participación efectiva de las mujeres indígenas, en "
        "condiciones de igualdad, en los procesos de desarrollo de sus pueblos y comunidades; "
        "su acceso a la educación, así como a la propiedad y posesión de la tierra.",
        "IX. Garantizar la red de comunicaciones.",
    ]


def test_y_suelto_cierra_la_fraccion():
    # Veracruz, art. 67: "y" en su propio renglón antes de la siguiente fracción.
    assert parrafos(
        "a efecto de que expliquen el motivo de su negativa;",
        "y",
        "IV. Las demás que señale la ley.",
    ) == ["a efecto de que expliquen el motivo de su negativa; y",
          "IV. Las demás que señale la ley."]


def test_marcadores_y_mayusculas_siguen_cortando():
    assert parrafos(
        "I. Votar en las elecciones;",
        "II. Ser votado;",
        "a) En los cargos de elección;",
        "b. En los demás;",
        "lll. Asociarse libremente;",
        "lV. Las demás;",
        "La ley regulará lo anterior.",
    ) == ["I. Votar en las elecciones;", "II. Ser votado;", "a) En los cargos de elección;",
          "b. En los demás;", "lll. Asociarse libremente;", "lV. Las demás;",
          "La ley regulará lo anterior."]


def test_minuscula_tras_punto_sigue_cortando():
    # Solo el ";" deja seguir: tras punto o dos puntos el corte no cambia.
    assert parrafos("Primera oración.", "segunda línea.") == ["Primera oración.", "segunda línea."]
    assert parrafos("Son requisitos:", "ser mexicano.") == ["Son requisitos:", "ser mexicano."]


def test_anio_al_inicio_de_renglon_no_es_numeral():
    # Quintana Roo, art. 106: la fecha se parte en "…de julio de" / "2026. Con efectos…".
    assert parrafos(
        "resuelta en la sesión de fecha 6 de julio de",
        "2026. Con efectos a partir de la notificación.",
        "1. Primer numeral.",
        "125. Numeral de tres cifras.",
    ) == ["resuelta en la sesión de fecha 6 de julio de 2026. Con efectos a partir de la notificación.",
          "1. Primer numeral.", "125. Numeral de tres cifras."]

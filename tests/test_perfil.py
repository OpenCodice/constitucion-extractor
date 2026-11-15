"""Fija el comportamiento del motor multi-fuente (CPEUM + perfiles estatales).

No depende de PDFs: usa texto sintético vía `parse_text`. Cubre las diferencias
que la Fase 0 detectó entre la federal y las constituciones estatales.
"""
from __future__ import annotations

from extractor.parse import parse_text
from extractor.passages import passages_for
from extractor.perfil import CPEUM, perfil_estatal
from extractor.fuentes import CDMX, JALISCO

# Perfil estatal genérico para las pruebas (gate monotónico, regex Title/UPPER).
ESTADO = perfil_estatal(
    ambito="prueba", clave="prb", nombre="Constitución de Prueba",
    fuente="Periódico Oficial de Prueba", url_fuente="https://example.test",
    texto_original="1900-01-01",
)


def _texto(*lineas: str) -> str:
    return "\n".join(lineas) + "\n"


# --- el gate: la diferencia que rompía Jalisco ------------------------------

def test_gate_estricto_federal_se_detiene_en_hueco():
    """Federal: un hueco (artículo derogado) detiene la secuencia (por diseño)."""
    txt = _texto("Artículo 1o. Uno.", "Artículo 2o. Dos.", "Artículo 4o. Cuatro.")
    nums = [a.number for a in parse_text(txt, perfil=CPEUM)]
    assert nums == [1, 2]          # el 4 se descarta: no es el esperado (3)


def test_gate_monotonico_estatal_tolera_hueco_por_derogacion():
    """Estatal: el gate monotónico salta el hueco y sigue (caso art. 6 de Jalisco)."""
    txt = _texto("Artículo 1º Uno.", "Artículo 2º Dos.", "Artículo 4º Cuatro.")
    nums = [a.number for a in parse_text(txt, perfil=ESTADO)]
    assert nums == [1, 2, 4]


def test_estatal_ignora_cita_en_minuscula():
    """'artículo 50 ...' (minúscula) es CITA, no encabezado: no debe crear art. 50.

    Era el bug que tragaba 37 artículos de Jalisco con IGNORECASE a ciegas.
    """
    txt = _texto(
        "Artículo 1º Primero.",
        "lo dispuesto en el artículo 50 de la Ley General se aplica aquí.",
        "Artículo 2º Segundo.",
    )
    nums = [a.number for a in parse_text(txt, perfil=ESTADO)]
    assert nums == [1, 2]          # nunca aparece el 50


def test_estatal_acepta_encabezado_en_mayusculas():
    """CDMX marca los artículos en MAYÚSCULAS: 'ARTÍCULO 2'."""
    txt = _texto("ARTÍCULO 1 Uno.", "ARTÍCULO 2 Dos.")
    nums = [a.number for a in parse_text(txt, perfil=CDMX)]
    assert nums == [1, 2]


def test_estatal_variante_bis():
    txt = _texto("Artículo 35º Treinta y cinco.", "Artículo 35º Bis Bis.",
                 "Artículo 36º Treinta y seis.")
    arts = parse_text(txt, perfil=ESTADO)
    assert [(a.number, a.suffix) for a in arts] == [(35, ""), (35, "Bis"), (36, "")]
    assert arts[1].key == "035-bis"


# --- contrato hacia el RAG: ambito + ids prefijados -------------------------

def test_pasajes_estatales_prefijados_y_con_ambito():
    art = parse_text(_texto("Artículo 1º Texto del artículo de prueba, suficientemente largo."),
                     perfil=ESTADO)[0]
    p = passages_for(art, "2026-06-08", perfil=ESTADO)[0]
    assert p["id"].startswith("prb:")
    assert p["ambito"] == "prueba"
    assert p["fuente"] == "Periódico Oficial de Prueba"


def test_pasajes_federales_sin_prefijo():
    art = parse_text(_texto("Artículo 1o. Texto del artículo federal, suficientemente largo."),
                     perfil=CPEUM)[0]
    p = passages_for(art, "2026-06-02", perfil=CPEUM)[0]
    assert not p["id"].startswith(":") and ":" not in p["id"]
    assert p["ambito"] == "federal"


# --- etiqueta según el estilo ordinal de la fuente --------------------------

def test_etiqueta_por_estilo_ordinal():
    fed = parse_text(_texto("Artículo 1o. x."), perfil=CPEUM)[0]
    jal = parse_text(_texto("Artículo 1º x."), perfil=JALISCO)[0]
    cmx = parse_text(_texto("ARTÍCULO 1 x."), perfil=CDMX)[0]
    assert fed.label == "Artículo 1o."
    assert jal.label == "Artículo 1º"
    assert cmx.label == "Artículo 1"


# --- pie de página "N de TOTAL": el total cambia con cada edición del PDF ----

def test_pie_cpeum_no_depende_del_total_de_paginas():
    """El PDF pasó de 414 a 416 páginas y el pie '12 de 416' se colaba a media
    oración. El pie se reconoce con cualquier total, no con uno fijo."""
    from extractor.parse import _strip_headers
    for total in (414, 416, 420, 1003):
        pagina = _texto(
            "Artículo 1o. Uno, con una oración que el salto de página parte en",
            f"12 de {total}",
            "dos mitades.",
            "Artículo 2o. Dos.")
        arts = parse_text(_strip_headers(pagina, CPEUM), perfil=CPEUM)
        assert [a.number for a in arts] == [1, 2]
        assert f"de {total}" not in arts[0].body
        assert "parte en\ndos mitades." in arts[0].body
    # Una línea de texto legal que solo se parece al pie no se descarta.
    assert "3 de 5" in _strip_headers("integrado por\n3 de 5\nconsejeros", CPEUM)


# --- encabezado estructural: no pertenece al artículo anterior --------------

def test_denominacion_de_titulo_capitulo_seccion_no_se_pega_al_articulo_anterior():
    """'Capítulo II / De los Mexicanos' quedaba con el 'Capítulo II' fuera pero
    la denominación pegada al final del artículo anterior; 'Sección I ...'
    quedaba entera. El bloque completo es estructura, no cuerpo."""
    txt = _texto(
        "Artículo 1o. Uno.",
        "Artículo reformado DOF 10-06-2011",
        "Capítulo II",
        "De los Mexicanos",
        "Artículo 2o. Dos.",
        "Sección I",
        "De la Elección e Instalación del Congreso",
        "Sección adicionada DOF 30-07-1999",
        "Artículo 3o. Tres.",
        "Título Cuarto",
        "De las Responsabilidades de los Servidores Públicos, Particulares",
        "Vinculados con Faltas Administrativas Graves, y Patrimonial del Estado.",
        "Denominación del Título reformada DOF 28-12-1982, 27-05-2015",
        "Artículo 4o. Cuatro.",
        "Título Quinto",
        "Capítulo I",
        "De la Soberanía Nacional",
        "Artículo 5o. Cinco.")
    arts = parse_text(txt, perfil=CPEUM)
    assert [a.body for a in arts] == [
        "Artículo 1o. Uno.\nArtículo reformado DOF 10-06-2011",
        "Artículo 2o. Dos.", "Artículo 3o. Tres.", "Artículo 4o. Cuatro.",
        "Artículo 5o. Cinco."]
    assert [(a.titulo, a.capitulo) for a in arts][1:] == [
        ("", "Capítulo II"), ("", "Capítulo II"),
        ("Título Cuarto", "Capítulo II"), ("Título Quinto", "Capítulo I")]
    # La nota de la denominación no cuenta como reforma del artículo anterior.
    assert [d.year for d in arts[2].reform_dates] == []


def test_mencion_de_un_titulo_dentro_del_cuerpo_no_es_encabezado():
    """'Título Cuarto de esta Constitución.' o un 'Capítulo II' suelto sin
    artículo a continuación no abren bloque: el cuerpo sigue completo."""
    txt = _texto(
        "Artículo 1o. Serán responsables en los términos del",
        "Título Cuarto de esta Constitución.",
        "Los servidores públicos aplicarán con imparcialidad los recursos.",
        "Artículo 2o. Dos.")
    a1 = parse_text(txt, perfil=CPEUM)[0]
    assert a1.body.endswith(
        "Título Cuarto de esta Constitución.\n"
        "Los servidores públicos aplicarán con imparcialidad los recursos.")
    # Estatal (gate monotónico, MAYÚSCULAS): mismo comportamiento.
    txt = _texto("ARTÍCULO 1. Uno.", "CAPÍTULO II", "DE LOS PODERES PÚBLICOS",
                 "ARTÍCULO 2. Dos.")
    assert [a.body for a in parse_text(txt, perfil=ESTADO)] == [
        "ARTÍCULO 1. Uno.", "ARTÍCULO 2. Dos."]


def test_estatal_variante_bis_minuscula_tras_encabezado_de_capitulo():
    """'Artículo 107 bis.-' (bis en minúscula) tras un bloque Capítulo +
    denominación abre su propio artículo; no se pierde ni se pega al anterior."""
    txt = _texto("Artículo 107.- Uno.", "Texto del 107.",
                 "CAPÍTULO V", "DE LA RESPONSABILIDAD PATRIMONIAL",
                 "DEL ESTADO Y LOS MUNICIPIOS",
                 "Artículo 107 bis.- Dos.", "Texto del bis.",
                 "Artículo 108.- Tres.")
    arts = parse_text(txt, perfil=ESTADO)
    assert [a.key for a in arts] == ["107", "107-bis", "108"]
    assert "RESPONSABILIDAD" not in arts[0].body
    assert "Texto del bis." in arts[1].body

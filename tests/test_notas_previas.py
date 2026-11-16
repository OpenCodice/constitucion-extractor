"""`notas_previas`: la nota de reforma que el PDF pone ANTES de "Artículo N" es
del artículo N, no del anterior; y `cobertura` tolera el encabezado entre esa
nota y el primer párrafo (solo ese hueco, una vez)."""
from __future__ import annotations

import re
from dataclasses import replace

from extractor.build import render_markdown
from extractor.parse import parse_text
from extractor.perfil import perfil_estatal
from extractor.verificar import Flujo, cobertura

_NOTA = re.compile(r"^\((?:REFORMAD|ADICIONAD|DEROGAD)")

BASE = perfil_estatal(
    ambito="prueba", clave="prb", nombre="Constitución de Prueba",
    fuente="Periódico Oficial de Prueba", url_fuente="https://example.test",
    texto_original="1900-01-01",
)
CON = replace(BASE, notas_previas=_NOTA)

TEXTO = "\n".join([
    "Artículo 1º. El Estado es libre.",
    "(REFORMADO, P.O. 13 DE OCTUBRE DE 2001)",
    "",
    "(ADICIONADO, P.O. 1 DE MAYO DE 1990)",
    "Artículo 2º. La soberanía reside en el pueblo.",
    "(ADICIONADO, P.O. 2 DE MAYO DE 1990)",
    "",
    "Los poderes la ejercen.",
    "Artículo 3º.-",
    "(DEROGADO, P.O. 3 DE JUNIO DE 2000)",
    "(REFORMADO, P.O. 4 DE JUNIO DE 2000)",
    "Artículo 4º. Las leyes obligan a todos.",
]) + "\n"


def _md(perfil):
    return {a.key: render_markdown(a, perfil=perfil) for a in parse_text(TEXTO, perfil=perfil)}


def test_sin_la_opcion_no_cambia_nada():
    md = _md(BASE)
    assert "(REFORMADO, P.O. 13 DE OCTUBRE DE 2001)" in md["001"]
    assert md["002"].startswith("# Artículo 2º\n\nLa soberanía")


def test_las_notas_previas_abren_su_articulo_en_orden():
    md = _md(CON)
    assert md["001"] == "# Artículo 1º\n\nEl Estado es libre.\n"
    assert md["002"] == (
        "# Artículo 2º\n\n(REFORMADO, P.O. 13 DE OCTUBRE DE 2001)\n\n"
        "(ADICIONADO, P.O. 1 DE MAYO DE 1990)\n\nLa soberanía reside en el pueblo.\n\n"
        "(ADICIONADO, P.O. 2 DE MAYO DE 1990)\n\nLos poderes la ejercen.\n")


def test_la_nota_que_es_todo_el_cuerpo_se_queda():
    # "Artículo 3º.-" + "(DEROGADO...)": su única nota es su cuerpo; la siguiente
    # sí es del 4.
    md = _md(CON)
    assert md["003"] == "# Artículo 3º\n\n(DEROGADO, P.O. 3 DE JUNIO DE 2000)\n"
    assert md["004"].startswith("# Artículo 4º\n\n(REFORMADO, P.O. 4 DE JUNIO DE 2000)\n\nLas leyes")


def test_fechas_de_reforma_van_con_su_articulo():
    arts = {a.key: a for a in parse_text(TEXTO, perfil=CON)}
    assert [d.year for d in arts["001"].reform_dates] == []
    assert {d.year for d in arts["002"].reform_dates} == {1990, 2001}


def test_cobertura_tolera_solo_el_encabezado_propio():
    flujo = Flujo.de(TEXTO)
    md = _md(CON)
    assert all(not cobertura(m, flujo) for m in md.values())
    # Si falta texto además del encabezado, sigue siendo un hueco.
    recortado = md["002"].replace("La soberanía reside en el pueblo.\n\n", "")
    assert cobertura(recortado, flujo)
    # El encabezado de OTRO artículo no se tolera.
    ajeno = md["002"].replace("# Artículo 2º", "# Artículo 7º")
    assert cobertura(ajeno, flujo)


def test_las_notas_no_alargan_el_bloque_de_encabezado():
    # Tabasco: Título + denominación + Capítulo + seis notas antes del artículo.
    texto = "\n".join([
        "Artículo 54.- La o el Fiscal General será responsable.",
        "TÍTULO V",
        "PODER JUDICIAL",
        "CAPITULO ÚNICO",
        *[f"(REFORMADO, P.O. {d} DE ENERO DE 2020)" for d in range(1, 7)],
        "Artículo 55.- El ejercicio del Poder Judicial se deposita en el Tribunal.",
    ]) + "\n"
    a54, a55 = parse_text(texto, perfil=CON)
    assert "PODER JUDICIAL" not in a54.body and "TÍTULO" not in a54.body
    assert render_markdown(a55, perfil=CON).count("(REFORMADO") == 6
    # Sin la opción el bloque es demasiado largo y se queda en el 54, como antes.
    assert "PODER JUDICIAL" in parse_text(texto, perfil=BASE)[0].body


ENC = replace(CON, notas_previas_encabezado=True)

TEXTO_ENC = "\n".join([
    "Artículo 3º.- Son obligaciones de los habitantes cumplir las leyes.",
    "(ADICIONADO, P.O. 1 DE FEBRERO DE 1960)",
    "CAPITULO II",
    "De los Habitantes del Estado",
    "(REFORMADO, P.O. 2 DE FEBRERO DE 1960)",
    "Artículo 4º.- Son michoacanos los nacidos en el Estado.",
]) + "\n"


def test_notas_antes_del_capitulo_van_al_articulo_siguiente():
    a3, a4 = parse_text(TEXTO_ENC, perfil=ENC)
    assert "(ADICIONADO" not in a3.body
    md = render_markdown(a4, perfil=ENC)
    assert md == ("# Artículo 4º\n\n(ADICIONADO, P.O. 1 DE FEBRERO DE 1960)\n\n"
                  "(REFORMADO, P.O. 2 DE FEBRERO DE 1960)\n\nSon michoacanos los nacidos en el Estado.\n")
    assert a4.capitulo == "CAPITULO II"
    assert not cobertura(md, Flujo.de(TEXTO_ENC))
    # Sin la opción la primera nota se queda en el 3.
    assert "(ADICIONADO" in parse_text(TEXTO_ENC, perfil=CON)[0].body


def test_cobertura_no_tolera_texto_tras_un_parrafo():
    # El hueco de encabezado solo se tolera mientras lo anterior sean notas.
    a4 = render_markdown(parse_text(TEXTO_ENC, perfil=ENC)[1], perfil=ENC)
    texto = TEXTO_ENC.replace("(ADICIONADO, P.O. 1 DE FEBRERO DE 1960)",
                              "Texto legal suelto.\n(ADICIONADO, P.O. 1 DE FEBRERO DE 1960)")
    md = a4.replace("(ADICIONADO", "Texto legal suelto.\n\n(ADICIONADO")
    assert cobertura(md, Flujo.de(texto))
    md_malo = a4.replace("# Artículo 4º\n\n", "# Artículo 4º\n\nSon obligaciones de los habitantes cumplir las leyes.\n\n")
    assert cobertura(md_malo, Flujo.de(TEXTO_ENC))


def test_encabezados_con_sufijo():
    texto = "\n".join([
        "Artículo 105 BIS.- El Tribunal de Justicia.",
        "CAPITULO III TER",
        "DEL TRIBUNAL DE DISCIPLINA JUDICIAL",
        "Artículo 105 TER.- El Tribunal de Disciplina Judicial.",
        "TITULO TERCERO A",
        "DE LOS ÓRGANOS AUTÓNOMOS",
        "Artículo 106.- Los órganos autónomos.",
        "CAPÍTULO I A los Municipios corresponde",
        "Artículo 107.- La hacienda.",
    ]) + "\n"
    perfil = replace(BASE, article_re=re.compile(
        r"^Art[íi]culo\s+(\d+)\s*((?i:bis|ter))?\.-"))
    arts = {a.key: a for a in parse_text(texto, perfil=perfil)}
    assert "DISCIPLINA" not in arts["105-bis"].body
    assert "TITULO" not in arts["105-ter"].body and "AUTÓNOMOS" not in arts["105-ter"].body
    assert arts["105-ter"].capitulo == "CAPITULO III TER"
    # "CAPÍTULO I A los…" es texto, no un encabezado.
    assert "CAPÍTULO I A los Municipios" in arts["106"].body

"""Pruebas del verificador (sin LLM real ni PDF)."""
import json
import re

from extractor.perfil import CPEUM
from extractor.verificar import (Cambio, Flujo, _norm, cobertura, paginas_de,
                                 patrones_de_ruido, verificar_cambio)

PARRAFO = "Quien ejerza el cargo no podrá adquirir ni solicitar otra nacionalidad."


PALABRAS = "uno dos tres cuatro cinco seis siete ocho nueve diez".split()


def _paginas(n=10):
    return [f"ENCABEZADO DEL CONGRESO\nArtículo de relleno.\nTexto legal {PALABRAS[i]} con contenido.\n"
            f"Más texto {PALABRAS[i]}.\nPárrafo reformado DOF 0{i % 3 + 1}-06-2011\n{i + 1} de {n}"
            for i in range(n)]


def test_ruido_acepta_pie_y_encabezado_repetidos():
    pats = patrones_de_ruido(["3 de 10", "ENCABEZADO DEL CONGRESO"], _paginas())
    assert pats == [r"^ENCABEZADO\s+DEL\s+CONGRESO$", r"^\d+\s+de\s+\d+$"]
    assert re.match(pats[1], "412 de 416")


def test_ruido_rechaza_texto_legal():
    paginas = _paginas()
    assert patrones_de_ruido(["Texto legal cuatro con contenido."], paginas) == []
    assert patrones_de_ruido(["línea que no existe en el PDF"], paginas) == []


def test_ruido_rechaza_linea_repetida_fuera_del_borde():
    paginas = [f"ENCABEZADO\nuno\nDerogado.\ndos\ntres\n{i} de 9" for i in range(9)]
    assert patrones_de_ruido(["Derogado."], paginas) == []


def test_bloques_solo_reporta_lo_que_cambio():
    c = Cambio("082", "A\n\nB\n\nC", "A\n\nB2\n\nC\n\nD")
    assert c.bloques() == (["B"], ["B2", "D"])


def test_paginas_se_anclan_al_articulo_cuando_el_parrafo_se_repite():
    normas = [_norm(t) for t in (
        f"Artículo 82. Para ser Presidente se requiere algo. {PARRAFO}",
        "Artículo 100. Texto sin relación con lo anterior en absoluto.",
        f"Artículo 116. Sólo podrá ser gobernador constitucional. {PARRAFO}",
    )]
    articulo = ["Sólo podrá ser gobernador constitucional.", PARRAFO]
    assert paginas_de([PARRAFO], articulo, normas) == [2]


def _cambio():
    return Cambio("116", "Texto anterior del artículo.", "Texto nuevo del artículo reformado.")


def test_veredicto_fiel():
    v = verificar_cambio(_cambio(), ["x"], ["x"], lambda _: '{"veredicto": "fiel"}', CPEUM)
    assert v.veredicto == "fiel"


def test_veredicto_valido_se_respeta():
    resp = json.dumps({"veredicto": "artefacto", "explicacion": "pie colado",
                       "problemas": [{"tipo": "ruido_pagina", "fragmento": "8 de 416"}],
                       "lineas_ruido": ["8 de 416"]})
    v = verificar_cambio(_cambio(), ["x"], ["x"], lambda _: resp, CPEUM)
    assert (v.veredicto, v.lineas_ruido) == ("artefacto", ["8 de 416"])


def test_respuesta_invalida_es_incierto():
    v = verificar_cambio(_cambio(), ["x"], ["x"], lambda _: "no es json", CPEUM)
    assert v.veredicto == "incierto"
    v = verificar_cambio(_cambio(), ["x"], ["x"], lambda _: '{"veredicto": "quizá"}', CPEUM)
    assert v.veredicto == "incierto"


PDF_LIMPIO = """Artículo 5. Primer párrafo del artículo cinco, con texto propio.
Segundo párrafo, distinto del primero y también único.
Derogado.
Capítulo II
Artículo 6. Otro artículo que no importa aquí.
Derogado."""


def _md(*parrafos):
    return "# Artículo 5\n\n" + "\n\n".join(parrafos) + "\n"


def test_cobertura_acepta_extraccion_completa():
    f = Flujo.de(PDF_LIMPIO)
    assert cobertura(_md("Primer párrafo del artículo cinco, con texto propio.",
                         "Segundo párrafo, distinto del primero y también único.",
                         "Derogado."), f) == []


def test_cobertura_detecta_parrafo_omitido():
    f = Flujo.de(PDF_LIMPIO)
    pr = cobertura(_md("Primer párrafo del artículo cinco, con texto propio.", "Derogado."), f)
    assert [p["tipo"] for p in pr] == ["texto_omitido"]
    assert "Segundo párrafo" in pr[0]["fragmento"]


def test_cobertura_detecta_texto_que_no_esta_en_el_pdf():
    f = Flujo.de(PDF_LIMPIO)
    pr = cobertura(_md("Primer párrafo del artículo 12 de 416 cinco, con texto propio.",
                       "Segundo párrafo, distinto del primero y también único."), f)
    assert [p["tipo"] for p in pr] == ["no_literal"]


def test_cobertura_ignora_encabezados_de_capitulo():
    f = Flujo.de("Artículo 5. Texto único del quinto.\nCapítulo II\nCierre único del quinto.")
    assert cobertura(_md("Texto único del quinto.", "Cierre único del quinto."), f) == []


def test_sin_llm_la_cobertura_cubre_todos_los_cambiados(monkeypatch, tmp_path):
    import extractor.verificar as vf
    cambios = [vf.Cambio(f"{i:03d}", "", f"# Artículo {i}\n\nTexto {i}.\n")
               for i in range(1, vf.MAX_ARTICULOS + 6)]
    monkeypatch.setattr(vf, "cambios", lambda out: cambios)
    monkeypatch.setattr(vf, "paginas_crudas", lambda pdf, perfil: [])
    monkeypatch.setattr(vf, "extract_clean_text", lambda pdf, perfil=None: "")
    monkeypatch.setattr(vf, "cobertura", lambda texto, flujo: [])
    monkeypatch.setattr(vf, "cargar_ruido", lambda out: [])
    from extractor.perfil import CPEUM
    r = vf.verificar("x.pdf", tmp_path, CPEUM, None)
    assert len(r.veredictos) == len(cambios) and r.ok

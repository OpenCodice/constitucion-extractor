"""Perfil de Michoacán: notas de reforma en renglón propio; resolver."""
import importlib.util
from pathlib import Path

from extractor.estados import michoacan

P = michoacan.PERFIL
_MOD = Path(__file__).resolve().parent.parent / "scripts" / "resolver_pdf.py"
_spec = importlib.util.spec_from_file_location("resolver_pdf", _MOD)
resolver_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver_pdf)


def test_encabezados():
    for linea, num, suf in [("Artículo 1º.- En el Estado", 1, None), ("Artículo 2° bis.- En el", 2, "bis"),
                            ("Artículo 3°. El Estado", 3, None), ("Artículo. 43.- El Ejecutivo", 43, None),
                            ("Artículo 98 A.- Se establecerá", 98, "A")]:
        m = P.article_re.match(linea)
        assert m and int(m.group(1)) == num and m.group(2) == suf
    assert P.page_footer_re.match("15/04/2026 12:27 p. m. 1")


def test_notas_partidas_y_como_parrafo():
    t = michoacan._preprocess("(ADICIONADO CON LOS CAPÍTULOS, P.O.\n23 DE MAYO DE 2006)\nTexto")
    assert t == "(ADICIONADO CON LOS CAPÍTULOS, P.O. 23 DE MAYO DE 2006)\n\nTexto"


def test_resolver_toma_el_texto_vigente():
    r = michoacan.RESOLVER
    html = ('<h6>Constitución Política de los Estados Unidos Mexicanos</h6><a href="https://congresomich.site/wp-content/uploads/2026/01/cpeum.pdf">x</a>'
            '<h6>Constitución Política del Estado de Michoacán de Ocampo</h6><p>Texto vigente: '
            '<a href="https://congresomich.site/wp-content/uploads/2026/04/20251202_CONSTITUCION-POLITI_122754923.pdf">PDF</a>'
            '</p><p>Reformas: <a href="https://congresomich.site/wp-content/uploads/2026/04/reforma-3-de-marzo.pdf">r</a>')
    assert resolver_pdf.elegir(html, r["patron"], r["index_url"], r["orden"]) == (
        "https://congresomich.site/wp-content/uploads/2026/04/20251202_CONSTITUCION-POLITI_122754923.pdf")

"""Perfil de Tamaulipas: encabezado con folio, guion pegado al texto; resolver."""
import importlib.util
from pathlib import Path

from extractor.estados import tamaulipas

P = tamaulipas.PERFIL
_MOD = Path(__file__).resolve().parent.parent / "scripts" / "resolver_pdf.py"
_spec = importlib.util.spec_from_file_location("resolver_pdf", _MOD)
resolver_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver_pdf)


def test_encabezados():
    for linea, num in [("ARTÍCULO 1o.- El Estado", 1), ("ARTÍCULO 49.-El Congreso", 49),
                       ("ARTÍCULO 153 Bis. - El Tribunal", 153)]:
        m = P.article_re.match(linea)
        assert m and int(m.group(1)) == num
    assert not P.article_re.match("ARTÍCULO 139, DE LA CONSTITUCIÓN")
    assert P.page_footer_re.match("Constitución Política del Estado de Tamaulipas Pág. 12")


def test_resolver():
    r = tamaulipas.RESOLVER
    html = ('<a href="/Parlamentario/Archivos/Constituciones/Const Pol del Edo POE 12-octubre 2026.pdf" '
            'target="_blank"></a><a href="/Parlamentario/Archivos/Constituciones/'
            'Const Pol del Edo POE 12-octubre 2026.pdf" target="_blank">PDF</a>')
    assert resolver_pdf.elegir(html, r["patron"], r["index_url"], r["orden"]) == (
        "https://www.congresotamaulipas.gob.mx/Parlamentario/Archivos/Constituciones/"
        "Const%20Pol%20del%20Edo%20POE%2012-octubre%202026.pdf")

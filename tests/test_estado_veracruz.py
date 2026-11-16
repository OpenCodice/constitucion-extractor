"""Perfil de Veracruz: notas antes del artículo, llamadas de nota y resolver (sin PDF)."""
import importlib.util
from datetime import date
from pathlib import Path

from extractor.build import render_markdown
from extractor.estados import veracruz
from extractor.parse import parse_text

P = veracruz.PERFIL
_MOD = Path(__file__).resolve().parent.parent / "scripts" / "resolver_pdf.py"
_spec = importlib.util.spec_from_file_location("resolver_pdf", _MOD)
resolver_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver_pdf)

# Fragmento real de https://www.legisver.gob.mx/Inicio.php?p=le (noviembre de 2026).
INDICE = """
<li class="collection-item"><a style="color:#333" href="javascript:PDF('leyes/LeyesPDF/CONSTITUCION30102026AI.pdf');">Constitución Política del Estado de Veracruz de Ignacio de la Llave</a></li>
<li class="collection-item"><a style="color:#333" href="leyes/LeyesPDF/CONSTITUCION30102026AI.pdf" target="_blank">Constitución Política del Estado de Veracruz de Ignacio de la Llave</a></li>
<li class="collection-item"><a style="color:#333" href="javascript:PDF('leyes/ConstitucionPDF/INICIATIVA.pdf');">Iniciativa de Reforma Integral a la Constitución Política del Estado de Veracruz de Ignacio de la Llave</a></li>
<li class="collection-item"><a style="color:#333" href="leyes/ConstitucionPDF/DICTAMEN.pdf" target="_blank">Dictamen y Texto de Ley aprobado por el Congreso del Estado</a></li>
<a style="color:#333" href="javascript:PDF('leyes/LeyesPDF/LCCONSTITUCIONAL04022020.pdf');">Ley de Control Constitucional para el Estado de Veracruz de Ignacio de la Llave.</a>
<a style="color:#333" href="http://www.legisver.gob.mx/leyes/LeyesPDF/LCCONSTITUCIONAL04022020.pdf" target="_blank">Ley de Control Constitucional para el Estado de Veracruz de Ignacio de la Llave.</a>
"""

TEXTO = "\n".join([
    "TÍTULO PRIMERO",
    "CAPÍTULO I",
    "DE LA SOBERANÍA Y DEL TERRITORIO DEL ESTADO",
    "(REFORMADO, G.O. 18 DE MARZO DE 2003)",
    "Artículo 1. El Estado de Veracruz de Ignacio de la Llave es parte integrante de la Federación",
    "Mexicana, libre y autónomo en su administración y gobierno interiores.",
    "El Congreso podrá llamar a las autoridades para que expliquen el motivo de su negativa;",
    "y",
    "(ADICIONADO, G.O. 4 DE NOVIEMBRE DE 2016)",
    "d) El Presidente de la Comisión durará en su función cinco años.",
    "(SE SUPRIME DENOMINACIÓN; “SECCION PRIMERA”; G.O. 9 DE ENERO DE 2015)",
    "DEL CONTROL CONSTITUCIONAL",
    "Artículo 64. Para el cumplimiento de las atribuciones señaladas en el artículo 56.",
    "(DEROGADO, G.O. 9 DE ENERO DE 2015)",
    "Artículo 67 Bis. El Sistema Estatal Anticorrupción es la instancia de coordinación.",
]) + "\n"


def test_resolver_elige_el_texto_vigente():
    r = veracruz.RESOLVER
    assert r["via"] == "mx" and r["orden"] == "ddmmaaaa"
    assert {m[0] for m in r["patron"].findall(INDICE)} == {"leyes/LeyesPDF/CONSTITUCION30102026AI.pdf"}
    assert resolver_pdf.elegir(INDICE, r["patron"], r["index_url"], r["orden"]) == (
        "https://www.legisver.gob.mx/leyes/LeyesPDF/CONSTITUCION30102026AI.pdf")


def test_resolver_toma_la_fecha_mas_reciente():
    r = veracruz.RESOLVER
    html = INDICE + '<a href="leyes/LeyesPDF/CONSTITUCION02072026.pdf">vieja</a>'
    assert resolver_pdf.elegir(html, r["patron"], r["index_url"], r["orden"]).endswith(
        "CONSTITUCION30102026AI.pdf")


def test_notas_previas_y_denominacion_suelta():
    arts = parse_text(TEXTO, perfil=P)
    assert [a.key for a in arts] == ["001", "064", "067-bis"]
    md = render_markdown(arts[0], perfil=P)
    assert "(REFORMADO, G.O. 18 DE MARZO DE 2003)\n\nEl Estado de Veracruz" in md
    assert "negativa; y\n\n(ADICIONADO, G.O. 4 DE NOVIEMBRE DE 2016)\n\nd) El Presidente" in md
    assert "DEL CONTROL" not in md
    md64 = render_markdown(arts[1], perfil=P)
    assert "2015)\n\nDEL CONTROL CONSTITUCIONAL\n\nPara el cumplimiento" in md64
    assert "(DEROGADO" not in md64
    assert "(DEROGADO, G.O. 9 DE ENERO DE 2015)" in render_markdown(arts[2], perfil=P)


def test_encabezado_y_llamadas_de_nota():
    for linea in ("CONSTITUCIÓN POLÍTICA DEL ESTADO LIBRE Y SOBERANO",
                  "DE VERACRUZ DE IGNACIO DE LA LLAVE", "Secretaría General 30 DE OCTUBRE DE 2026"):
        assert P.page_footer_re.match(linea)
    assert not P.page_footer_re.match("DE VERACRUZ DE IGNACIO DE LA LLAVE, el Congreso")
    assert veracruz.version_encabezado(
        "H. CONGRESO DEL ESTADO DE VERACRUZ Última Actualización\n"
        "Secretaría General 30 DE OCTUBRE DE 2026\n") == date(2026, 10, 30)
    assert not P.filtro_char({"object_type": "char", "text": "*", "size": 14.0})
    assert P.filtro_char({"object_type": "char", "text": "*", "size": 8.0})
    assert P.filtro_char({"object_type": "char", "text": "a", "size": 14.0})

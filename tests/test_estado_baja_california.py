"""Perfil de Baja California: pruebas sin PDF."""
from datetime import date

from extractor.estados import baja_california as b
from extractor.parse import _strip_headers

# Fragmento de la respuesta al postback del listado (grupo 4 del desplegable).
HTML = ('<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc+/=" />'
        '<td><a href="../Documentos/ProcesoParlamentario/Leyes/TOMO_I/20260904_CONSTBC.PDF">'
        'CONSTITUCIÓN POLÍTICA</a></td>'
        '<td><a href="../Documentos/ProcesoParlamentario/Leyes/TOMO_I/20251230_CONSTBC.PDF">x</a></td>'
        '<td><a href="../Documentos/ProcesoParlamentario/Leyes/TOMO_I/20250101_LEYRESP.PDF">y</a></td>')


def test_elige_la_constitucion_mas_reciente():
    assert b.elegir_pdf(HTML) == ("https://www.congresobc.gob.mx/Documentos/"
                                  "ProcesoParlamentario/Leyes/TOMO_I/20260904_CONSTBC.PDF")


def test_campos_ocultos_del_formulario():
    assert b.campos_ocultos(HTML) == {"__VIEWSTATE": "abc+/="}


def test_encabezado_en_diagonal_y_pie_fuera():
    pagina = ("H. Congreso del Estado de Baja California.\nC\nD\no\nre\nc i\ni o y\n.\n"
              "Actualización Legislativa.\nÚltima Reforma P.O. No. 50, Sección II, 04-Sep-2026\n"
              "a) Los municipios;\nARTÍCULO 2.- La porción de territorio.\n"
              "Constitución Política del Estado Libre y Soberano de Baja California. Página 1")
    assert _strip_headers(pagina, b.PERFIL).splitlines() == [
        "a) Los municipios;", "ARTÍCULO 2.- La porción de territorio."]


def test_version_del_encabezado():
    assert b.version_encabezado("Última Reforma P.O. No. 50, Sección II, 04-Sep-2026") == date(2026, 9, 4)


def test_nota_al_margen_aislada():
    out = b.separar_notas("éste.\nPárrafo Reformado\nCuando las campañas")
    assert out == "éste.\n\nPárrafo Reformado\n\nCuando las campañas"

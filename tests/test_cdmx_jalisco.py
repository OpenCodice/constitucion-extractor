"""CDMX (edición de la Consejería Jurídica, notas al margen) y Jalisco (fechas de
reforma desde la tabla de reformas del final del PDF)."""
from datetime import date

from extractor.build import render_markdown
from extractor.fuentes import (CDMX, JALISCO, fechas_cdmx, reformas_tabla_jalisco,
                               version_cdmx)
from extractor.parse import parse_text


def test_cdmx_notas_al_margen_en_su_parrafo():
    texto = ("TÍTULO PRIMERO\n"
             "ARTÍCULO 3\n"
             "DE LOS PRINCIPIOS RECTORES\n"
             "1. La dignidad humana es principio rector.\n"
             "a) El respeto a los derechos humanos;\n"
             "Inciso reformado G.O. CDMX 02/09/24\n"
             "b) La rectoría del ejercicio de la función pública.\n"
             "Derogado. Párrafo derogado G.O.CDMX 23/12/24\n"
             "TÍTULO SEGUNDO CARTA\n"
             "DE DERECHOS\n"
             "CAPÍTULO I\n"
             "DE LAS NORMAS\n"
             "ARTÍCULO 4\n"
             "PRINCIPIOS\n"
             "1. En la Ciudad las personas gozan de los derechos humanos.\n"
             "Numeral reformado G.O. CDMX. 8/10/26\n")
    a3, a4 = parse_text(CDMX.preprocess(texto), perfil=CDMX)
    md3 = render_markdown(a3, perfil=CDMX)
    assert "_Inciso reformado G.O. CDMX 02/09/24_\n\nb) La rectoría" in md3
    assert "Derogado.\n\n_Párrafo derogado G.O.CDMX 23/12/24_" in md3
    assert "DE DERECHOS" not in md3          # denominación del título, no del art. 3
    assert a3.reform_dates == [date(2024, 9, 2), date(2024, 12, 23)]
    assert a4.titulo == "TÍTULO SEGUNDO"
    assert a4.reform_dates == [date(2026, 10, 8)]


def test_cdmx_fechas_solo_de_notas():
    assert fechas_cdmx("entrará en vigor el 1 de enero de 2030.") == []
    assert fechas_cdmx("texto (REFORMADO G.O. CDMX 26 DE JULIO DE 2019)\n"
                       "(FE DE ERRATAS G.O. CDMX 04 DE DICIEMBRE DE 2019)") == \
        [date(2019, 7, 26), date(2019, 12, 4)]


def test_cdmx_version_de_portada_en_dos_renglones():
    assert version_cdmx("TEXTO VIGENTE\nÚltima reforma publicada en la G.O. CDMX\n"
                        "el 8 de octubre de 2026\n") == date(2026, 10, 8)


_TABLA_JAL = """\
Artículo 117 Bis.- Texto.
TRANSITORIOS
PRIMERO.- Entrará en vigor el 1 de enero de 2027.
TABLA DE REFORMAS Y ADICIONES
11604. Se reforma el artículo 4 fracción V (arresto 36 horas), publicado en el Periódico Oficial El Estado de
Jalisco del día 15 de noviembre de 1984.
15424. Se reforman los artículos del 1 al 67, y se adicionan los artículos 68 al 112, publicado en el Periódico Oficial
El Estado de Jalisco del día 13 de julio de 1994.
17907.- Se reforma el artículo 74 en su fracción II.- Abr. 1º.de 2000. Sec. II.
18785.- Adiciona la frac. X al artículo 21 de la Constitución Política del Estado de Jalisco y reforma los arts. 18
fracción VII y 30 de la Ley Electoral del Estado.-Jun. 7 de 2001. Sec. II.
ACUERDO ECÓNOMICO NÚMERO 94/01.-Declara aprobada la minuta de decreto número 18785, por el cual se adiciona
la fracción X al artículo 22.-Aprobado May. 3 de 2001.
24859/LX/14.- Reforma los artículos 6º, 7º y 8º de la Constitución Política del Estado de Jalisco. Abr.- 10 de
2014 Sec. IV
24957/LX/14.- Se adiciona un párrafo al artículo 52 de la Constitución Política del Estado de Jalisco.- Jul. 28 de
2015 sec. II. (Acción de inconstitucionalidad 75/2015, promovida por la Procuradora General de la República.
Sep. 24 de 2016 sec. III)
29838/LXIV/25.- Se reforman los artículos 21, 35, 35 Bis, 53, 59 y 74, de la Constitución Política del Estado de
Jalisco.- Oct. 29 de 2026, sec. IX
TABLA DE ACCIONES DE INCONSTITUCIONALIDAD Y CONTROVERSIAS CONSTITUCIONALES
Acción de Inconstitucionalidad 165/2020, surtiendo efectos a partir del 30 de septiembre del 2020.
"""


def test_jalisco_fechas_de_la_tabla_de_reformas():
    r = reformas_tabla_jalisco(_TABLA_JAL)
    assert r["004"] == [date(1994, 7, 13)]          # el decreto de 1984 es de la numeración vieja
    assert r["074"] == [date(1994, 7, 13), date(2000, 4, 1), date(2026, 10, 29)]
    assert r["021"] == [date(1994, 7, 13), date(2001, 6, 7), date(2026, 10, 29)]
    assert r["018"] == [date(1994, 7, 13)]          # el 18 de la Ley Electoral no cuenta
    assert date(2001, 5, 3) not in r["022"]          # los acuerdos no son decretos
    assert r["007"][-1] == date(2014, 4, 10)
    assert r["052"][-1] == date(2015, 7, 28)         # no la fecha de la acción de inconstitucionalidad
    assert r["035-bis"] == [date(2026, 10, 29)]
    assert "113" not in r


def test_jalisco_fechas_del_articulado_no_son_reformas():
    texto = ("Artículo 52.- El 14 de junio de 2016 se instaló el Consejo.\n" + _TABLA_JAL)
    a52, _ = parse_text(texto, perfil=JALISCO)
    assert a52.reform_dates == [date(1994, 7, 13), date(2015, 7, 28)]


def test_cdmx_denominaciones_aparte_del_texto():
    texto = ("ARTÍCULO 70\n"
             "DE LA NATURALEZA INTERCULTURAL, PLURIÉTNICA, PLURILINGÜE Y\n"
             "PLURICULTURAL DE LA CIUDAD.\n"
             "1. La Ciudad de México es intercultural.\n"
             "ARTÍCULO 71\n"
             "INVIOLABILIDAD CONSTITUCIONAL\n"
             "Esta Constitución no puede ser alterada por actos de fuerza.\n"
             "A. De la función judicial\n"
             "El derecho a la buena administración de justicia estará garantizado.\n"
             "B. SE DEROGA\n"
             "(DEROGADO G.O. CDMX 26 DE JULIO DE 2019)\n")
    a70, a71 = parse_text(CDMX.preprocess(texto), perfil=CDMX)
    assert render_markdown(a70, perfil=CDMX).split("\n\n")[1] == (
        "DE LA NATURALEZA INTERCULTURAL, PLURIÉTNICA, PLURILINGÜE Y PLURICULTURAL DE LA CIUDAD.")
    assert render_markdown(a71, perfil=CDMX).split("\n\n")[1:] == [
        "INVIOLABILIDAD CONSTITUCIONAL",
        "Esta Constitución no puede ser alterada por actos de fuerza.",
        "A. De la función judicial",
        "El derecho a la buena administración de justicia estará garantizado.",
        "B. SE DEROGA (DEROGADO G.O. CDMX 26 DE JULIO DE 2019)\n"]

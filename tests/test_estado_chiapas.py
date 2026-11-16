"""Perfil de Chiapas: pruebas sin PDF."""
from datetime import date

from extractor.estados import chiapas as c


def test_version_de_la_portada():
    portada = ("ÚLTIMA REFORMA PUBLICADA MEDIANTE PERIÓDICO OFICIAL NÚMERO 135, DE\n"
               "FECHA 30 DE SEPTIEMBRE DEL 2026. DECRETO NÚMERO 312.\n")
    assert c.version_portada(portada) == date(2026, 9, 30)


def test_cita_partida_no_es_inciso():
    out = c.preparar("se procederá en los términos del artículo\n55.\nArtículo 59. Son")
    assert "del artículo 55.\n" in out


def test_nota_partida_queda_en_un_renglon_aislado():
    texto = ("17. Cacahoatán.\n"
             "(REFORMA PUBLICADA MEDIANTE P.O. NUM. 316, SEGUNDA SECCIÓN DE FECHA 06 DE SEPTIEMBRE DE\n"
             "2017)\n18. Capitán Luis Ángel Vidal\n")
    assert ("\n\n(REFORMA PUBLICADA MEDIANTE P.O. NUM. 316, SEGUNDA SECCIÓN DE FECHA 06 DE "
            "SEPTIEMBRE DE 2017)\n\n18.") in c.preparar(texto)

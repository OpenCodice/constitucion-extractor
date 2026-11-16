"""Guanajuato: resolver sobre el listado del bucket S3 y cierre del articulado (sin PDF ni red)."""
from datetime import date

import pytest

from extractor.estados.guanajuato import (PERFIL, RESOLVER, elegir_del_bucket,
                                          objetos_de_listado, version_encabezado)
from extractor.parse import parse_text

# Página de ListObjects del bucket del Congreso (recortada de la real, nov. 2026).
_OBJ = ("<Contents><Key>{}</Key><LastModified>{}</LastModified><Size>1</Size>"
        "<StorageClass>STANDARD</StorageClass></Contents>")
_FILAS = [
    ("uploads/reforma/pdf/3719/CPG_REF_27Mayo2026.pdf", "2026-06-01T17:07:34.000Z"),
    ("uploads/reforma/pdf/3719/8c4bc1c7-6806-439c-83fb-bf7fb4040c76.pdf", "2026-07-02T18:45:13.000Z"),
    ("uploads/reforma/pdf/3731/CPELYSG_REF_04Agosto2026.pdf", "2026-08-05T19:26:28.000Z"),
    ("uploads/reforma/pdf/3732/LFAFEG_REF_15Octubre2026.pdf", "2026-10-16T10:00:00.000Z"),
    ("uploads/reforma/pdf/3740/CPEG_REF_10Nov2026.pdf", "2026-11-10T10:00:00.000Z"),
    ("uploads/reforma/pdf/740/20200625.pdf", "2020-06-25T10:00:00.000Z"),
]
XML = ('<?xml version="1.0" encoding="UTF-8"?>'
       '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
       "<Name>congreso-gto</Name><Prefix>uploads/reforma/pdf/</Prefix>"
       "<IsTruncated>true</IsTruncated>"
       + "".join(_OBJ.format(*f) for f in _FILAS) + "</ListBucketResult>").encode()

URL = "https://congreso-gto.s3.amazonaws.com/uploads/reforma/pdf/"


def _sin_descargas(url):
    raise AssertionError(f"no debía descargar {url}")


def test_lee_el_listado():
    objetos, mas = objetos_de_listado(XML)
    assert mas and len(objetos) == len(_FILAS)
    assert objetos[2] == _FILAS[2]


def test_elige_por_nombre_sin_descargar():
    # 3740 es el Código Penal (CPEG_), 3732 otra ley; 740 es menor aunque
    # ordene después como texto.
    objetos, _ = objetos_de_listado(XML)
    assert elegir_del_bucket(objetos, _sin_descargas) == URL + "3731/CPELYSG_REF_04Agosto2026.pdf"


def test_uuid_se_reconoce_por_el_titulo():
    otra = "uploads/reforma/pdf/3741/0b1c2d3e-0000-4000-8000-000000000001.pdf"
    const = "uploads/reforma/pdf/3742/0b1c2d3e-0000-4000-8000-000000000002.pdf"
    objetos = [(otra, "2026-11-12T00:00:00.000Z"), (const, "2026-11-13T00:00:00.000Z")]
    pdfs = {URL + "3741/0b1c2d3e-0000-4000-8000-000000000001.pdf": b"%PDF /Title(CPEG) ...",
            URL + "3742/0b1c2d3e-0000-4000-8000-000000000002.pdf": b"%PDF /Title(CPG) ..."}
    assert elegir_del_bucket(objetos, pdfs.__getitem__) == URL + const.split("pdf/", 1)[1]
    # Si la Constitución no aparece, cae a la del alta (3731) en vez de a otra ley.
    objetos.pop()
    objetos.append(_FILAS[2])
    assert elegir_del_bucket(objetos, pdfs.__getitem__).endswith("3731/CPELYSG_REF_04Agosto2026.pdf")


def test_sin_constitucion_falla():
    with pytest.raises(SystemExit):
        elegir_del_bucket([_FILAS[3]], _sin_descargas)


def test_resolver_es_funcion():
    assert RESOLVER["tipo"] == "funcion" and callable(RESOLVER["funcion"])


def test_version_del_encabezado():
    linea = ("Instituto de Investigaciones Legislativas Reforma: P.O. Número 154; "
             "Segunda Parte; Decreto:204; 04-08-2026")
    assert version_encabezado(linea) == date(2026, 8, 4)


def test_articulado_termina_en_transitorios_con_punto():
    texto = ("ARTICULO 147.- Esta Constitución no perderá su fuerza.\n"
             "Artículos transitorios.\n"
             "Art. 1º Esta Constitución se publicará por bando solemne.\n")
    (art,) = parse_text(texto, perfil=PERFIL)
    assert "transitorios" not in art.body

"""`scripts/vencimiento.py`: el aviso de `credenciales.yml` antes de que una credencial venza."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("vencimiento", RAIZ / "scripts" / "vencimiento.py")
vencimiento = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vencimiento)

AHORA = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("texto, esperado", [
    # La cabecera github-authentication-token-expiration, con UTC o con zona.
    ("2027-11-20 06:00:00 UTC", "2027-11-20T06:00:00"),
    ("2027-11-20 00:00:00 -0600", "2027-11-20T06:00:00"),
    ("2027-11-20 11:30:00 +05:30", "2027-11-20T06:00:00"),
    # `expires_on` de Cloudflare y la variable CLAUDE_TOKEN_VENCE.
    ("2027-11-20T06:00:00Z", "2027-11-20T06:00:00"),
    ("2027-11-20T06:00:00.123456Z", "2027-11-20T06:00:00"),
    ("2027-11-15", "2027-11-15T00:00:00"),
    (" 2027-11-15\n", "2027-11-15T00:00:00"),
])
def test_leer_fecha(texto, esperado):
    assert vencimiento.leer_fecha(texto).strftime("%Y-%m-%dT%H:%M:%S") == esperado


@pytest.mark.parametrize("texto", ["pronto", "15/11/2027", "2027-13-40", "2027-11-15 6pm"])
def test_fecha_ilegible_falla(texto):
    with pytest.raises(ValueError):
        vencimiento.leer_fecha(texto)
    vigente, linea = vencimiento.revisar("X", texto, AHORA)
    assert not vigente and linea.startswith("::error::Credencial por renovar: no se entiende cuándo vence X")


@pytest.mark.parametrize("faltan_dias, vigente", [(400, True), (30.1, True), (29.9, False), (1, False), (-1, False)])
def test_umbral_de_30_dias(faltan_dias, vigente):
    fecha = (AHORA + timedelta(days=faltan_dias)).strftime("%Y-%m-%d %H:%M:%S UTC")
    ok, linea = vencimiento.revisar("PR_TOKEN", fecha, AHORA, renovar="gh secret set PR_TOKEN")
    assert ok is vigente
    if vigente:
        assert not linea.startswith("::") and "OK" in linea
    else:
        assert linea.startswith("::error::Credencial por renovar: PR_TOKEN ")
        assert fecha[:16] in linea and "Cómo: gh secret set PR_TOKEN" in linea
        assert ("venció el" if faltan_dias < 0 else "vence el") in linea


def test_el_error_no_cambia_de_un_dia_a_otro():
    """El supervisor identifica la falla por esta línea: con la misma fecha tiene que ser la misma."""
    fecha = "2026-12-08 06:00:00 UTC"
    assert vencimiento.revisar("X", fecha, AHORA)[1] == vencimiento.revisar("X", fecha, AHORA + timedelta(days=6))[1]


def test_sin_fecha_solo_avisa():
    assert vencimiento.revisar("PR_TOKEN", "", AHORA) == (True, "::notice::PR_TOKEN: no vence")
    ok, linea = vencimiento.revisar("CLAUDE", "  ", AHORA, sin_fecha="no se conoce su fecha de vencimiento")
    assert ok and linea == "::notice::CLAUDE: no se conoce su fecha de vencimiento"


def test_cloudflare():
    revisar = lambda respuesta: vencimiento.revisar_cloudflare("CLOUDFLARE_API_TOKEN", respuesta, AHORA)  # noqa: E731
    activo = {"success": True, "errors": [], "result": {"id": "x", "status": "active"}}
    assert revisar(activo) == (True, "::notice::CLOUDFLARE_API_TOKEN: activo en Cloudflare y no vence")
    assert revisar(activo | {"result": {"status": "active", "expires_on": "2027-11-20T00:00:00Z"}})[0]
    ok, linea = revisar(activo | {"result": {"status": "active", "expires_on": "2026-12-01T00:00:00Z"}})
    assert not ok and "CLOUDFLARE_API_TOKEN vence el 2026-12-01 00:00 UTC, en menos de 30 días" in linea
    for respuesta, motivo in [
        (activo | {"result": {"status": "disabled"}}, "disabled"),
        (activo | {"result": {"status": "expired"}}, "expired"),
        ({"success": False, "errors": [{"code": 1000, "message": "Invalid API Token"}], "messages": [], "result": None},
         "Invalid API Token"),
        ({}, "sin respuesta válida"),
    ]:
        ok, linea = revisar(respuesta)
        assert not ok and linea.startswith(f"::error::Credencial por renovar: CLOUDFLARE_API_TOKEN no está activo en Cloudflare ({motivo})")


def test_linea_de_comandos(tmp_path, capsys):
    assert vencimiento.main(["fecha", "X", "", "--sin-fecha", "no vence"]) == 0
    assert vencimiento.main(["fecha", "X", "2020-01-01"]) == 1
    assert "::error::Credencial por renovar: X venció el 2020-01-01 00:00 UTC." in capsys.readouterr().out
    respuesta = tmp_path / "r.json"
    respuesta.write_text(json.dumps({"success": True, "result": {"status": "active"}}), encoding="utf-8")
    assert vencimiento.main(["cloudflare", "CF", str(respuesta)]) == 0
    capsys.readouterr()
    # Una respuesta que no se pudo leer no es una credencial vencida.
    respuesta.write_text("<html>502</html>", encoding="utf-8")
    assert vencimiento.main(["cloudflare", "CF", str(respuesta)]) == 1
    assert "Credencial por renovar" not in capsys.readouterr().out

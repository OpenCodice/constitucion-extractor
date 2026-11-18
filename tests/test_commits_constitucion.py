"""Commit(s) con trailers de una constitución regenerada
(scripts/commits_constitucion.py) y su validación (scripts/validar_commits.py)."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, _SCRIPTS / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _cargar("commits_constitucion")
vc = _cargar("validar_commits")
tr = _cargar("trailers")

DOC = "jalisco/constitucion"
FUENTE = "Periódico Oficial del Estado de Jalisco — Congreso del Estado de Jalisco"


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True,
                          text=True).stdout


def _escribir(raiz: Path, pdf: str, version: str, corregir: bool):
    """Extractor de juguete: el 'PDF' es `clave|cuerpo` por línea; el extractor
    nuevo (`corregir`) arregla una errata de lectura."""
    art = raiz / "articulos"
    art.mkdir(parents=True, exist_ok=True)
    for f in art.glob("*.md"):
        f.unlink()
    fechas = set()
    for l in Path(pdf).read_text().splitlines():
        clave, cuerpo = l.split("|")
        if corregir:
            cuerpo = cuerpo.replace("lectrua", "lectura")
        if "reformado" in cuerpo:
            fechas.add(version)
        (art / f"{clave}.md").write_text(f"# Artículo {int(clave)}\n\n{cuerpo}\n")
    (raiz / "metadata").mkdir(exist_ok=True)
    (raiz / "metadata" / "articulos.json").write_text(json.dumps(
        {"fuente": FUENTE, "version": version, "articulos": []}))
    (raiz / "metadata" / "reformas.json").write_text(json.dumps({f: [] for f in fechas}))
    (raiz / "metadata" / "pasajes.jsonl").write_text(
        json.dumps({"url_fuente": "https://x/vieja.pdf"}) + "\n")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "datos"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    raiz = r / DOC
    (raiz / "fuente").mkdir(parents=True)
    viejo = tmp_path / "viejo.pdf"
    viejo.write_text("001|Una lectrua.\n002|Dos.\n")
    _escribir(raiz, str(viejo), "2026-09-01", corregir=False)
    (raiz / "fuente" / "constitucion.pdf").write_bytes(viejo.read_bytes())
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "publicado")
    monkeypatch.setattr(cc, "construir", lambda raiz, pdf, perfil, url, version: (
        _escribir(raiz, pdf, version or "2026-09-01", corregir=True), True)[1])
    return r


def _regenerar_y_commit(repo, tmp_path, pdf_texto, version):
    pdf = tmp_path / "nuevo.pdf"
    pdf.write_text(pdf_texto)
    _escribir(repo / DOC, str(pdf), version, corregir=True)
    base = _git(repo, "rev-parse", "HEAD").strip()
    cc.main([str(repo), "--documento", DOC, "--perfil", "jalisco", "--pdf", str(pdf),
             "--url", "https://x/nueva.pdf", "--version", version,
             "--extractor-dir", str(Path(__file__).resolve().parent.parent)])
    assert not _git(repo, "status", "--porcelain")
    assert vc.main(str(repo), base) == 0
    return [tr.parsear(_git(repo, "log", "-1", "--format=%B", c)) for c in
            _git(repo, "rev-list", "--reverse", f"{base}..HEAD").split()]


def test_correccion_y_reforma_separadas(repo, tmp_path):
    commits = _regenerar_y_commit(repo, tmp_path, "001|Una lectrua.\n002|Dos reformado.\n",
                                  "2026-10-29")
    assert [t for t, _ in commits] == ["Corrección de extracción jalisco: art. 1",
                                       "Reforma jalisco (P.O. 2026-10-29): art. 2"]
    cor, ref = dict(commits[0][1]), dict(commits[1][1])
    assert cor["Fuente"] == "https://x/vieja.pdf"
    assert cor["Fuente-Sha256"] == tr.sha256_bytes(b"001|Una lectrua.\n002|Dos.\n")
    assert ref["Fuente"] == "https://x/nueva.pdf" and ref["Publicacion-Origen"] == "notas"
    assert ref["Medio"] == "Periódico Oficial del Estado de Jalisco"
    assert (repo / DOC / "fuente" / "constitucion.pdf").read_text().endswith("reformado.\n")


def test_mismo_pdf_es_correccion(repo, tmp_path):
    commits = _regenerar_y_commit(repo, tmp_path, "001|Una lectrua.\n002|Dos.\n", "2026-09-01")
    assert [t for t, _ in commits] == ["Corrección de extracción jalisco: art. 1"]


def test_solo_metadata_es_metadatos(repo, tmp_path):
    pdf = repo / DOC / "fuente" / "constitucion.pdf"
    base = _git(repo, "rev-parse", "HEAD").strip()
    meta = repo / DOC / "metadata" / "articulos.json"
    meta.write_text(json.dumps({"fuente": "Periódico Oficial del Estado de Jalisco — otro",
                                "version": "2026-09-01", "articulos": []}))
    cc.main([str(repo), "--documento", DOC, "--perfil", "jalisco", "--pdf", str(pdf),
             "--url", "https://x/vieja.pdf",
             "--extractor-dir", str(Path(__file__).resolve().parent.parent)])
    assert vc.main(str(repo), base) == 0
    _, t = tr.parsear(_git(repo, "log", "-1", "--format=%B"))
    assert tr.valor(t, "Tipo") == "metadatos"
    assert _git(repo, "log", "-1", "--format=%s").strip() == "Metadatos de jalisco: articulos.json"


def _con_registro(repo, tmp_path, pdf_texto, version, registro):
    pdf = tmp_path / "nuevo.pdf"
    pdf.write_text(pdf_texto)
    _escribir(repo / DOC, str(pdf), version, corregir=True)
    base = _git(repo, "rev-parse", "HEAD").strip()
    cc.main([str(repo), "--documento", DOC, "--perfil", "jalisco", "--pdf", str(pdf),
             "--url", "https://x/nueva.pdf", "--version", version,
             "--extractor-dir", str(Path(__file__).resolve().parent.parent),
             "--verificadas", str(registro)])
    return base


def test_correccion_sin_confirmar_no_se_publica(repo, tmp_path):
    base = _con_registro(repo, tmp_path, "001|Una lectrua.\n002|Dos reformado.\n",
                         "2026-10-29", tmp_path / "registro")
    assert _git(repo, "rev-parse", "HEAD").strip() == base
    assert not _git(repo, "status", "--porcelain")


def test_correccion_confirmada_se_publica(repo, tmp_path):
    im = cc.impacto
    antes = (repo / DOC / "articulos" / "001.md").read_text()
    viejo = (repo / DOC / "fuente" / "constitucion.pdf").read_bytes()
    entrada = {"documento": DOC, "clave": "001", "pdf": tr.sha256_bytes(viejo),
               "antes": im.huella(antes), "despues": im.huella(antes.replace("lectrua", "lectura")),
               "veredicto": "mejora"}
    im.escribir([entrada], tmp_path / "registro", "prueba")
    base = _con_registro(repo, tmp_path, "001|Una lectrua.\n002|Dos reformado.\n",
                         "2026-10-29", tmp_path / "registro")
    assert len(_git(repo, "rev-list", f"{base}..HEAD").split()) == 2
    assert im.main(["exigir", str(repo), "--base", base,
                    "--registro", str(tmp_path / "registro")]) == 0


def test_restaurar_no_esconde_un_cambio_del_mismo_tamano(tmp_path):
    """Un artículo corregido del mismo tamaño ('lectrua' → 'lectura') restaurado
    con la fecha de su origen, igual en segundos a la del índice, no lo veía
    `git status` (con un inodo reutilizado y el mismo ctime, en Linux).
    checkStat=minimal y trustctime=false reproducen ese caso en cualquier
    sistema."""
    import os
    import time
    repo = tmp_path / "repo"
    repo.mkdir()
    for a in (("init", "-q"), ("config", "user.email", "t@t"), ("config", "user.name", "t"),
              ("config", "core.checkStat", "minimal"), ("config", "core.trustctime", "false")):
        _git(repo, *a)
    f = repo / DOC / "articulos" / "001.md"
    f.parent.mkdir(parents=True)
    f.write_text("Una lectrua.\n")
    mtime = f.stat().st_mtime_ns
    time.sleep(1.05)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "x")
    origen = tmp_path / "origen"
    (origen / DOC / "articulos").mkdir(parents=True)
    (origen / DOC / "articulos" / "001.md").write_text("Una lectura.\n")
    os.utime(origen / DOC / "articulos" / "001.md", ns=(mtime, mtime))
    cc._restaurar(str(repo), DOC, origen)
    assert cc.cambios(str(repo), DOC) == [f"{DOC}/articulos/001.md"]

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

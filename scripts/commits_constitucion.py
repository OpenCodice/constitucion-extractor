#!/usr/bin/env python3
"""Hace el commit (o los dos) de una constitución regenerada, con sus trailers.

La vigilancia ya regeneró la carpeta del documento con el extractor actual y el
PDF nuevo. El tipo del commit sale de la causa, nunca del agente
(scripts/trailers.py):

- mismo archivo oficial que el guardado en `fuente/` → corrección de extracción;
- archivo distinto → se reconstruye el PDF anterior (el de `fuente/`) con el
  extractor actual. Lo que eso cambia respecto de lo publicado es una
  corrección y va primero, con la fuente anterior; lo que falta para llegar al
  texto nuevo es la reforma, que trae el PDF nuevo a `fuente/`;
- documento que no existía → alta.

Si la corrección no toca el texto de ningún artículo es `metadatos`. Con
`--verificadas`, una corrección solo se publica si cada artículo que cambia
está confirmado como mejora en el registro de `scripts/impacto.py`; si no, el
documento no se publica en esta corrida (ni su reforma, que se construyó con
el mismo extractor) y queda como estaba.

Uso:
  commits_constitucion.py <repo> --documento cpeum|<estado>/constitucion \\
      --perfil P --pdf NUEVO.pdf [--doc NUEVO.doc] --url URL [--version V] \\
      [--extractor-dir D] [--verificadas verificaciones/impacto]

`--doc`: el estado publica Word; su sha256 es el de la fuente y se guarda junto
al PDF convertido. `--version`: la versión se pasó explícita al extractor (la
fecha va en el nombre del archivo); la reconstrucción del PDF anterior usa la
versión publicada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import impacto  # noqa: E402
import trailers as tr  # noqa: E402

EXTRACTOR = Path(__file__).resolve().parent.parent


def _git(repo: str, *args: str, check: bool = True) -> str:
    return subprocess.run(["git", "-C", repo, *args], check=check, capture_output=True,
                          text=True).stdout


def sha256(ruta: str | Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def rutas_documento(documento: str) -> list[str]:
    return ["articulos", "metadata", "fuente"] if documento == "cpeum" else [documento]


def raiz_documento(repo: str, documento: str) -> Path:
    return Path(repo) if documento == "cpeum" else Path(repo) / documento


def cambios(repo: str, documento: str) -> list[str]:
    salida = _git(repo, "status", "--porcelain", "-z", "--no-renames", "-uall", "--",
                  *rutas_documento(documento))
    return [e[3:] for e in salida.split("\0") if e]


def _articulos_cambiados(repo: str, documento: str) -> bool:
    base = "articulos" if documento == "cpeum" else f"{documento}/articulos"
    return bool(_git(repo, "status", "--porcelain", "-uall", "--", base).strip())


def commit(repo: str, documento: str, tipo: str, *, fuente: str, sha: str, extractor: str,
           separacion: str | None = None) -> str:
    rutas = cambios(repo, documento)
    if tipo == "correccion":
        tipo = tr.tipo_sin_reforma(documento, rutas, tr.lector_git(repo, "HEAD"), tr.lector_fs(repo))
    msg = tr.mensaje(documento, tipo, rutas, tr.lector_git(repo, "HEAD"), tr.lector_fs(repo),
                     fuente=fuente, fuente_sha256=sha, extractor=extractor,
                     separacion=separacion)
    _git(repo, "add", "-A", "--", *rutas)
    _git(repo, "commit", "-q", "-m", msg)
    titulo = msg.split("\n", 1)[0]
    print(f"{tipo}: {titulo}")
    return tipo


def construir(raiz: Path, pdf: str, perfil: str, url: str | None, version: str | None) -> bool:
    cmd = [sys.executable, "-m", "extractor", "build", "--pdf", pdf, "--out", str(raiz),
           "--perfil", perfil]
    if url:
        cmd += ["--url-fuente", url]
    if version:
        cmd += ["--version", version]
    r = subprocess.run(cmd, cwd=EXTRACTOR, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(EXTRACTOR)})
    if r.returncode != 0:
        print(f"  · no se pudo reconstruir el PDF anterior: "
              f"{(r.stderr.strip().splitlines() or [''])[-1][:200]}")
    return r.returncode == 0


def _guardar(repo: str, documento: str, destino: Path) -> None:
    for rel in rutas_documento(documento):
        if (Path(repo) / rel).exists():
            shutil.copytree(Path(repo) / rel, destino / rel)


def _restaurar(repo: str, documento: str, origen: Path) -> None:
    for rel in rutas_documento(documento):
        if (Path(repo) / rel).exists():
            shutil.rmtree(Path(repo) / rel)
        if (origen / rel).exists():
            shutil.copytree(origen / rel, Path(repo) / rel)


def sin_confirmar(repo: str, documento: str, pdf_sha: str, registro: dict | None) -> list[str]:
    """Artículos de la corrección que hay ahora en el árbol que el registro no
    confirma como mejora (vacío si no se exige)."""
    if registro is None:
        return []
    corregidos = tr.cambios_de_articulos(documento, cambios(repo, documento),
                                         tr.lector_git(repo, "HEAD"), tr.lector_fs(repo))
    return impacto.faltantes(registro, documento, pdf_sha, corregidos)


def retener(repo: str, documento: str, faltan: list[str]) -> None:
    _git(repo, "checkout", "-q", "HEAD", "--", *rutas_documento(documento), check=False)
    _git(repo, "clean", "-fdq", "--", *rutas_documento(documento))
    print(f"retenido: la corrección de {documento} no está confirmada contra el PDF "
          f"(arts. {', '.join(faltan[:12])}); no se publica en esta corrida")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write("retenido=true\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--documento", required=True)
    ap.add_argument("--perfil", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--doc", default=None)
    ap.add_argument("--url", required=True)
    ap.add_argument("--version", default=None)
    ap.add_argument("--extractor-dir", default=str(EXTRACTOR))
    ap.add_argument("--extractor-repo", default="constitucion-extractor")
    ap.add_argument("--verificadas", default=None,
                    help="registro de correcciones confirmadas (scripts/impacto.py)")
    a = ap.parse_args(argv)
    registro = impacto.cargar(a.verificadas) if a.verificadas else None

    repo, doc = a.repo, a.documento
    raiz = raiz_documento(repo, doc)
    extractor = tr.extractor_id(a.extractor_repo,
                                _git(a.extractor_dir, "rev-parse", "HEAD").strip())
    fuente_dir = raiz / "fuente"
    pdf_dest = fuente_dir / ("CPEUM.pdf" if doc == "cpeum" else "constitucion.pdf")
    doc_dest = fuente_dir / "constitucion.doc"
    nuevo_sha = sha256(a.doc or a.pdf)
    antes = tr.lector_git(repo, "HEAD")
    rel = lambda p: str(p.relative_to(repo))  # noqa: E731
    viejo = antes(rel(doc_dest)) if a.doc else None
    viejo = viejo if viejo is not None else antes(rel(pdf_dest))
    viejo_sha = tr.sha256_bytes(viejo) if viejo is not None else None

    def traer_fuente() -> None:
        fuente_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a.pdf, pdf_dest)
        if a.doc:
            shutil.copyfile(a.doc, doc_dest)

    hechos: list[str] = []
    if not cambios(repo, doc):
        print("Sin cambios.")
    elif tr.tipo_por_existencia(doc, antes, tr.lector_fs(repo)) == "alta":
        traer_fuente()
        hechos.append(commit(repo, doc, "alta", fuente=a.url, sha=nuevo_sha, extractor=extractor))
    elif viejo_sha is None:
        # Sin la fuente anterior guardada no hay con qué separar.
        traer_fuente()
        hechos.append(commit(repo, doc, "reforma", fuente=a.url, sha=nuevo_sha,
                             extractor=extractor, separacion="no-disponible"))
    elif viejo_sha == nuevo_sha:
        faltan = sin_confirmar(repo, doc, viejo_sha, registro)
        if faltan:
            retener(repo, doc, faltan)
        else:
            hechos.append(commit(repo, doc, "correccion", fuente=a.url, sha=nuevo_sha,
                                 extractor=extractor))
    else:
        separacion = None
        faltan = []
        with tempfile.TemporaryDirectory() as tmp:
            final = Path(tmp) / "final"
            _guardar(repo, doc, final)
            _git(repo, "checkout", "-q", "HEAD", "--", *rutas_documento(doc))
            _git(repo, "clean", "-fdq", "--", *rutas_documento(doc))
            pdf_viejo = Path(tmp) / "anterior.pdf"
            pdf_viejo.write_bytes(antes(rel(pdf_dest)))
            idx = json.loads(antes(rel(raiz / "metadata" / "articulos.json")) or b"{}")
            pasajes = (antes(rel(raiz / "metadata" / "pasajes.jsonl")) or b"").split(b"\n", 1)[0]
            url_vieja = json.loads(pasajes).get("url_fuente") if pasajes.strip() else None
            if construir(raiz, str(pdf_viejo), a.perfil, url_vieja,
                         idx.get("version") if a.version else None):
                faltan = sin_confirmar(repo, doc, viejo_sha, registro)
                if _articulos_cambiados(repo, doc) and not faltan:
                    hechos.append(commit(repo, doc, "correccion", fuente=url_vieja or a.url,
                                         sha=viejo_sha, extractor=extractor))
            else:
                separacion = "no-disponible"
            _restaurar(repo, doc, final)
        if faltan:
            # La reforma salió del mismo extractor: tampoco se publica.
            retener(repo, doc, faltan)
        else:
            traer_fuente()
            hechos.append(commit(repo, doc, "reforma", fuente=a.url, sha=nuevo_sha,
                                 extractor=extractor, separacion=separacion))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"tipo={'reforma' if {'reforma', 'alta'} & set(hechos) else 'correccion'}\n")
            fh.write(f"commits={len(hechos)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

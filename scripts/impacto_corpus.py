#!/usr/bin/env python3
"""Impacto del extractor, tal como está en disco, sobre todo lo publicado.

Reconstruye cada constitución publicada (la CPEUM y las estatales) desde el
PDF que guarda su `fuente/` en el repo de datos, compara artículo por artículo
contra el texto publicado (HEAD del repo de datos, no su árbol de trabajo) y
deja en `--trabajo` las correcciones que eso produciría y que el registro de
`scripts/impacto.py` aún no confirma (`pendientes.json`, para
`scripts/agente/impacto.sh`). También audita, en cada documento que cambia, la
cobertura antes y después: un documento con artículos nuevos con problemas es
una regresión y el cambio del extractor no puede entrar.

Sale 0 si no queda nada por verificar ni hay regresiones, 1 si hay correcciones
por verificar, 2 si hay regresiones de cobertura o documentos que no se
pudieron reconstruir.

Uso:
  impacto_corpus.py --trabajo T [--cpeum REPO] [--estatales REPO] [--solo DOC]...
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import impacto  # noqa: E402
import trailers as tr  # noqa: E402

EXTRACTOR = Path(__file__).resolve().parent.parent
ORG = "https://github.com/OpenCodice"


def _git(repo, *args, binario=False):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
    return r.stdout if binario else r.stdout.decode("utf-8")


def clonar(nombre: str, destino: Path) -> Path:
    if not (destino / ".git").exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"{ORG}/{nombre}.git", str(destino)],
                       check=True)
    return destino


def documentos(cpeum: Path | None, estatales: Path | None) -> list[dict]:
    """Cada constitución publicada: su repo, su documento y su perfil."""
    sys.path.insert(0, str(EXTRACTOR))
    from extractor.fuentes import FUENTES
    docs = []
    if cpeum:
        docs.append({"repo": cpeum, "documento": "cpeum", "perfil": "cpeum"})
    if estatales:
        for d in sorted(x for x in _git(estatales, "ls-tree", "-d", "-z", "--name-only",
                                            "HEAD").split("\0") if x):
            documento = f"{d}/constitucion"
            pdf = f"{documento}/fuente/constitucion.pdf"
            if d in FUENTES and tr.lector_git(str(estatales), "HEAD")(pdf) is not None:
                docs.append({"repo": estatales, "documento": documento, "perfil": d})
    return docs


def _publicado(repo: Path, documento: str, destino: Path) -> dict[str, bytes]:
    """Artículos publicados (HEAD) y, en `destino`, una copia con lo que el
    extractor lee además del PDF (fuente/ruido.json) para auditarla."""
    base = tr._dir_articulos(documento)
    raiz = "" if documento == "cpeum" else f"{documento}/"
    arts = {}
    (destino / "articulos").mkdir(parents=True, exist_ok=True)
    for r in _git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--",
                  base.rstrip("/")).split("\0"):
        clave = tr.clave_articulo(r, documento)
        if clave is not None:
            arts[clave] = _git(repo, "show", f"HEAD:{r}", binario=True)
            (destino / "articulos" / f"{clave}.md").write_bytes(arts[clave])
    ruido = tr.lector_git(str(repo), "HEAD")(f"{raiz}fuente/ruido.json")
    if ruido is not None:
        (destino / "fuente").mkdir(exist_ok=True)
        (destino / "fuente" / "ruido.json").write_bytes(ruido)
    return arts


def _extraer(cmd: list[str]) -> str | None:
    r = subprocess.run(cmd, cwd=EXTRACTOR, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(EXTRACTOR)})
    return None if r.returncode == 0 else (r.stderr.strip().splitlines() or ["?"])[-1][:300]


def _auditar(pdf: str, out: Path, perfil: str) -> set[str] | None:
    salida = out / "auditoria.json"
    if _extraer([sys.executable, "-m", "extractor", "auditar", "--pdf", pdf, "--out", str(out),
                 "--perfil", perfil, "--json", str(salida)]) is not None:
        return None
    return set(json.loads(salida.read_text(encoding="utf-8"))["con_problemas"])


def evaluar(d: dict, trabajo: Path) -> dict:
    repo, documento, perfil = d["repo"], d["documento"], d["perfil"]
    nombre = documento.replace("/", "__")
    publicado_dir, nuevo_dir = trabajo / "publicado" / nombre, trabajo / "nuevo" / nombre
    for p in (publicado_dir, nuevo_dir):
        shutil.rmtree(p, ignore_errors=True)
    publicado = _publicado(repo, documento, publicado_dir)
    leer = tr.lector_git(str(repo), "HEAD")
    pdf_bytes = next(leer(r) for r in tr.rutas_fuente(documento)
                     if r.endswith(".pdf") and leer(r) is not None)
    pdf = trabajo / "pdfs" / f"{nombre}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(pdf_bytes)
    meta = tr._dir_metadata(documento)
    idx = tr._json(leer, meta + "articulos.json") or {}
    if (publicado_dir / "fuente").exists():
        shutil.copytree(publicado_dir / "fuente", nuevo_dir / "fuente")
    cmd = [sys.executable, "-m", "extractor", "build", "--pdf", str(pdf), "--out", str(nuevo_dir),
           "--perfil", perfil, "--only", "text"]
    if idx.get("version"):
        cmd += ["--version", idx["version"]]
    error = _extraer(cmd)
    res = {"documento": documento, "pdf_sha256": tr.sha256_bytes(pdf_bytes), "pdf": str(pdf),
           "error": error, "cambios": [], "regresiones": []}
    if error:
        return res
    nuevo = {p.stem: p.read_bytes() for p in (nuevo_dir / "articulos").glob("*.md")}
    for clave in sorted(set(publicado) | set(nuevo)):
        a, b = publicado.get(clave), nuevo.get(clave)
        if a != b:
            res["cambios"].append((clave, a.decode("utf-8") if a is not None else None,
                                   b.decode("utf-8") if b is not None else None))
    if res["cambios"]:
        antes, despues = _auditar(str(pdf), publicado_dir, perfil), _auditar(str(pdf), nuevo_dir, perfil)
        if antes is None or despues is None:
            res["error"] = "no se pudo auditar"
        else:
            res["regresiones"] = sorted(despues - antes)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--trabajo", required=True)
    ap.add_argument("--cpeum", default=None, help="clon de constitucion-mexicana (si no, se clona)")
    ap.add_argument("--estatales", default=None, help="clon de leyes-estatales (si no, se clona)")
    ap.add_argument("--solo", action="append", help="limitar a estos documentos")
    ap.add_argument("--registro", default=str(impacto.REGISTRO))
    ap.add_argument("--procesos", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args(argv)

    t = Path(a.trabajo)
    t.mkdir(parents=True, exist_ok=True)
    cpeum = Path(a.cpeum) if a.cpeum else clonar("constitucion-mexicana", t / "clones" / "cpeum")
    estatales = Path(a.estatales) if a.estatales else clonar("leyes-estatales", t / "clones" / "estatales")
    docs = [d for d in documentos(cpeum, estatales) if not a.solo or d["documento"] in a.solo]
    with ThreadPoolExecutor(max_workers=max(1, a.procesos)) as pool:
        resultados = list(pool.map(lambda d: evaluar(d, t), docs))

    cambios = [impacto.Cambio(r["documento"], c, r["pdf_sha256"], x, y)
               for r in resultados for c, x, y in r["cambios"]]
    pdfs = {r["pdf_sha256"]: r["pdf"] for r in resultados}
    resumen = impacto.exportar(cambios, t, pdfs, registro=impacto.cargar(a.registro),
                               origen="el extractor de este repo con cambios sin publicar")
    errores = [f"{r['documento']}: {r['error']}" for r in resultados if r["error"]]
    regresiones = [f"{r['documento']}: {', '.join(r['regresiones'][:10])}"
                   for r in resultados if r["regresiones"]]
    tocados = sorted({c.documento for c in cambios})
    informe = {"documentos": len(docs), "tocados": tocados, "errores": errores,
               "regresiones": regresiones, **resumen}
    (t / "resumen.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1) + "\n",
                                    encoding="utf-8")
    print(f"{len(docs)} documentos reconstruidos; cambian {len(cambios)} artículos en "
          f"{len(tocados)} ({', '.join(tocados[:8])}); {resumen['ya_mejora']} ya confirmados, "
          f"{resumen['pendientes']} por verificar en {resumen['grupos']} grupos.")
    for e in errores:
        print(f"✗ {e}")
    for r in regresiones:
        print(f"✗ regresión de cobertura en {r}")
    if resumen["ya_empeora"] or resumen["ya_incierto"]:
        print(f"✗ reproduce correcciones ya rechazadas: "
              f"{', '.join((resumen['ya_empeora'] + resumen['ya_incierto'])[:10])}")
    if errores or regresiones or resumen["ya_empeora"] or resumen["ya_incierto"]:
        return 2
    return 1 if resumen["pendientes"] or resumen["sin_revisar"] else 0


if __name__ == "__main__":
    # Una excepción saldría con 1, que aquí significa "hay correcciones por
    # verificar": se confundiría con un resultado. Sale 3, que nadie acepta.
    try:
        sys.exit(main())
    except Exception:                                # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("✗ impacto_corpus.py falló: no se pudo medir el impacto")
        sys.exit(3)

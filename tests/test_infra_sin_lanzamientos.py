"""Ningún workflow ni script de este repo lanza una corrida.

El único que lanza es `OpenCodice/supervisor`; aquí cada corrida hace su
trabajo, declara su estado y termina. La excepción es el Worker `scheduler`,
que lanza solo al supervisor y no está ni en `.github/` ni en `scripts/`.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS = (".github", "scripts")

LANZAMIENTOS = {
    "gh workflow run": re.compile(r"\bgh\s+workflow\s+run\b"),
    "gh run rerun": re.compile(r"\bgh\s+run\s+rerun\b"),
    "/dispatches": re.compile(r"/dispatches\b"),
    "repository_dispatch": re.compile(r"\brepository_dispatch\b"),
}


def lanzamientos(texto: str) -> list[tuple[int, str]]:
    return [
        (n, nombre)
        for n, linea in enumerate(texto.splitlines(), 1)
        for nombre, patron in LANZAMIENTOS.items()
        if patron.search(linea)
    ]


def archivos() -> list[Path]:
    return sorted(
        p
        for carpeta in CARPETAS
        for p in (RAIZ / carpeta).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )


def test_ni_workflows_ni_scripts_lanzan_corridas():
    encontrados = []
    for p in archivos():
        try:
            texto = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        encontrados += [f"{p.relative_to(RAIZ)}:{n}: {nombre}" for n, nombre in lanzamientos(texto)]
    assert not encontrados, "Solo el supervisor lanza corridas:\n" + "\n".join(encontrados)


def test_se_revisan_los_workflows_y_los_scripts():
    rutas = {p.relative_to(RAIZ).as_posix() for p in archivos()}
    assert ".github/workflows/vigilar-cpeum.yml" in rutas
    assert "scripts/agente/cerrar.sh" in rutas


@pytest.mark.parametrize("linea", [
    'run: gh workflow run vigilar-cpeum.yml -R "$GITHUB_REPOSITORY" --ref main',
    "gh  workflow   run x.yml",
    'gh run rerun "$GITHUB_RUN_ID" --failed',
    "gh api repos/OpenCodice/constitucion-web/dispatches -f event_type=datos-actualizados",
    'curl -X POST "$API/actions/workflows/x.yml/dispatches"',
    "  repository_dispatch:",
])
def test_detecta_cada_forma_de_lanzar(linea):
    assert lanzamientos(linea)


@pytest.mark.parametrize("linea", [
    "  workflow_dispatch:",
    "    uses: ./.github/workflows/revisar-pr.yml",
    "gh pr list -R OpenCodice/leyes-estatales --state open",
    "gh run view 123 --log",
])
def test_no_confunde_lo_que_no_lanza(linea):
    assert not lanzamientos(linea)

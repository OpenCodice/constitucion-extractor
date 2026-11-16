"""Perfiles de las constituciones estatales, un módulo por estado.

El nombre del módulo es el slug del estado con guion bajo (`nuevo_leon.py` →
`nuevo-leon`), que es también el nombre del perfil, del resolver y de la carpeta
en `leyes-estatales`. Cada módulo define `PERFIL` y, si su PDF se puede
encontrar solo, `RESOLVER` (ver `scripts/resolver_pdf.py`).
"""
from __future__ import annotations

import importlib
import pkgutil


def _modulos():
    for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if not m.name.startswith("_"):
            yield m.name.replace("_", "-"), importlib.import_module(f"{__name__}.{m.name}")


def cargar_estados() -> dict:
    return {estado: mod.PERFIL for estado, mod in _modulos()}


def resolvers_estados() -> dict:
    """Cómo encontrar el PDF vigente de cada estado (ver scripts/resolver_pdf.py).
    Un estado sin `RESOLVER`, o que aún no reproduce fielmente su PDF
    (`LISTO = False`), queda fuera de la vigilancia automática."""
    return {estado: (getattr(mod, "RESOLVER", None) if getattr(mod, "LISTO", False) else None)
            or {"tipo": "manual"} for estado, mod in _modulos()}

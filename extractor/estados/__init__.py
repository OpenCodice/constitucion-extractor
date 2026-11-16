"""Perfiles de las constituciones estatales, un módulo por estado.

El nombre del módulo es el slug del estado con guion bajo (`nuevo_leon.py` →
`nuevo-leon`), que es también el nombre del perfil, del resolver y de la carpeta
en `leyes-estatales`. Cada módulo define:

- `PERFIL` — cómo leer su PDF (falta si aún no hay un PDF oficial utilizable);
- `RESOLVER` — cómo encontrar cada semana el PDF vigente (ver
  `scripts/resolver_pdf.py`);
- `LISTO` — True cuando su extracción reproduce fielmente el PDF; solo entonces
  entra a la vigilancia;
- `MOTIVO` — si el estado queda fuera por ahora, por qué, en lenguaje llano: lo
  muestra constitucion.app/leyes.

Jalisco y CDMX viven en `extractor/fuentes.py`, de antes de este paquete.
"""
from __future__ import annotations

import importlib
import pkgutil

# Las 32 entidades: slug (carpeta en leyes-estatales) y nombre.
ENTIDADES = {
    "aguascalientes": "Aguascalientes", "baja-california": "Baja California",
    "baja-california-sur": "Baja California Sur", "campeche": "Campeche",
    "chiapas": "Chiapas", "chihuahua": "Chihuahua", "cdmx": "Ciudad de México",
    "coahuila": "Coahuila", "colima": "Colima", "durango": "Durango",
    "edomex": "Estado de México", "guanajuato": "Guanajuato", "guerrero": "Guerrero",
    "hidalgo": "Hidalgo", "jalisco": "Jalisco", "michoacan": "Michoacán",
    "morelos": "Morelos", "nayarit": "Nayarit", "nuevo-leon": "Nuevo León",
    "oaxaca": "Oaxaca", "puebla": "Puebla", "queretaro": "Querétaro",
    "quintana-roo": "Quintana Roo", "san-luis-potosi": "San Luis Potosí",
    "sinaloa": "Sinaloa", "sonora": "Sonora", "tabasco": "Tabasco",
    "tamaulipas": "Tamaulipas", "tlaxcala": "Tlaxcala", "veracruz": "Veracruz",
    "yucatan": "Yucatán", "zacatecas": "Zacatecas",
}


def _modulos():
    for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if not m.name.startswith("_"):
            yield m.name.replace("_", "-"), importlib.import_module(f"{__name__}.{m.name}")


def cargar_estados() -> dict:
    return {estado: mod.PERFIL for estado, mod in _modulos() if hasattr(mod, "PERFIL")}


def resolvers_estados() -> dict:
    """Cómo encontrar el PDF vigente de cada estado (ver scripts/resolver_pdf.py).
    Un estado sin `RESOLVER`, o que aún no reproduce fielmente su PDF
    (`LISTO = False`), queda fuera de la vigilancia automática."""
    return {estado: (getattr(mod, "RESOLVER", None) if getattr(mod, "LISTO", False) else None)
            or {"tipo": "manual"} for estado, mod in _modulos()}


def registro() -> list[dict]:
    """Situación de las 32 entidades, para `estados.json` (lo lee la web).

    situacion: "vigilada" (extracción fiel, entra a la vigilancia semanal),
    "fuera" (con `motivo`) o "en_preparacion"."""
    mods = dict(_modulos())
    filas = []
    for slug, nombre in ENTIDADES.items():
        mod = mods.get(slug)
        if slug in ("jalisco", "cdmx") or (mod and getattr(mod, "LISTO", False)):
            situacion, motivo = "vigilada", None
        elif mod and getattr(mod, "MOTIVO", None):
            situacion, motivo = "fuera", mod.MOTIVO
        else:
            situacion, motivo = "en_preparacion", None
        perfil = getattr(mod, "PERFIL", None)
        filas.append({"estado": slug, "nombre": nombre, "situacion": situacion,
                      "motivo": motivo,
                      "documento": perfil.nombre if perfil else None})
    return filas

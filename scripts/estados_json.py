#!/usr/bin/env python3
"""Escribe `estados.json`: la situación de cada entidad (ver
`extractor.estados.registro`). constitucion.app lo lee para /leyes y /estado.
Una prueba exige que el archivo esté al día con el registro.

Uso: python scripts/estados_json.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extractor.estados import registro  # noqa: E402


def contenido() -> str:
    return json.dumps(registro(), ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    (RAIZ / "estados.json").write_text(contenido(), encoding="utf-8")

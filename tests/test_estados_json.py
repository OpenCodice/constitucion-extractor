"""`estados.json` es generado: debe coincidir con el registro de `extractor/estados/`."""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("estados_json", RAIZ / "scripts" / "estados_json.py")
estados_json = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(estados_json)


def test_estados_json_al_dia():
    actual = (RAIZ / "estados.json").read_text(encoding="utf-8")
    assert actual == estados_json.contenido(), "corre: python scripts/estados_json.py"


def test_32_entidades():
    from extractor.estados import ENTIDADES
    assert len(ENTIDADES) == 32

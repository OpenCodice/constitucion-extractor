#!/usr/bin/env python3
"""Regenera la tabla de estados del README de leyes-estatales desde sus carpetas
{estado}/constitucion/ y, para las demás leyes de cada estado, desde su
fuentes.json (lo escribe la vigilancia de fiscal-extractor). Uso:
readme_estatales.py <ruta a leyes-estatales>

Solo reemplaza dos bloques: la tabla de estados (`ESTADOS:INICIO` …
`ESTADOS:FIN`) y la de automatización (`AUTOMATIZACION:INICIO` … `FIN`; si el
README aún no tiene sus marcas, la tabla que sigue a «## Automatización»). La
tabla de estados no lleva cifras que cambien con cada reforma (artículos,
fechas), para que los PR de vigilancia no choquen en el README: esas cifras
están en constitucion.app/leyes.

Lo corre la vigilancia de las leyes estatales (vigilar-leyes-estatales.yml de
fiscal-extractor), que lo publica en su commit `Tipo: indice`. """
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


NOMBRES = {
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


def tabla(REPO: Path) -> str:
    fuentes = REPO / "fuentes.json"
    leyes: dict[str, list[str]] = {}
    for d in (json.loads(fuentes.read_text(encoding="utf-8"))["documentos"]
              if fuentes.exists() else []):
        if d.get("estado") == "incluida":
            leyes.setdefault(d["clave"].split("/")[0], []).append(
                f"[{d.get('sigla') or d['clave']}]({d['clave']}/)")
    filas = ["| Estado | Carpeta | Publicada por | Otras leyes |", "|---|---|---|---|"]
    presentes = []
    for d in sorted(REPO.glob("*/constitucion/metadata/articulos.json")):
        slug = d.parts[-4]
        meta = json.loads(d.read_text(encoding="utf-8"))
        presentes.append(slug)
        fuente = (meta.get("fuente") or "").replace("|", "\\|")
        otras = ", ".join(sorted(leyes.get(slug, []))) or "—"
        filas.append(f"| {NOMBRES.get(slug, slug)} | [`{slug}/constitucion/`]({slug}/constitucion/) "
                     f"| {fuente} | {otras} |")
    faltan = [n for s, n in NOMBRES.items() if s not in presentes]
    nota = (f"\n\nFaltan {len(faltan)}: {', '.join(sorted(faltan))}. Por qué, en "
            "[constitucion.app/leyes](https://constitucion.app/leyes#estados).") if faltan else ""
    return "\n".join(filas) + nota


_CE = "[`constitucion-extractor`](https://github.com/OpenCodice/constitucion-extractor)"
_FE = "[`fiscal-extractor`](https://github.com/OpenCodice/fiscal-extractor)"
AUTOMATIZACION = "\n".join([
    "| Dónde | Disparo | Qué hace |",
    "|-------|---------|----------|",
    f"| `vigilar-estatales.yml` de {_CE} | lunes (Worker `scheduler`) / manual | "
    "las constituciones: resuelve la URL vigente de cada estado, regenera, verifica cada "
    "artículo cambiado contra el PDF con un agente y abre aquí un PR por estado |",
    f"| `vigilar-leyes-estatales.yml` de {_FE} | lunes (Worker `scheduler`) / manual | "
    "las demás leyes de cada estado: reprocesa las que cambiaron, da de alta las nuevas por "
    "tandas tras revisarlas enteras contra su PDF, repara el extractor cuando encuentra "
    "defectos y abre aquí un PR |",
    f"| `expandir-estatales.yml` de {_FE} | miércoles (Worker `scheduler`) / manual | "
    "ronda de expansión: cuando la vigilancia anterior terminó, un agente escribe el "
    "registro de las leyes de un estado más y, si pasa las compuertas, lanza su vigilancia |",
    "| `revisar-pr.yml` de los dos extractores | cada PR de vigilancia | "
    "valida en un job sin secretos los invariantes de cada documento y los trailers de "
    "cada commit (GATE) y fusiona solo el PR que llegó verificado |",
])
# Antes de las marcas: la tabla que sigue a «## Automatización».
_SIN_MARCAS = re.compile(r"(## Automatización\n(?:(?!\n## |\n\|).)*?\n\n)((?:\|[^\n]*\n)+)", re.S)


def bloque(t: str, nombre: str, contenido: str) -> str:
    return re.sub(rf"(<!-- {nombre}:INICIO -->).*?(<!-- {nombre}:FIN -->)",
                  lambda m: f"{m.group(1)}\n{contenido}\n{m.group(2)}", t, flags=re.S)


def main(REPO: Path) -> None:
    readme = REPO / "README.md"
    t = readme.read_text(encoding="utf-8")
    if "<!-- AUTOMATIZACION:INICIO -->" not in t:
        t = _SIN_MARCAS.sub(lambda m: f"{m.group(1)}<!-- AUTOMATIZACION:INICIO -->\n"
                            "<!-- AUTOMATIZACION:FIN -->\n", t, count=1)
    t = bloque(t, "ESTADOS", tabla(REPO))
    t = bloque(t, "AUTOMATIZACION", AUTOMATIZACION)
    readme.write_text(t, encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

#!/usr/bin/env python3
"""Resuelve la URL del PDF VIGENTE de la constitución de un estado.

El problema que resuelve: a diferencia del DOF federal (URL fija), los congresos
estatales no exponen una URL estable. Hay dos patrones:

  - "directo":  el PDF vive en una URL con nombre estable (p.ej. CDMX). Se
                devuelve tal cual.
  - "indice":   el PDF lleva la FECHA embebida en el nombre y rota en cada
                reforma (p.ej. Jalisco: ...-DDMMYY.pdf). Hay que leer la página
                índice de leyes, extraer el enlace de la Constitución y quedarse
                con el de fecha más reciente.

Usa urllib (librería estándar). Importa el registro de `extractor/estados/`,
así que necesita las dependencias del extractor instaladas.

Uso:
    python scripts/resolver_pdf.py jalisco        # imprime la URL vigente
    python scripts/resolver_pdf.py --listar       # estados soportados
    python scripts/resolver_pdf.py --matriz       # matriz JSON de la vigilancia
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# estado → cómo encontrar su PDF vigente.
RESOLVERS: dict[str, dict] = {
    # CDMX: el Congreso publica el texto vigente en una URL de nombre estable
    # (más limpia que el PDF del piloto, que salía de una URL hash que rota). El
    # perfil `cdmx` ya la parsea limpio (números de página y cola de decretos
    # tratados), así que se vigila automático.
    "cdmx": {
        "tipo": "directo",
        "url": ("https://www.congresocdmx.gob.mx/archivos/legislativas/"
                "constitucion_politica_de_la_ciudad_de_mexico.pdf"),
    },
    # Jalisco: el PDF lleva la fecha (DDMMYY) en el nombre y rota en cada
    # reforma. El "Listado Completo" de la biblioteca virtual enlaza al vigente.
    "jalisco": {
        "tipo": "indice",
        "index_url": ("https://congresoweb.congresojal.gob.mx/"
                      "bibliotecavirtual/busquedasleyes/Listado'2.cfm"),
        "encoding": "iso-8859-1",
        # ruta relativa del PDF de la Constitución, con DDMMYY al final.
        "patron": re.compile(
            r'href="(\.\./legislacion/[^"]*Documentos_PDF-Constituci[^"]*'
            r'-(\d{2})(\d{2})(\d{2})\.pdf)"'),
    },
}


# Worker de Cloudflare en México (ver egress-mx/): para los estados cuyo
# sitio rechaza IP de fuera del país ("via": "mx" en su RESOLVER).
EGRESS_MX = os.environ.get("EGRESS_MX_URL", "https://egress-mx.danielcardeenas.workers.dev/")


def via_mx(url: str) -> tuple[str, dict]:
    """URL y cabeceras para pedir `url` a través del Worker en México."""
    token = os.environ.get("EGRESS_MX_TOKEN", "")
    if not token:
        raise SystemExit("falta EGRESS_MX_TOKEN para descargar vía México")
    return f"{EGRESS_MX}?url={quote(url, safe='')}", {"Authorization": f"Bearer {token}"}


def _fetch_text(url: str, encoding: str, via: str | None = None) -> str:
    headers = {"User-Agent": _UA}
    if via == "mx":
        url, extra = via_mx(url)
        headers.update(extra)
    req = Request(url, headers=headers)
    with urlopen(req, timeout=90) as r:               # nosec: URL fija de config
        return r.read().decode(encoding, errors="replace")


def _encode_url(url: str) -> str:
    """Percent-encode solo la ruta (espacios y acentos) dejando el resto igual."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=quote(parts.path, safe="/%")))


def elegir_mas_reciente(html: str, patron: re.Pattern, index_url: str) -> str:
    """Del índice `html`, devuelve la URL absoluta (codificada) del PDF de la
    Constitución con la fecha DDMMYY más reciente. Función pura (testeable)."""
    matches = patron.findall(html)
    if not matches:
        raise SystemExit(f"no se encontró el PDF de la Constitución en {index_url}")
    # Cada match: (ruta_relativa, DD, MM, YY). Quédate con la fecha más reciente.
    rel = max(matches, key=lambda m: date(2000 + int(m[3]), int(m[2]), int(m[1])))[0]
    return _encode_url(urljoin(index_url, rel))


def _resolver_indice(cfg: dict) -> str:
    html = _fetch_text(cfg["index_url"], cfg.get("encoding", "utf-8"), cfg.get("via"))
    orden = cfg.get("orden", "ddmmyy")
    if orden == "ddmmyy":
        return elegir_mas_reciente(html, cfg["patron"], cfg["index_url"])
    return elegir(html, cfg["patron"], cfg["index_url"], orden,
                  cfg.get("plantilla"))


def elegir(html: str, patron: re.Pattern, index_url: str, orden: str,
           plantilla: str | None = None) -> str:
    """Del índice, la URL del PDF vigente. `orden`:
    - "unico": todas las coincidencias deben ser la misma ruta (si el índice
      enlaza dos constituciones distintas, mejor fallar que adivinar);
    - "yyyymmdd" / "fecha": el grupo 2 es la fecha (AAAAMMDD, o AAAA-MM-DD en
      cualquier separador) y gana la más reciente;
    - "ddmmaaaa": igual, con la fecha en orden día-mes-año.
    `plantilla` arma la URL final con la ruta capturada (`{0}`). Función pura."""
    ms = [m if isinstance(m, tuple) else (m,) for m in patron.findall(html)]
    if not ms:
        raise SystemExit(f"no se encontró el PDF de la Constitución en {index_url}")
    if orden == "unico":
        rutas = {m[0] for m in ms}
        if len(rutas) > 1:
            raise SystemExit(f"{index_url} enlaza {len(rutas)} PDF distintos: {sorted(rutas)[:3]}")
        rel = ms[0][0]
    elif orden in ("yyyymmdd", "fecha"):
        rel = max(ms, key=lambda m: re.sub(r"\D", "", m[1]))[0]
    elif orden == "ddmmaaaa":
        rel = max(ms, key=lambda m: (d := re.sub(r"\D", "", m[1]))[4:8] + d[2:4] + d[0:2])[0]
    else:
        raise SystemExit(f"orden desconocido: {orden!r}")
    url = plantilla.format(rel) if plantilla else urljoin(index_url, rel)
    return _encode_url(url)


def _de_los_estados() -> dict[str, dict]:
    """Resolvers declarados en cada módulo de `extractor/estados/` (`RESOLVER`)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from extractor.estados import resolvers_estados
    return resolvers_estados()


RESOLVERS.update(_de_los_estados())


def resolver(estado: str) -> str:
    cfg = RESOLVERS.get(estado)
    if cfg is None:
        raise SystemExit(
            f"estado desconocido: {estado!r}. Soportados: {', '.join(RESOLVERS)}")
    if cfg["tipo"] == "manual":
        return ""                       # sin URL automática → el watcher lo salta
    if cfg["tipo"] == "directo":
        return cfg["url"]
    if cfg["tipo"] == "indice":
        return _resolver_indice(cfg)
    if cfg["tipo"] == "funcion":
        return cfg["funcion"]()
    raise SystemExit(f"tipo de resolver desconocido: {cfg['tipo']!r}")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--matriz":
        # La vigilancia corre un job por estado con vigilancia automática; el
        # perfil y la carpeta llevan el mismo nombre que el estado.
        print(json.dumps([{"estado": e, "perfil": e, "dir": f"{e}/constitucion",
                           "via": c.get("via") or ""}
                          for e, c in RESOLVERS.items() if c["tipo"] != "manual"]))
        return 0
    if argv[0] == "--listar":
        for e, c in RESOLVERS.items():
            print(f"{e}\t{c['tipo']}")
        return 0
    print(resolver(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

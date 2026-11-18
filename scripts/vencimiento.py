#!/usr/bin/env python3
"""Falla si una credencial vence pronto. Lo usa `credenciales.yml`.

    vencimiento.py fecha NOMBRE "<fecha>" [--sin-fecha TEXTO] [--renovar TEXTO] [--dias N]
    vencimiento.py cloudflare NOMBRE respuesta.json [--renovar TEXTO] [--dias N]

`fecha` recibe la fecha tal como la da su fuente: la cabecera
`github-authentication-token-expiration` de GitHub (`2027-11-20 06:00:00 UTC`
o con zona `-0600`), un día ISO (`2027-11-15`) o un instante ISO. Vacía, la
credencial no vence o no se sabe cuándo: solo avisa. `cloudflare` lee la
respuesta de `/user/tokens/verify`.

Si falla, lo único que imprime es un `::error::` que empieza por
«Credencial por renovar»: el supervisor reconoce por esa línea que no es una
falla que se arregle reintentando, y el mensaje no lleva nada que cambie de un
día a otro salvo la fecha.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

MARCA = "Credencial por renovar"
_FECHA = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?\s*(UTC|GMT|Z|[+-]\d{2}:?\d{2})?)?$")


def leer_fecha(texto: str) -> datetime:
    """El instante (UTC) de una fecha de vencimiento. Sin hora, el inicio de ese día; sin zona, UTC."""
    m = _FECHA.match(texto.strip())
    if not m:
        raise ValueError(f"fecha ilegible: {texto!r}")
    zona = m.group(3) or "UTC"
    zona = "+00:00" if zona in ("UTC", "GMT", "Z") else f"{zona[:3]}:{zona[-2:]}"
    return datetime.fromisoformat(f"{m.group(1)}T{m.group(2) or '00:00:00'}{zona}").astimezone(timezone.utc)


def revisar(nombre: str, fecha: str, ahora: datetime, dias: int = 30, sin_fecha: str = "no vence",
            renovar: str = "") -> tuple[bool, str]:
    """(vigente, línea para el log)."""
    como = f" Cómo: {renovar}" if renovar else ""
    if not fecha.strip():
        return True, f"::notice::{nombre}: {sin_fecha}"
    try:
        vence = leer_fecha(fecha)
    except ValueError as e:
        return False, f"::error::{MARCA}: no se entiende cuándo vence {nombre} ({e})."
    cuando = vence.strftime("%Y-%m-%d %H:%M UTC")
    if vence <= ahora:
        return False, f"::error::{MARCA}: {nombre} venció el {cuando}.{como}"
    if vence - ahora < timedelta(days=dias):
        return False, f"::error::{MARCA}: {nombre} vence el {cuando}, en menos de {dias} días.{como}"
    return True, f"{nombre} vence el {cuando} (faltan {(vence - ahora).days} días): OK"


def revisar_cloudflare(nombre: str, respuesta: dict, ahora: datetime, dias: int = 30, renovar: str = "") -> tuple[bool, str]:
    """Lo que dice `GET /user/tokens/verify` (o el de la cuenta): activo y sin vencer pronto."""
    como = f" Cómo: {renovar}" if renovar else ""
    resultado = respuesta.get("result") or {}
    if not respuesta.get("success") or resultado.get("status") != "active":
        motivo = resultado.get("status") or "; ".join(
            str(e.get("message")) for e in respuesta.get("errors") or [] if isinstance(e, dict)) or "sin respuesta válida"
        return False, f"::error::{MARCA}: {nombre} no está activo en Cloudflare ({motivo}).{como}"
    return revisar(nombre, resultado.get("expires_on") or "", ahora, dias, "activo en Cloudflare y no vence", renovar)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("modo", choices=("fecha", "cloudflare"))
    analizador.add_argument("nombre")
    analizador.add_argument("valor", help="la fecha (modo fecha) o el archivo con la respuesta (modo cloudflare)")
    analizador.add_argument("--dias", type=int, default=30)
    analizador.add_argument("--sin-fecha", default="no vence")
    analizador.add_argument("--renovar", default="")
    args = analizador.parse_args(argv)
    ahora = datetime.now(timezone.utc)
    if args.modo == "fecha":
        vigente, linea = revisar(args.nombre, args.valor, ahora, args.dias, args.sin_fecha, args.renovar)
    else:
        try:
            with open(args.valor, encoding="utf-8") as f:
                respuesta = json.load(f)
            if not isinstance(respuesta, dict):
                raise ValueError("no es un objeto")
        except (OSError, ValueError) as e:
            # No se sabe nada del token: es una falla de la comprobación, no una credencial vencida.
            print(f"::error::No se pudo leer la respuesta de Cloudflare sobre {args.nombre}: {e}")
            return 1
        vigente, linea = revisar_cloudflare(args.nombre, respuesta, ahora, args.dias, args.renovar)
    print(linea)
    return 0 if vigente else 1


if __name__ == "__main__":
    sys.exit(main())

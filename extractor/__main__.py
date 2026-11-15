"""CLI del extractor.

Uso:
    python -m extractor build --pdf CPEUM.pdf --out ../constitucion-mexicana
    python -m extractor stats --pdf CPEUM.pdf
    python -m extractor verificar --pdf CPEUM.pdf --out ../constitucion-mexicana --reparar
"""
from __future__ import annotations

import argparse
import sys

from .build import build
from .fuentes import FUENTES, perfil_por_nombre
from .parse import parse


def _add_perfil(sp: argparse.ArgumentParser) -> None:
    """Flag común: qué fuente parsear (federal por defecto)."""
    sp.add_argument("--perfil", choices=sorted(FUENTES), default="cpeum",
                    help="Fuente a procesar (default: cpeum). Ej.: jalisco, cdmx")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="extractor",
                                description="Extractor de constituciones (federal + estatales) a Markdown")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Genera el texto (capa 1) y la metadata (capa 3)")
    b.add_argument("--pdf", default="CPEUM.pdf")
    b.add_argument("--out", required=True, help="Ruta al repo de datos (constitucion-mexicana)")
    b.add_argument("--only", choices=["all", "text", "metadata"], default="all",
                   help="Qué capa escribir: all (default), text, metadata")
    b.add_argument("--version", default=None,
                   help="Fecha de versión YYYY-MM-DD (override; si el PDF no la trae)")
    b.add_argument("--url-fuente", default=None,
                   help="URL del PDF vigente (override; la del perfil puede rotar)")
    _add_perfil(b)

    idx = sub.add_parser("index", help="Regenera SOLO la metadata derivada (no toca los .md)")
    idx.add_argument("--pdf", default="CPEUM.pdf")
    idx.add_argument("--out", required=True)
    idx.add_argument("--version", default=None,
                     help="Fecha de versión YYYY-MM-DD (override; si el PDF no la trae)")
    idx.add_argument("--url-fuente", default=None,
                     help="URL del PDF vigente (override; la del perfil puede rotar)")
    _add_perfil(idx)

    v = sub.add_parser("validar",
                       help="Verifica invariantes del repo de datos (gate de CI). Sale !=0 si falla")
    v.add_argument("--out", required=True, help="Ruta al repo de datos")
    v.add_argument("--base", default=None,
                   help="Ref git base para checks de diff (p.ej. origin/main)")
    v.add_argument("--max-cambios", type=int, default=20,
                   help="Máximo de artículos que puede tocar una reforma legítima")
    _add_perfil(v)

    vf = sub.add_parser("verificar",
                        help="Verifica con LLM los artículos cambiados contra el PDF. "
                             "Sale !=0 si quedan cambios que no son reforma")
    vf.add_argument("--pdf", default="CPEUM.pdf")
    vf.add_argument("--out", required=True, help="Ruta al repo de datos (ya regenerado)")
    vf.add_argument("--reparar", action="store_true",
                    help="Aprender ruido de página, regenerar y reverificar")
    vf.add_argument("--modelo", default=None,
                    help="Modelo (default: $VERIFICADOR_MODELO o el del módulo)")
    vf.add_argument("--sin-llm", action="store_true",
                    help="Solo la cobertura determinista (sin LLM ni autorreparación)")
    vf.add_argument("--reporte", default=None, help="Escribe el reporte markdown aquí")
    vf.add_argument("--version", default=None)
    vf.add_argument("--url-fuente", default=None)
    _add_perfil(vf)

    au = sub.add_parser("auditar",
                        help="Cobertura determinista de todos los artículos contra el PDF")
    au.add_argument("--pdf", default="CPEUM.pdf")
    au.add_argument("--out", required=True, help="Ruta al repo de datos")
    au.add_argument("--json", default=None, help="Escribe el resultado aquí")
    _add_perfil(au)

    s = sub.add_parser("stats", help="Imprime estadísticas del parseo (no escribe)")
    s.add_argument("--pdf", default="CPEUM.pdf")
    _add_perfil(s)

    args = p.parse_args(argv)

    if args.cmd == "validar":
        from .validate import format_report, validate
        perfil = perfil_por_nombre(args.perfil)
        ok, checks = validate(args.out, base=args.base, max_changes=args.max_cambios,
                              perfil=perfil)
        print(format_report(checks))
        print("\n" + ("✅ Invariantes OK" if ok else "❌ Invariantes ROTOS — no mergear"))
        return 0 if ok else 1

    if args.cmd == "verificar":
        from .verificar import (con_ruido, modelo_configurado,
                                modelo_fuerte_configurado, openai_call,
                                reporte_md, verificar)
        perfil = con_ruido(perfil_por_nombre(args.perfil), args.out)
        modelo = args.modelo or modelo_configurado()

        def rebuild(p):
            build(args.pdf, args.out, perfil=p, version=args.version,
                  url_fuente=args.url_fuente)

        if args.sin_llm:
            r = verificar(args.pdf, args.out, perfil, None)
        else:
            r = verificar(args.pdf, args.out, perfil, openai_call(modelo),
                          reparar=args.reparar, rebuild=rebuild,
                          call_fuerte=openai_call(modelo_fuerte_configurado()))
        md = reporte_md(r)
        if args.reporte:
            with open(args.reporte, "w", encoding="utf-8") as fh:
                fh.write(md)
        print(md)
        return 0 if r.ok else 2

    if args.cmd == "auditar":
        import json
        from .verificar import auditar, con_ruido
        perfil = con_ruido(perfil_por_nombre(args.perfil), args.out)
        res = auditar(args.pdf, args.out, perfil)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=2)
        malos = res["con_problemas"]
        print(f"{len(malos)} de {res['total']} artículos con problemas de cobertura")
        for clave, pr in malos.items():
            print(f"  {clave}: " + "; ".join(f"{p['tipo']} «{p['fragmento'][:80]}»" for p in pr[:3]))
        return 0

    if args.cmd == "build":
        from .verificar import con_ruido
        perfil = con_ruido(perfil_por_nombre(args.perfil), args.out)
        arts = build(args.pdf, args.out, what=args.only, perfil=perfil,
                     version=args.version, url_fuente=args.url_fuente)
        if args.only == "metadata":
            print(f"✓ metadata de {len(arts)} artículos en {args.out}/metadata/")
        else:
            print(f"✓ {len(arts)} artículos escritos en {args.out}/articulos/")
        return 0

    if args.cmd == "index":
        from .verificar import con_ruido
        perfil = con_ruido(perfil_por_nombre(args.perfil), args.out)
        arts = build(args.pdf, args.out, what="metadata", perfil=perfil,
                     version=args.version, url_fuente=args.url_fuente)
        print(f"✓ metadata regenerada para {len(arts)} artículos (sin tocar los .md)")
        return 0

    if args.cmd == "stats":
        perfil = perfil_por_nombre(args.perfil)
        arts = parse(args.pdf, perfil=perfil)
        nums = [a.number for a in arts]
        lo, hi = (min(nums), max(nums)) if nums else (0, 0)
        gaps = [n for n in range(lo, hi + 1) if n not in nums]
        print(f"Perfil: {perfil.ambito} ({perfil.nombre})")
        print(f"Artículos: {len(arts)} (rango {lo}–{hi})")
        print(f"Huecos en {lo}–{hi}: {gaps or 'ninguno'}")
        print(f"Con sufijo: {[a.label for a in arts if a.suffix] or 'ninguno'}")
        total_reformas = sum(len(a.reform_dates) for a in arts)
        print(f"Notas de reforma totales: {total_reformas}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

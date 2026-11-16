#!/usr/bin/env bash
# Compuertas deterministas después del agente. Regenera el repo de datos desde
# cero (el texto nunca sale del agente), decide si su arreglo al extractor se
# publica y emite el veredicto final. Sale 0 si todo quedó fiel, 2 si no.
#
# Entorno: PDF, OUT, PERFIL; opcionales BUILD_ARGS, AGENTE_DIR, REPORTE,
# EXTRACTOR_TOKEN + EXTRACTOR_SLUG (para publicar el arreglo), EXTRACTOR_PUSH_URL
# (destino alterno, para pruebas).
set -uo pipefail

EXTRACTOR="$(cd "$(dirname "$0")/../.." && pwd)"
TRABAJO="${AGENTE_DIR:-/tmp/agente}"
REPORTE="${REPORTE:-/tmp/verificacion.md}"
cd "$EXTRACTOR"
export PYTHONPATH="$EXTRACTOR"

if [ ! -s "$TRABAJO/cambiados.txt" ]; then
  exit 0
fi

regenerar() {
  # En el alta de un estado la carpeta aún no tiene archivos versionados.
  git -C "$OUT" checkout -q -- . 2>/dev/null || true
  git -C "$OUT" clean -fdq -- .
  # shellcheck disable=SC2086
  python -m extractor build --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" ${BUILD_ARGS:-} > /dev/null
}

descartar() {
  echo "::warning::Arreglo del agente descartado: $1"
  motivo_descarte="$1"
  [ -s "$TRABAJO/arreglo-descartado.patch" ] || git diff > "$TRABAJO/arreglo-descartado.patch" || true
  git checkout -q -- . && git clean -fdq
}

campo() {
  python - "$TRABAJO/veredicto.json" "$1" <<'PY'
import json, sys
try:
    v = json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2], "")
except Exception:
    v = ""
print(str(v).lower() if isinstance(v, bool) else v)
PY
}

reparado=false
motivo_descarte=""
# La vigilancia corre en este mismo repo: el agente solo puede publicar cambios
# al extractor y a sus pruebas, nunca a workflows, scripts ni Workers.
# Archivos nuevos sueltos (copias de PDF, notas de trabajo) no se publican.
git ls-files --others --exclude-standard | grep -vE '^(extractor|tests)/' | while IFS= read -r f; do rm -f -- "$f"; done
fuera=$( { git diff --name-only HEAD; git ls-files --deleted; } | sort -u | grep -vE '^(extractor|tests)/' || true)
if [ -n "$fuera" ]; then
  descartar "toca archivos fuera de extractor/ y tests/: $(echo "$fuera" | head -3 | tr '\n' ' ')"
fi
if [ -n "$(git status --porcelain)" ]; then
  pip install -q pytest > /dev/null 2>&1 || true
  if ! python -m pytest -q > "$TRABAJO/pytest.log" 2>&1; then
    descartar "las pruebas no pasan"
  else
    regenerar
    python -m extractor auditar --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" \
      --json "$TRABAJO/nuevo.json" > /dev/null
    nuevas=$(python - "$TRABAJO" <<'PY'
import json, sys
t = sys.argv[1]
base = set(json.load(open(f"{t}/base.json"))["con_problemas"])
nuevo = set(json.load(open(f"{t}/nuevo.json"))["con_problemas"])
print(" ".join(sorted(nuevo - base)))
PY
)
    if [ -n "$nuevas" ]; then
      descartar "rompe la cobertura de: $nuevas"
    elif [ -z "${EXTRACTOR_PUSH_URL:-}" ] && { [ -z "${EXTRACTOR_TOKEN:-}" ] || [ -z "${EXTRACTOR_SLUG:-}" ]; }; then
      descartar "sin credenciales para publicar el arreglo en el extractor"
    else
      titulo="$(campo titulo_commit)"
      git add -A
      git -c user.name="${GITHUB_ACTOR:-opencodice-ci}" \
          -c user.email="${GITHUB_ACTOR_ID:-0}+${GITHUB_ACTOR:-opencodice-ci}@users.noreply.github.com" \
          commit -q -m "Reparación automática: ${titulo:-ajuste del extractor a un cambio de formato del PDF}"
      destino="${EXTRACTOR_PUSH_URL:-https://x-access-token:${EXTRACTOR_TOKEN:-}@github.com/${EXTRACTOR_SLUG:-}.git}"
      # Otras corridas (un job por estado) pueden haber publicado su propio
      # arreglo mientras tanto: se rebasa sobre el main más reciente.
      export GIT_AUTHOR_NAME="${GITHUB_ACTOR:-opencodice-ci}" GIT_COMMITTER_NAME="${GITHUB_ACTOR:-opencodice-ci}"
      export GIT_AUTHOR_EMAIL="${GITHUB_ACTOR_ID:-0}+${GITHUB_ACTOR:-opencodice-ci}@users.noreply.github.com"
      export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
      if git pull -q --rebase "$destino" main && git push -q "$destino" HEAD:main; then
        reparado=true
      else
        git rebase --abort 2>/dev/null || true
        # El arreglo ya está en un commit: se guarda antes de deshacerlo.
        git format-patch -1 --stdout > "$TRABAJO/arreglo-descartado.patch" || true
        git reset -q --hard HEAD~1
        descartar "no se pudo publicar el arreglo en el extractor (chocó con otro arreglo publicado mientras tanto)"
      fi
    fi
  fi
fi

regenerar
python -m extractor verificar --sin-llm --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" \
  --reporte "$TRABAJO/cobertura-final.md" > /dev/null
cobertura_ok=$?
fiel="$(campo fiel)"

ok=false
if [ "$cobertura_ok" -eq 0 ] && [ "$fiel" = "true" ] && [ -z "$motivo_descarte" ]; then
  ok=true
fi

python - "$TRABAJO" "$REPORTE" "$ok" "$reparado" "$motivo_descarte" "$OUT" "$PERFIL" <<'PY'
import json, os, pathlib, subprocess, sys
trabajo, reporte, ok, reparado, descarte, out_dir, perfil = sys.argv[1:8]
t = pathlib.Path(trabajo)
try:
    v = json.loads((t / "veredicto.json").read_text(encoding="utf-8"))
except Exception:
    v = None
# Asunto del commit de datos: distingue reforma real de corrección de extracción.
cambiadas = sorted({pathlib.Path(l[3:].strip()).stem for l in subprocess.run(
    ["git", "-C", out_dir, "status", "--porcelain", "--no-renames", "--", "articulos"],
    capture_output=True, text=True).stdout.splitlines() if l.strip().endswith(".md")})
reformadas = sorted(set(map(str, (v or {}).get("reformadas", []))) & set(cambiadas))
correcciones = [c for c in cambiadas if c not in reformadas]
nombre = "CPEUM" if perfil == "cpeum" else perfil
try:
    version = json.loads(pathlib.Path(out_dir, "metadata", "articulos.json")
                         .read_text(encoding="utf-8")).get("version")
except Exception:
    version = None


def arts(claves):
    if len(claves) > 12:
        return f"{len(claves)} artículos"
    return "arts. " + ", ".join(c.lstrip("0") or "0" for c in claves)


if reformadas:
    fecha = f" ({'DOF ' if perfil == 'cpeum' else ''}{version})" if version else ""
    asunto = f"Reforma {nombre}{fecha}: {arts(reformadas)}"
    if correcciones:
        asunto += f" (+{len(correcciones)} correcciones de extracción)"
    tipo = "reforma"
else:
    asunto = f"Corrección de extracción {nombre}: {arts(correcciones)}"
    tipo = "correccion"

icono = {"fiel": "✅", "artefacto": "❌", "incierto": "❔"}
out = ["### 🤖 Verificación del agente contra el PDF", ""]
if ok == "true":
    out.append("La extracción quedó verificada: reproduce fielmente el PDF oficial.")
else:
    out.append("**La extracción NO quedó verificada — no mergear sin revisar.**")
if v is None:
    out += ["", "El agente no entregó veredicto."]
else:
    out += ["", str(v.get("resumen", ""))]
    if reparado == "true":
        out += ["", f"🔧 El agente reparó el extractor: _{v.get('titulo_commit', '')}_"]
    out.append("")
    for u in v.get("unidades", [])[:80]:
        out.append(f"- {icono.get(u.get('veredicto'), '❔')} **{u.get('clave')}** — {u.get('nota', '')}")
if descarte:
    out += ["", f"⚠️ Se descartó un arreglo del agente: {descarte}."]
out += ["", (t / "cobertura-final.md").read_text(encoding="utf-8")]
if ok == "true":
    out += ["", f"<!-- asunto: {asunto} -->"]
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write(f"tipo={tipo}\n")
pathlib.Path(reporte).write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
PY

[ "$ok" = "true" ] && exit 0 || exit 2

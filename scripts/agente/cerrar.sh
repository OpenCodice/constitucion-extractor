#!/usr/bin/env bash
# Compuertas deterministas después del agente, en dos fases (dos pasos del
# workflow, con el agente de impacto entre ellas):
#
#   cerrar.sh compuertas — sin secretos. Si el agente cambió el extractor:
#     pruebas, cobertura del documento sin regresiones y el impacto del arreglo
#     en TODAS las constituciones publicadas (scripts/impacto_corpus.py). Deja
#     en $TRABAJO/arreglo.json si el arreglo se descarta, está listo o espera
#     a que el agente de impacto confirme sus correcciones
#     ($TRABAJO/impacto-arreglo/pendientes.json, scripts/agente/impacto.sh).
#   cerrar.sh publicar — con EXTRACTOR_TOKEN. Pasa al registro el veredicto de
#     impacto; publica el arreglo solo si cada artículo publicado que cambia es
#     una mejora. Regenera el repo de datos desde cero (el texto nunca sale del
#     agente) y emite el veredicto final. En un alta, además, la revisión
#     completa por bloques (scripts/revision.py) debe quedar sin hallazgos.
#
# Sale 0 si todo quedó fiel, 2 si no (publicar); compuertas sale 0.
#
# Entorno: PDF, OUT, PERFIL; opcionales BUILD_ARGS, AGENTE_DIR, REPORTE,
# EXTRACTOR_TOKEN + EXTRACTOR_SLUG (para publicar el arreglo), EXTRACTOR_PUSH_URL
# (destino alterno, para pruebas).
set -uo pipefail

FASE="${1:?uso: cerrar.sh compuertas|publicar}"
EXTRACTOR="$(cd "$(dirname "$0")/../.." && pwd)"
TRABAJO="${AGENTE_DIR:-/tmp/agente}"
REPORTE="${REPORTE:-/tmp/verificacion.md}"
IMPACTO="$TRABAJO/impacto-arreglo"
cd "$EXTRACTOR"
export PYTHONPATH="$EXTRACTOR"

if [ ! -s "$TRABAJO/cambiados.txt" ]; then
  exit 0
fi
RAIZ="$(git -C "$OUT" rev-parse --show-toplevel)"
DOC="$([ "$PERFIL" = cpeum ] && echo cpeum || echo "$PERFIL/constitucion")"

regenerar() {
  # En el alta de un estado la carpeta aún no tiene archivos versionados.
  git -C "$OUT" checkout -q -- . 2>/dev/null || true
  git -C "$OUT" clean -fdq -- .
  rm -f "$TRABAJO/regenerar-fallo"
  # Un build que falla deja el repo a medias: no se publica (ver publicar).
  # shellcheck disable=SC2086
  python -m extractor build --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" ${BUILD_ARGS:-} > /dev/null \
    || { echo "::error::No se pudo regenerar el repo de datos."; touch "$TRABAJO/regenerar-fallo"; }
}

estado_arreglo() {
  python3 - "$TRABAJO/arreglo.json" "$@" <<'PY'
import json, sys
ruta, *par = sys.argv[1:]
if par:
    json.dump({"estado": par[0], "motivo": par[1] if len(par) > 1 else ""}, open(ruta, "w"),
              ensure_ascii=False)
else:
    try:
        d = json.load(open(ruta))
    except Exception:
        d = {"estado": "ninguno", "motivo": ""}
    print(d["estado"] + "\t" + d.get("motivo", ""))
PY
}

descartar() {
  echo "::warning::Arreglo del agente descartado: $1"
  [ -s "$TRABAJO/arreglo-descartado.patch" ] || git diff > "$TRABAJO/arreglo-descartado.patch" || true
  git checkout -q -- . && git clean -fdq
  estado_arreglo descartado "$1"
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

compuertas() {
  estado_arreglo ninguno
  # La vigilancia corre en este mismo repo: el agente solo puede publicar
  # cambios al extractor y a sus pruebas, nunca a workflows, scripts ni
  # Workers. Archivos nuevos sueltos (copias de PDF, notas) no se publican.
  git ls-files --others --exclude-standard | grep -vE '^(extractor|tests)/' | while IFS= read -r f; do rm -f -- "$f"; done
  fuera=$( { git diff --name-only HEAD; git ls-files --deleted; } | sort -u | grep -vE '^(extractor|tests)/' || true)
  if [ -n "$fuera" ]; then
    descartar "toca archivos fuera de extractor/ y tests/: $(echo "$fuera" | head -3 | tr '\n' ' ')"
  fi
  [ -n "$(git status --porcelain)" ] || return 0
  pip install -q pytest > /dev/null 2>&1 || true
  if ! python -m pytest -q > "$TRABAJO/pytest.log" 2>&1; then
    descartar "las pruebas no pasan"
    return 0
  fi
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
    return 0
  fi
  # El arreglo cambia el extractor de todas las constituciones: se reconstruye
  # cada una desde el PDF publicado y cada artículo publicado que cambie tiene
  # que confirmarse como mejora antes de que el arreglo entre.
  args=(--trabajo "$IMPACTO")
  if [ "$DOC" = cpeum ]; then args+=(--cpeum "$RAIZ"); else args+=(--estatales "$RAIZ"); fi
  rm -rf "$IMPACTO"
  python scripts/impacto_corpus.py "${args[@]}" > "$TRABAJO/impacto-arreglo.log" 2>&1
  rc=$?
  cat "$TRABAJO/impacto-arreglo.log"
  case "$rc" in
    0) estado_arreglo listo ;;
    # 1 es "hay correcciones por verificar" solo si dejó qué verificar.
    1) if [ -s "$IMPACTO/pendientes.json" ]; then estado_arreglo impacto
       else descartar "la medición del impacto falló sin dejar qué verificar"; fi ;;
    *) descartar "en el resto del corpus: $(grep '^✗' "$TRABAJO/impacto-arreglo.log" | head -3 | tr '\n' ' ')" ;;
  esac
}

publicar_arreglo() {
  if [ -z "${EXTRACTOR_PUSH_URL:-}" ] && { [ -z "${EXTRACTOR_TOKEN:-}" ] || [ -z "${EXTRACTOR_SLUG:-}" ]; }; then
    descartar "sin credenciales para publicar el arreglo en el extractor"
    return
  fi
  titulo="$(campo titulo_commit)"
  git add -A
  git -c user.name="Claude (agente OpenCodice)" \
      -c user.email="noreply@anthropic.com" \
      commit -q -m "Reparación automática: ${titulo:-ajuste del extractor a un cambio de formato del PDF}"
  destino="${EXTRACTOR_PUSH_URL:-https://x-access-token:${EXTRACTOR_TOKEN:-}@github.com/${EXTRACTOR_SLUG:-}.git}"
  # Otras corridas (un job por estado) pueden haber publicado su propio
  # arreglo mientras tanto: se rebasa sobre el main más reciente.
  export GIT_AUTHOR_NAME="Claude (agente OpenCodice)" GIT_COMMITTER_NAME="Claude (agente OpenCodice)"
  export GIT_AUTHOR_EMAIL="noreply@anthropic.com"
  export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
  # Con ocho jobs en paralelo y los registros de verificaciones, main puede
  # avanzar entre el pull y el push: se reintenta antes de dar el arreglo por
  # perdido.
  publicado=false
  for intento in 1 2 3; do
    if git pull -q --rebase "$destino" main && git push -q "$destino" HEAD:main; then
      publicado=true
      break
    fi
    git rebase --abort 2>/dev/null || true
    [ "$intento" = 3 ] || sleep $((intento * 5))
  done
  if [ "$publicado" = true ]; then
    estado_arreglo publicado
  else
    # El arreglo ya está en un commit: se guarda antes de deshacerlo.
    git format-patch -1 --stdout > "$TRABAJO/arreglo-descartado.patch" || true
    git reset -q --hard HEAD~1
    descartar "no se pudo publicar el arreglo en el extractor (chocó con otro arreglo publicado mientras tanto)"
  fi
}

publicar() {
  IFS=$'\t' read -r estado _ < <(estado_arreglo)
  if [ "$estado" = impacto ]; then
    python scripts/impacto.py cerrar --trabajo "$IMPACTO" \
      --extractor "OpenCodice/constitucion-extractor@$(git rev-parse HEAD)" \
      --reporte "$TRABAJO/impacto-arreglo.md"
    if [ $? -eq 0 ]; then
      estado=listo
    else
      descartar "no todo lo que cambia en el corpus quedó confirmado como mejora: $(tail -n +2 "$TRABAJO/impacto-arreglo.md" | head -c 400)"
    fi
  fi
  [ "$estado" = listo ] && publicar_arreglo
  IFS=$'\t' read -r estado motivo_descarte < <(estado_arreglo)
  [ "$estado" = descartado ] || motivo_descarte=""

  regenerar
  python -m extractor verificar --sin-llm --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" \
    --reporte "$TRABAJO/cobertura-final.md" > /dev/null
  cobertura_ok=$?
  revision=""
  if [ -f "$TRABAJO/alta" ]; then
    if [ -s "$TRABAJO/revision/previa.json" ]; then
      revision="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["motivo"])' "$TRABAJO/revision/previa.json") (revisión anterior con el mismo PDF y extractor)"
    else
      revision="$(python scripts/revision.py cerrar --repo "$RAIZ" --documento "$DOC" --pdf "$PDF" \
        --trabajo "$TRABAJO/revision")"
      rc=$?
      revision="${revision#✗ }"
      # Solo el 0 es una revisión sin hallazgos; un cierre que falla no lo es.
      if [ "$rc" = 0 ]; then
        revision=""
      elif [ "$rc" != 2 ] || [ -z "$revision" ]; then
        revision="no se pudo cerrar su revisión completa (código $rc)"
      fi
      bash scripts/agente/publicar_registro.sh \
        "Revisión completa de $DOC: $([ -z "$revision" ] && echo 'sin hallazgos' || echo 'con hallazgos, no se publica')"
    fi
    fiel=$([ -z "$revision" ] && echo true || echo false)
  else
    fiel="$(campo fiel)"
  fi

  ok=false
  if [ "$cobertura_ok" -eq 0 ] && [ "$fiel" = "true" ] && [ -z "$motivo_descarte" ] \
      && [ ! -e "$TRABAJO/regenerar-fallo" ]; then
    ok=true
  fi

  python - "$TRABAJO" "$REPORTE" "$ok" "$estado" "$motivo_descarte" "$revision" <<'PY'
import json, pathlib, sys
trabajo, reporte, ok, estado, descarte, revision = sys.argv[1:7]
t = pathlib.Path(trabajo)
try:
    v = json.loads((t / "veredicto.json").read_text(encoding="utf-8"))
except Exception:
    v = None
icono = {"fiel": "✅", "artefacto": "❌", "incierto": "❔"}
out = ["### 🤖 Verificación del agente contra el PDF", ""]
if ok == "true":
    out.append("La extracción quedó verificada: reproduce fielmente el PDF oficial.")
else:
    out.append("**La extracción NO quedó verificada — no se publica.**")
if (t / "alta").exists():
    out += ["", "Documento nuevo: revisión completa por bloques contra el PDF. "
            + (f"Resultado: {revision}" if revision else "Sin hallazgos en ningún bloque.")]
if v is None:
    if not (t / "alta").exists():
        out += ["", "El agente no entregó veredicto."]
else:
    out += ["", str(v.get("resumen", ""))]
    if estado == "publicado":
        out += ["", f"🔧 El agente reparó el extractor: _{v.get('titulo_commit', '')}_"]
    out.append("")
    for u in v.get("unidades", [])[:80]:
        out.append(f"- {icono.get(u.get('veredicto'), '❔')} **{u.get('clave')}** — {u.get('nota', '')}")
if (t / "impacto-arreglo.md").exists():
    out += ["", "Impacto del arreglo en las demás constituciones: "
            + (t / "impacto-arreglo.md").read_text(encoding="utf-8").strip()]
if descarte:
    out += ["", f"⚠️ Se descartó un arreglo del agente: {descarte}."]
out += ["", (t / "cobertura-final.md").read_text(encoding="utf-8")]
pathlib.Path(reporte).write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
PY

  [ "$ok" = "true" ] && return 0 || return 2
}

case "$FASE" in
  compuertas) compuertas; exit 0 ;;
  publicar) publicar; exit $? ;;
  *) echo "fase desconocida: $FASE" >&2; exit 64 ;;
esac

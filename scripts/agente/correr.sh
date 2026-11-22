#!/usr/bin/env bash
# Lanza al agente (Claude Code) para verificar la extracción contra el PDF y,
# si hay un defecto, repararlo en el código del extractor.
#
# Un documento que aún no está publicado (alta) no se verifica por sus
# artículos cambiados sino entero, por bloques (scripts/revision.py y
# brief-revision.md), en sesiones de REVISION_POR_SESION bloques. Si ya se
# revisó con el mismo PDF y el mismo extractor y tuvo hallazgos, no se vuelve
# a pagar la revisión: no se publica.
#
# Entorno: PDF, OUT, PERFIL, CLAUDE_CODE_OAUTH_TOKEN; opcionales BUILD_ARGS,
# AGENTE_DIR, AGENTE_MAX_TURNOS, AGENTE_MODELO, REVISION_POR_SESION. Este paso
# no debe recibir ningún otro secreto: el agente lee PDFs externos.
set -euo pipefail

EXTRACTOR="$(cd "$(dirname "$0")/../.." && pwd)"
TRABAJO="${AGENTE_DIR:-/tmp/agente}"
mkdir -p "$TRABAJO"
rm -f "$TRABAJO/veredicto.json" "$TRABAJO/alta"
cd "$EXTRACTOR"
export PYTHONPATH="$EXTRACTOR"
source scripts/agente/sesion.sh

git -C "$OUT" status --porcelain -- articulos > "$TRABAJO/cambiados.txt"
if [ ! -s "$TRABAJO/cambiados.txt" ]; then
  echo "Sin artículos cambiados: no hay nada que verificar."
  exit 0
fi

BUILD="python -m extractor build --pdf $PDF --out $OUT --perfil $PERFIL ${BUILD_ARGS:-}"
python -m extractor auditar --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" \
  --json "$TRABAJO/base.json"
python -m extractor verificar --sin-llm --pdf "$PDF" --out "$OUT" --perfil "$PERFIL" \
  --reporte "$TRABAJO/cobertura.md" > /dev/null || true

command -v claude > /dev/null || npm install -g @anthropic-ai/claude-code > /dev/null

DOCUMENTO="$([ "$PERFIL" = cpeum ] && echo cpeum || echo "$PERFIL/constitucion")"
# lanzar PASO BRIEF
lanzar() {
  sesion_agente "$1" "$TRABAJO/uso.jsonl" "$2" "$DOCUMENTO" \
    --max-turns "${AGENTE_MAX_TURNOS:-120}" \
    --permission-mode acceptEdits \
    --allowedTools Bash Read Edit Write Glob Grep \
    >> "$TRABAJO/agente.log" 2>&1 || echo "::warning::El agente terminó con error (ver $TRABAJO/agente.log)."
}

if ! git -C "$OUT" cat-file -e HEAD:./metadata/articulos.json 2>/dev/null; then
  touch "$TRABAJO/alta"
  RAIZ="$(git -C "$OUT" rev-parse --show-toplevel)"
  DOC="$([ "$PERFIL" = cpeum ] && echo cpeum || echo "$PERFIL/constitucion")"
  REV="$TRABAJO/revision"
  PLANEAR="python scripts/revision.py planear --repo $RAIZ --documento $DOC --pdf $PDF --trabajo $REV"
  previa="$(python scripts/revision.py previa --documento "$DOC" --pdf "$PDF")"
  if [ -n "$previa" ] && [ "$(echo "$previa" | python3 -c 'import json,sys; print(json.load(sys.stdin)["resultado"])')" != fiel ]; then
    echo "Revisión completa anterior con el mismo PDF y extractor: $previa"
    mkdir -p "$REV" && echo "$previa" > "$REV/previa.json"
    exit 0
  fi
  for n in $(seq 1 "${REVISION_SESIONES:-8}"); do
    $PLANEAR
    python3 scripts/agente/brief_revision.py "$REV" "$n" "${REVISION_POR_SESION:-8}" \
      __EXTRACTOR__="$EXTRACTOR" __OUT__="$OUT" __PDF__="$PDF" __PERFIL__="$PERFIL" \
      __BUILD__="$BUILD" __PLANEAR__="$PLANEAR" __TRABAJO_AGENTE__="$TRABAJO" __DOCUMENTO__="$DOC"
    [ -s "$REV/brief.md" ] || break
    lanzar revision-alta "$REV/brief.md"
  done
  tail -n 40 "$TRABAJO/agente.log" 2>/dev/null || true
  exit 0
fi

# Si todo lo que cambió son correcciones que ya se confirmaron contra este
# mismo PDF (impacto.yml las juzgó al entrar el cambio del extractor), no hay
# nada nuevo que revisar.
if python scripts/impacto.py ya-confirmadas "$(git -C "$OUT" rev-parse --show-toplevel)" \
    --documento "$([ "$PERFIL" = cpeum ] && echo cpeum || echo "$PERFIL/constitucion")" --pdf "$PDF"; then
  echo '{"fiel": true, "reparado": false, "resumen": "Todos los artículos cambiados son correcciones ya confirmadas contra este PDF (verificaciones/impacto/).", "unidades": []}' \
    > "$TRABAJO/veredicto.json"
  exit 0
fi

python - "$TRABAJO" "$EXTRACTOR" "$OUT" "$PDF" "$PERFIL" "$BUILD" <<'PY'
import pathlib, sys
trabajo, extractor, out, pdf, perfil, build = sys.argv[1:7]
t = pathlib.Path(trabajo)
brief = pathlib.Path(extractor, "scripts/agente/brief.md").read_text(encoding="utf-8")
for clave, valor in {
    "__EXTRACTOR__": extractor, "__OUT__": out, "__PDF__": pdf, "__PERFIL__": perfil,
    "__BUILD__": build, "__TRABAJO__": trabajo,
    "__CAMBIADOS__": (t / "cambiados.txt").read_text(encoding="utf-8").rstrip(),
    "__COBERTURA__": (t / "cobertura.md").read_text(encoding="utf-8").rstrip(),
}.items():
    brief = brief.replace(clave, valor)
(t / "brief.md").write_text(brief, encoding="utf-8")
PY

lanzar verificacion "$TRABAJO/brief.md"
tail -n 40 "$TRABAJO/agente.log" || true

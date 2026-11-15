#!/usr/bin/env bash
# Lanza al agente (Claude Code) para verificar la extracción contra el PDF y,
# si hay un defecto, repararlo en el código del extractor.
#
# Entorno: PDF, OUT, PERFIL, CLAUDE_CODE_OAUTH_TOKEN; opcionales BUILD_ARGS,
# AGENTE_DIR, AGENTE_MAX_TURNOS, AGENTE_MODELO. Este paso no debe recibir
# ningún otro secreto: el agente lee PDFs externos.
set -euo pipefail

EXTRACTOR="$(cd "$(dirname "$0")/../.." && pwd)"
TRABAJO="${AGENTE_DIR:-/tmp/agente}"
mkdir -p "$TRABAJO"
rm -f "$TRABAJO/veredicto.json"
cd "$EXTRACTOR"
export PYTHONPATH="$EXTRACTOR"

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

command -v claude > /dev/null || npm install -g @anthropic-ai/claude-code > /dev/null

claude -p "$(cat "$TRABAJO/brief.md")" \
  --max-turns "${AGENTE_MAX_TURNOS:-120}" \
  --permission-mode acceptEdits \
  --allowedTools Bash Read Edit Write Glob Grep \
  ${AGENTE_MODELO:+--model "$AGENTE_MODELO"} \
  > "$TRABAJO/agente.log" 2>&1 || echo "::warning::El agente terminó con error (ver $TRABAJO/agente.log)."
tail -n 40 "$TRABAJO/agente.log" || true

#!/usr/bin/env bash
# Despliega el Worker de una carpeta (worker.js y wrangler.jsonc) solo si su
# código no es el que Cloudflare ya tiene activo, y comprueba que el despliegue
# quedó registrado.
#
# Lo desplegado se reconoce por la etiqueta de su versión: la huella del
# código, que este mismo script le pone al desplegar. Así da igual por qué
# corre el workflow (un push que tocó otro Worker, un reintento del
# supervisor, una corrida a mano): cada Worker se publica cuando main y
# Cloudflare difieren, y nunca por un cambio ajeno.
#
# Uso: WRANGLER=wrangler@x.y.z scripts/desplegar_worker.sh <carpeta>
# Con CLOUDFLARE_API_TOKEN y CLOUDFLARE_ACCOUNT_ID. Escribe en $GITHUB_OUTPUT:
#   anterior=<id de la versión que estaba activa; vacío si no era una sola>
#   intentado=true    en cuanto va a desplegar: desde ahí Cloudflare puede
#                     tener el código nuevo aunque este script falle
#   desplegado=true|false
set -euo pipefail

cd "$1"
nombre=$(basename "$PWD")
wrangler() { npx --yes "$WRANGLER" "$@"; }
campo() { node -e 'const d = JSON.parse(require("fs").readFileSync(0, "utf8")); console.log((new Function("d", "return " + process.argv[1])(d)) ?? "")' "$1"; }

# La etiqueta de una versión admite pocos caracteres.
huella=$(cat worker.js wrangler.jsonc | sha256sum | cut -c1-24)

anterior=$(wrangler deployments status --json | campo 'd.versions.length === 1 ? d.versions[0].version_id : ""')
etiqueta=""
if [ -n "$anterior" ]; then
  etiqueta=$(wrangler versions view "$anterior" --json | campo 'd.annotations?.["workers/tag"]')
fi
echo "anterior=$anterior" >> "$GITHUB_OUTPUT"

if [ "$etiqueta" = "$huella" ]; then
  echo "El Worker $nombre ya tiene desplegado este código ($huella): no se despliega."
  echo "desplegado=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

despliegues() { wrangler deployments list --json | campo 'd.map((x) => x.id).sort().join("\n")'; }
antes=$(despliegues)
echo "intentado=true" >> "$GITHUB_OUTPUT"
wrangler deploy --tag "$huella" --message "${GITHUB_SHA:-a mano}"
nuevo=$(comm -13 <(echo "$antes") <(despliegues))
if [ -z "$nuevo" ]; then
  echo "::error::wrangler deploy terminó bien pero Cloudflare no lista ningún despliegue nuevo del Worker $nombre."
  exit 1
fi
echo "Despliegue nuevo de $nombre ($huella): $nuevo"
echo "desplegado=true" >> "$GITHUB_OUTPUT"

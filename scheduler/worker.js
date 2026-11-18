// Programador de la vigilancia de OpenCodice. El cron de GitHub Actions es de
// "mejor esfuerzo" y dejó de disparar sin aviso (además, en repos públicos se
// apaga tras 60 días sin commits), así que la vigilancia se lanza desde aquí con
// la API de GitHub (workflow_dispatch). Un vigilante diario relanza cualquier
// vigilancia que lleve demasiado sin correr.

const ORG = "OpenCodice";

// Qué se lanza y cuándo (UTC). `cron` debe estar también en wrangler.jsonc.
// En Cloudflare el día 1 es el domingo, no el lunes: se usan abreviaturas.
const VIGILANCIAS = [
  { repo: "fiscal-extractor", workflow: "vigilar-fiscal.yml", cron: "0 9 * * MON" },
  // La vigilancia vive en los extractores; cada una abre su PR en su repo de datos.
  { repo: "constitucion-extractor", workflow: "vigilar-cpeum.yml", cron: "0 9 * * MON" },
  { repo: "constitucion-extractor", workflow: "vigilar-estatales.yml", cron: "0 9 * * MON" },
  // Después de la fiscal: las dos publican arreglos en fiscal-extractor.
  { repo: "fiscal-extractor", workflow: "vigilar-federal.yml", cron: "0 13 * * MON" },
  // Las demás leyes de cada estado; el agente no repara el extractor aquí, así que
  // no compite con la federal por fiscal-extractor.
  { repo: "fiscal-extractor", workflow: "vigilar-leyes-estatales.yml", cron: "0 13 * * MON" },
  // Cada hora: lee el archivo de páginas del Congreso (Worker congreso-archivo)
  // y le pide lo que falta; publica una vez al día, a las 18:00, después de las
  // vigilancias de leyes de los lunes (liga los decretos con sus commits).
  { repo: "congreso-extractor", workflow: "actualizar-congreso.yml", cron: "0 * * * *",
    inputs: (hora) => ({ publicar: hora === 18 ? "si" : "no" }) },
];

// El vigilante: si una vigilancia lleva más de esto sin ninguna corrida, se lanza.
const VIGILANTE = "30 15 * * *";
const MAX_DIAS_SIN_CORRER = 8;

// Rondas semanales que no son vigilancias: van con el cron diario del vigilante
// el día indicado (getUTCDay: 0 = domingo), para no gastar otro Cron Trigger
// (Cloudflare Free admite pocos por cuenta). El vigilante no las relanza: si
// una no corre, la de la semana siguiente hace lo mismo.
const RONDAS = [
  // Ronda de expansión: suma un estado al corpus de leyes estatales si terminó
  // la cadena de vigilancias del anterior (lo decide el propio workflow).
  { repo: "fiscal-extractor", workflow: "expandir-estatales.yml", dia: 3 },
];

async function github(env, ruta, opciones = {}) {
  const r = await fetch(`https://api.github.com${ruta}`, {
    ...opciones,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "opencodice-scheduler",
      ...(opciones.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!r.ok) throw new Error(`${opciones.method ?? "GET"} ${ruta}: ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

async function lanzar(env, v, motivo, hora = new Date().getUTCHours()) {
  await github(env, `/repos/${ORG}/${v.repo}/actions/workflows/${v.workflow}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: "main", ...(v.inputs ? { inputs: v.inputs(hora) } : {}) }),
  });
  console.log(`lanzada ${v.repo}/${v.workflow} (${motivo})`);
}

async function vigilante(env) {
  const ahora = Date.now();
  for (const v of VIGILANCIAS) {
    const { workflow_runs: runs } = await github(
      env, `/repos/${ORG}/${v.repo}/actions/workflows/${v.workflow}/runs?per_page=1`);
    const ultima = runs[0];
    const dias = ultima ? (ahora - Date.parse(ultima.created_at)) / 86_400_000 : Infinity;
    if (ultima && ultima.status !== "completed") continue;
    if (dias > MAX_DIAS_SIN_CORRER) await lanzar(env, v, `sin correr hace ${dias.toFixed(1)} días`);
  }
}

export default {
  async scheduled(evento, env) {
    const dia = new Date(evento.scheduledTime).getUTCDay();
    const toca = evento.cron === VIGILANTE
      ? RONDAS.filter((r) => r.dia === dia)
      : VIGILANCIAS.filter((v) => v.cron === evento.cron);
    if (evento.cron === VIGILANTE) {
      try {
        await vigilante(env);
      } catch (e) {
        console.error(e);
      }
    }
    // Una falla no detiene las demás; queda en los logs del Worker.
    const hora = new Date(evento.scheduledTime).getUTCHours();
    const resultados = await Promise.allSettled(toca.map((v) => lanzar(env, v, `cron ${evento.cron}`, hora)));
    for (const r of resultados) if (r.status === "rejected") console.error(r.reason);
  },
};

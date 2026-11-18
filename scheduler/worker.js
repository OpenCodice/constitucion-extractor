// Reloj de OpenCodice. El cron de GitHub Actions es de "mejor esfuerzo" y dejó
// de disparar sin aviso (además, en repos públicos se apaga tras 60 días sin
// commits), así que el tic sale de aquí: cada 15 minutos lanza al supervisor
// con la API de GitHub (workflow_dispatch), y el supervisor decide qué más
// tiene que correr. También lo vigila: si deja de correr, abre un issue.

const ORG = "OpenCodice";
const ORIGEN = "scheduler";

// El único Cron Trigger del Worker (UTC). Debe ser el mismo que en
// wrangler.jsonc: lo comprueba worker.test.mjs.
export const TIC = "*/15 * * * *";
export const CRONS = [TIC];

export const SUPERVISOR = { repo: "supervisor", workflow: "supervisor.yml", inputs: { origen: ORIGEN } };

// Hombre muerto: sin una corrida exitosa del supervisor en este tiempo, se
// avisa en un issue de su repo, como mucho una vez cada SILENCIO_AVISO_HORAS.
export const TITULO_HOMBRE_MUERTO = "🚨 El supervisor no corre";
const MAX_HORAS_SIN_SUPERVISOR = 3;
const SILENCIO_AVISO_HORAS = 6;

// Todo cabe con holgura antes del tic siguiente, aunque cada intento agote su
// tiempo.
export const ESPERA_REINTENTO_MS = [2_000, 5_000, 15_000];
// Una petición que no contesta no puede detener el tic.
const MAX_MS_POR_PETICION = 20_000;

const HORA_MS = 3_600_000;

// Qué hacer con el issue del hombre muerto: "abrir", "comentar", "cerrar" o
// "nada". `ultimaExitosa` es la fecha (ms) de la última corrida exitosa del
// supervisor, o null; `issue`, el que esté abierto con ese título (con
// `ultimoAviso`: la fecha de su último comentario o, si no tiene, la suya), o null.
export function decidirHombreMuerto({ ahora, ultimaExitosa, issue }) {
  const vivo = ultimaExitosa != null && ahora - ultimaExitosa <= MAX_HORAS_SIN_SUPERVISOR * HORA_MS;
  if (vivo) return issue ? "cerrar" : "nada";
  if (!issue) return "abrir";
  return ahora - issue.ultimoAviso >= SILENCIO_AVISO_HORAS * HORA_MS ? "comentar" : "nada";
}

// Una falla de red, un límite de peticiones o un error del servidor pueden
// pasar al reintentar; un 401, 403, 404 o 422 no.
export function reintentable(status) {
  return status === undefined || status === 408 || status === 429 || status >= 500;
}

async function github(env, ruta, opciones = {}) {
  const r = await fetch(`https://api.github.com${ruta}`, {
    ...opciones,
    signal: AbortSignal.timeout(MAX_MS_POR_PETICION),
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "opencodice-scheduler",
      ...(opciones.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!r.ok) {
    const e = new Error(`${opciones.method ?? "GET"} ${ruta}: ${r.status} ${await r.text()}`);
    e.status = r.status;
    throw e;
  }
  return r.status === 204 ? null : r.json();
}

const dormir = (ms) => new Promise((listo) => setTimeout(listo, ms));

async function lanzarSupervisor(env, esperar) {
  const ruta = `/repos/${ORG}/${SUPERVISOR.repo}/actions/workflows/${SUPERVISOR.workflow}/dispatches`;
  for (let intento = 0; ; intento += 1) {
    try {
      await github(env, ruta, { method: "POST", body: JSON.stringify({ ref: "main", inputs: SUPERVISOR.inputs }) });
      console.log(`lanzado ${SUPERVISOR.repo}/${SUPERVISOR.workflow}`);
      return;
    } catch (e) {
      if (intento >= ESPERA_REINTENTO_MS.length || !reintentable(e.status)) throw e;
      await esperar(ESPERA_REINTENTO_MS[intento]);
    }
  }
}

async function hombreMuerto(env, ahora) {
  const repo = `/repos/${ORG}/${SUPERVISOR.repo}`;
  const { workflow_runs: exitosas } = await github(
    env, `${repo}/actions/workflows/${SUPERVISOR.workflow}/runs?status=success&per_page=1`);
  const ultimaExitosa = exitosas[0] ? Date.parse(exitosas[0].created_at) : null;
  const abiertos = await github(env, `${repo}/issues?state=open&per_page=100`);
  const abierto = abiertos.find((i) => i.title === TITULO_HOMBRE_MUERTO && !i.pull_request);

  let issue = null;
  if (abierto) {
    // El Worker no guarda estado: cuándo avisó por última vez se lee del issue.
    const desde = new Date(ahora - SILENCIO_AVISO_HORAS * HORA_MS).toISOString();
    const recientes = await github(env, `${repo}/issues/${abierto.number}/comments?since=${desde}&per_page=100`);
    issue = { ultimoAviso: Math.max(Date.parse(abierto.created_at), ...recientes.map((c) => Date.parse(c.created_at))) };
  }

  const accion = decidirHombreMuerto({ ahora, ultimaExitosa, issue });
  const ultima = ultimaExitosa ? `la última fue el ${new Date(ultimaExitosa).toISOString()}` : "no tiene ninguna";
  const sinCorrer = `\`${SUPERVISOR.workflow}\` no tiene una corrida exitosa en las últimas ${MAX_HORAS_SIN_SUPERVISOR} horas (${ultima}).`;
  const escribir = (ruta, method, cuerpo) => github(env, ruta, { method, body: JSON.stringify(cuerpo) });
  if (accion === "abrir") {
    await escribir(`${repo}/issues`, "POST", {
      title: TITULO_HOMBRE_MUERTO,
      body: `${sinCorrer}\n\nLo lanza cada 15 minutos el Worker \`scheduler\` (constitucion-extractor/scheduler). ` +
        "Mientras no corra, nada lanza ni relanza las cadenas. Este issue se cierra solo cuando vuelva a correr bien.",
    });
  } else if (accion === "comentar") {
    await escribir(`${repo}/issues/${abierto.number}/comments`, "POST", { body: `Sigue sin correr: ${sinCorrer}` });
  } else if (accion === "cerrar") {
    await escribir(`${repo}/issues/${abierto.number}/comments`, "POST",
      { body: `El supervisor volvió a correr bien (${ultima}).` });
    await escribir(`${repo}/issues/${abierto.number}`, "PATCH", { state: "closed" });
  }
  if (accion !== "nada") console.log(`hombre muerto: ${accion}`);
}

// Un tic: lanza al supervisor y revisa el hombre muerto, a la vez y cada uno
// por su cuenta, para que ni la falla ni la tardanza de uno alcancen al otro.
// No lee nada de un tic anterior: el siguiente empieza igual, haya pasado lo
// que haya pasado en este.
export async function tic(env, { ahora = Date.now(), esperar = dormir } = {}) {
  const [lanzamiento, aviso] = await Promise.allSettled([lanzarSupervisor(env, esperar), hombreMuerto(env, ahora)]);
  if (lanzamiento.status === "rejected") console.error("no se pudo lanzar al supervisor:", lanzamiento.reason);
  // Con un token sin permiso de Issues (403) no hay dónde avisar: queda en
  // los registros.
  if (aviso.status === "rejected") console.error("hombre muerto:", aviso.reason);
  return { lanzado: lanzamiento.status === "fulfilled", hombreMuerto: aviso.status === "fulfilled" };
}

export default {
  async scheduled(_evento, env) {
    await tic(env);
  },
};

// Reloj de OpenCodice. El cron de GitHub Actions es de "mejor esfuerzo" y dejó
// de disparar sin aviso (además, en repos públicos se apaga tras 60 días sin
// commits), así que el tic sale de aquí: cada 15 minutos lanza al supervisor
// con la API de GitHub (workflow_dispatch), y el supervisor decide qué más
// tiene que correr. También lo vigila: si deja de correr, abre un issue. Y
// avisa, en otro issue, un mes antes de que venza su propio token.

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
const DIA_MS = 24 * HORA_MS;

// El token del Worker: GitHub dice cuándo vence en esta cabecera de cualquier
// respuesta autenticada (no viene si el token no vence). Con menos de
// AVISO_VENCIMIENTO_DIAS por delante se avisa en un issue del supervisor, como
// mucho una vez cada SILENCIO_VENCIMIENTO_DIAS.
export const CABECERA_VENCIMIENTO = "github-authentication-token-expiration";
export const PREFIJO_VENCIMIENTO = "🔑 El token del scheduler vence el ";
const AVISO_VENCIMIENTO_DIAS = 30;
const SILENCIO_VENCIMIENTO_DIAS = 7;

// La fecha (ms) de la cabecera: `2027-11-20 06:00:00 UTC` o
// `2027-11-20 00:00:00 -0600`; sin zona, UTC. null si no hay cabecera (el
// token no vence) y NaN si no se entiende.
export function leerVencimiento(cabecera) {
  if (cabecera == null || String(cabecera).trim() === "") return null;
  const m = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*(UTC|GMT|Z|[+-]\d{2}:?\d{2})?$/.exec(String(cabecera).trim());
  if (!m) return NaN;
  const zona = !m[3] || /^[A-Z]+$/.test(m[3]) ? "Z" : `${m[3].slice(0, 3)}:${m[3].slice(-2)}`;
  return Date.parse(`${m[1]}T${m[2]}${zona}`);
}

export const tituloVencimiento = (vence) => `${PREFIJO_VENCIMIENTO}${new Date(vence).toISOString().slice(0, 10)}`;

// Qué hacer con el issue del vencimiento: "abrir", "comentar", "cerrar",
// "reabrir" (cerrar el de la fecha vieja y abrir el de la nueva) o "nada".
// `vence` es la fecha (ms) en que vence el token, o null si no vence; `issue`,
// el que esté abierto con ese prefijo (`titulo` y `ultimoAviso`, como en el
// hombre muerto), o null.
export function decidirVencimiento({ ahora, vence, issue }) {
  const porVencer = vence != null && vence - ahora < AVISO_VENCIMIENTO_DIAS * DIA_MS;
  if (!porVencer) return issue ? "cerrar" : "nada";
  if (!issue) return "abrir";
  if (issue.titulo !== tituloVencimiento(vence)) return "reabrir";
  return ahora - issue.ultimoAviso >= SILENCIO_VENCIMIENTO_DIAS * DIA_MS ? "comentar" : "nada";
}

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

// Las peticiones de un tic a la API de GitHub. `token` guarda lo que la primera
// respuesta aceptada dijo del token: no hace falta una petición aparte.
function cliente(env) {
  const token = { visto: false, cabecera: null };
  const github = async (ruta, opciones = {}) => {
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
    if (!token.visto) Object.assign(token, { visto: true, cabecera: r.headers.get(CABECERA_VENCIMIENTO) });
    return r.status === 204 ? null : r.json();
  };
  return { github, token };
}

const dormir = (ms) => new Promise((listo) => setTimeout(listo, ms));

// Cuándo se avisó por última vez en un issue (el Worker no guarda estado: se
// lee del issue): la fecha de su último comentario desde `desde` o, si no
// tiene, la suya.
async function ultimoAviso(github, repo, issue, desde) {
  const recientes = await github(`${repo}/issues/${issue.number}/comments?since=${new Date(desde).toISOString()}&per_page=100`);
  return Math.max(Date.parse(issue.created_at), ...recientes.map((c) => Date.parse(c.created_at)));
}

async function lanzarSupervisor(github, esperar) {
  const ruta = `/repos/${ORG}/${SUPERVISOR.repo}/actions/workflows/${SUPERVISOR.workflow}/dispatches`;
  for (let intento = 0; ; intento += 1) {
    try {
      await github(ruta, { method: "POST", body: JSON.stringify({ ref: "main", inputs: SUPERVISOR.inputs }) });
      console.log(`lanzado ${SUPERVISOR.repo}/${SUPERVISOR.workflow}`);
      return;
    } catch (e) {
      if (intento >= ESPERA_REINTENTO_MS.length || !reintentable(e.status)) throw e;
      await esperar(ESPERA_REINTENTO_MS[intento]);
    }
  }
}

const REPO_SUPERVISOR = `/repos/${ORG}/${SUPERVISOR.repo}`;

// Devuelve los issues abiertos que leyó, para que el aviso de vencimiento no
// tenga que pedirlos otra vez.
async function hombreMuerto(github, ahora) {
  const repo = REPO_SUPERVISOR;
  const { workflow_runs: exitosas } = await github(
    `${repo}/actions/workflows/${SUPERVISOR.workflow}/runs?status=success&per_page=1`);
  const ultimaExitosa = exitosas[0] ? Date.parse(exitosas[0].created_at) : null;
  const abiertos = await github(`${repo}/issues?state=open&per_page=100`);
  const abierto = abiertos.find((i) => i.title === TITULO_HOMBRE_MUERTO && !i.pull_request);

  const issue = abierto
    ? { ultimoAviso: await ultimoAviso(github, repo, abierto, ahora - SILENCIO_AVISO_HORAS * HORA_MS) }
    : null;

  const accion = decidirHombreMuerto({ ahora, ultimaExitosa, issue });
  const ultima = ultimaExitosa ? `la última fue el ${new Date(ultimaExitosa).toISOString()}` : "no tiene ninguna";
  const sinCorrer = `\`${SUPERVISOR.workflow}\` no tiene una corrida exitosa en las últimas ${MAX_HORAS_SIN_SUPERVISOR} horas (${ultima}).`;
  const escribir = (ruta, method, cuerpo) => github(ruta, { method, body: JSON.stringify(cuerpo) });
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
  return abiertos;
}

// Avisa de que el token del Worker está por vencer. `token` es lo que las
// respuestas de este tic dijeron de él; `abiertos`, los issues abiertos del
// supervisor si el hombre muerto ya los leyó.
async function avisoVencimiento(github, ahora, token, abiertos) {
  // Sin ninguna respuesta aceptada no se sabe nada del token (y, si ya
  // venció, tampoco hay con qué avisar).
  if (!token.visto) return;
  const vence = leerVencimiento(token.cabecera);
  if (Number.isNaN(vence)) throw new Error(`${CABECERA_VENCIMIENTO} ilegible: ${token.cabecera}`);
  const repo = REPO_SUPERVISOR;
  abiertos ??= await github(`${repo}/issues?state=open&per_page=100`);
  const abierto = abiertos.find((i) => i.title.startsWith(PREFIJO_VENCIMIENTO) && !i.pull_request);

  let issue = null;
  if (abierto) {
    // Solo hace falta saber cuándo se avisó si el aviso sigue siendo el mismo.
    const mismo = vence != null && abierto.title === tituloVencimiento(vence);
    issue = {
      titulo: abierto.title,
      ultimoAviso: mismo ? await ultimoAviso(github, repo, abierto, ahora - SILENCIO_VENCIMIENTO_DIAS * DIA_MS) : ahora,
    };
  }

  const accion = decidirVencimiento({ ahora, vence, issue });
  const escribir = (ruta, method, cuerpo) => github(ruta, { method, body: JSON.stringify(cuerpo) });
  const cuando = vence == null ? "" : `el ${new Date(vence).toISOString().replace("T", " ").slice(0, 16)} UTC`;
  const faltan = vence == null ? "" : `faltan ${Math.floor((vence - ahora) / DIA_MS)} días`;
  if (accion === "cerrar" || accion === "reabrir") {
    await escribir(`${repo}/issues/${abierto.number}/comments`, "POST", {
      body: vence == null ? "El token del scheduler ya no vence." : `El token del scheduler se renovó: ahora vence ${cuando}.`,
    });
    await escribir(`${repo}/issues/${abierto.number}`, "PATCH", { state: "closed" });
  }
  if (accion === "abrir" || accion === "reabrir") {
    await escribir(`${repo}/issues`, "POST", {
      title: tituloVencimiento(vence),
      body: `El token de GitHub del Worker \`scheduler\` (su secret \`GITHUB_TOKEN\`) vence ${cuando} (${faltan}). ` +
        "Con él lanza al supervisor cada 15 minutos y abre el issue del hombre muerto: cuando venza fallan las dos " +
        "cosas a la vez, y solo queda el cron de respaldo de `supervisor.yml`.\n\n" +
        "**Qué necesita el nuevo.** Un fine-grained PAT (`opencodice-scheduler`) de la organización OpenCodice, " +
        "solo sobre el repo `supervisor`, con Actions: read and write e Issues: read and write.\n\n" +
        "**Cómo se cambia.** `npx wrangler secret put GITHUB_TOKEN` desde `constitucion-extractor/scheduler/` " +
        "(no hace falta desplegar).\n\n" +
        "Este issue se cierra solo cuando el Worker vea otra fecha de vencimiento.",
    });
  } else if (accion === "comentar") {
    await escribir(`${repo}/issues/${abierto.number}/comments`, "POST",
      { body: `El token del scheduler sigue sin renovarse: vence ${cuando} (${faltan}).` });
  }
  if (accion !== "nada") console.log(`vencimiento del token: ${accion}`);
}

// Un tic: lanza al supervisor y revisa el hombre muerto, a la vez y cada uno
// por su cuenta, para que ni la falla ni la tardanza de uno alcancen al otro.
// Después, también por su cuenta, mira cuándo vence el token con lo que esas
// respuestas dijeron de él. No lee nada de un tic anterior: el siguiente
// empieza igual, haya pasado lo que haya pasado en este.
export async function tic(env, { ahora = Date.now(), esperar = dormir } = {}) {
  const { github, token } = cliente(env);
  const [lanzamiento, aviso] = await Promise.allSettled([lanzarSupervisor(github, esperar), hombreMuerto(github, ahora)]);
  if (lanzamiento.status === "rejected") console.error("no se pudo lanzar al supervisor:", lanzamiento.reason);
  // Con un token sin permiso de Issues (403) no hay dónde avisar: queda en
  // los registros.
  if (aviso.status === "rejected") console.error("hombre muerto:", aviso.reason);
  const [vencimiento] = await Promise.allSettled([
    avisoVencimiento(github, ahora, token, aviso.status === "fulfilled" ? aviso.value : null)]);
  if (vencimiento.status === "rejected") console.error("vencimiento del token:", vencimiento.reason);
  return {
    lanzado: lanzamiento.status === "fulfilled",
    hombreMuerto: aviso.status === "fulfilled",
    vencimiento: vencimiento.status === "fulfilled",
  };
}

export default {
  async scheduled(_evento, env) {
    await tic(env);
  },
};

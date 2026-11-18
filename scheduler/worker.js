// Reloj de OpenCodice. El cron de GitHub Actions es de "mejor esfuerzo" y dejó
// de disparar sin aviso (además, en repos públicos se apaga tras 60 días sin
// commits), así que todo lo periódico se lanza desde aquí con la API de GitHub
// (workflow_dispatch): el supervisor cada 15 minutos, las vigilancias cada
// lunes y la ronda de expansión los miércoles. También vigila al supervisor:
// si deja de correr, abre un issue.

const ORG = "OpenCodice";
const ORIGEN = "scheduler";

// Los Cron Triggers del Worker (UTC). Deben ser los mismos que en
// wrangler.jsonc: lo comprueba worker.test.mjs.
export const TIC = "*/15 * * * *";
export const DIARIO = "30 15 * * *";

// Qué vigilancia se lanza con qué cron. En Cloudflare el día 1 es el domingo,
// no el lunes: se usan abreviaturas.
export const VIGILANCIAS = [
  { repo: "fiscal-extractor", workflow: "vigilar-fiscal.yml", cron: "0 9 * * MON" },
  // La vigilancia vive en los extractores; cada una abre su PR en su repo de datos.
  { repo: "constitucion-extractor", workflow: "vigilar-cpeum.yml", cron: "0 9 * * MON" },
  { repo: "constitucion-extractor", workflow: "vigilar-estatales.yml", cron: "0 9 * * MON" },
  // Después de la fiscal: las dos publican arreglos en fiscal-extractor.
  { repo: "fiscal-extractor", workflow: "vigilar-federal.yml", cron: "0 13 * * MON" },
  // Las demás leyes de cada estado; el agente no repara el extractor aquí, así que
  // no compite con la federal por fiscal-extractor.
  { repo: "fiscal-extractor", workflow: "vigilar-leyes-estatales.yml", cron: "0 13 * * MON" },
];

export const CRONS = [...new Set([...VIGILANCIAS.map((v) => v.cron), TIC, DIARIO])];

// Con cada tic. Mientras su repo no exista o su workflow esté deshabilitado,
// GitHub contesta 404 o 422: no es un error del reloj.
const SUPERVISOR = { repo: "supervisor", workflow: "supervisor.yml", opcional: true };

// En el tic del minuto 0: lee el archivo de páginas del Congreso (Worker
// congreso-archivo) y le pide lo que falta; publica una vez al día, a las
// 18:00, después de las vigilancias de leyes de los lunes (liga los decretos
// con sus commits).
const CONGRESO = {
  repo: "congreso-extractor", workflow: "actualizar-congreso.yml",
  inputs: (hora) => ({ publicar: hora === 18 ? "si" : "no" }),
};

// Rondas semanales que no son vigilancias: van con el cron diario el día
// indicado (getUTCDay: 0 = domingo), para no gastar otro Cron Trigger
// (Cloudflare Free admite pocos por cuenta). El vigilante no las relanza: si
// una no corre, la de la semana siguiente hace lo mismo.
export const RONDAS = [
  // Ronda de expansión: suma un estado al corpus de leyes estatales si terminó
  // la cadena de vigilancias del anterior (lo decide el propio workflow).
  { repo: "fiscal-extractor", workflow: "expandir-estatales.yml", dia: 3 },
];

// El vigilante: si una vigilancia lleva más de esto sin ninguna corrida, se lanza.
const MAX_DIAS_SIN_CORRER = 8;
// Una corrida sin terminar más vieja que esto está colgada: ya no cuenta como
// "en curso" (un job de GitHub no dura más de 6 h).
const MAX_HORAS_EN_CURSO = 12;

// Hombre muerto: sin una corrida exitosa del supervisor en este tiempo, se
// avisa en un issue de su repo, como mucho una vez cada SILENCIO_AVISO_HORAS.
export const TITULO_HOMBRE_MUERTO = "🚨 El supervisor no corre";
const MAX_HORAS_SIN_SUPERVISOR = 3;
const SILENCIO_AVISO_HORAS = 6;

const REINTENTOS = 2;
const ESPERA_REINTENTO_MS = [2_000, 5_000];

const HORA_MS = 3_600_000;

function lanzamiento(v, hora) {
  return {
    repo: v.repo,
    workflow: v.workflow,
    inputs: { ...(v.inputs ? v.inputs(hora) : {}), origen: ORIGEN },
    ...(v.opcional ? { opcional: true } : {}),
  };
}

// Qué toca en un disparo: los workflows que se lanzan (con sus inputs) y si
// corren el vigilante de 8 días y el hombre muerto. El hombre muerto va solo
// con el tic, que también cae a las 15:30: con el cron diario a la vez, dos
// ejecuciones simultáneas abrirían el issue dos veces.
export function queToca(cron, scheduledTime) {
  const t = new Date(scheduledTime);
  const hora = t.getUTCHours();
  if (cron === TIC) {
    const toca = [SUPERVISOR, ...(t.getUTCMinutes() === 0 ? [CONGRESO] : [])];
    return { lanzamientos: toca.map((v) => lanzamiento(v, hora)), vigilante: false, hombreMuerto: true };
  }
  if (cron === DIARIO) {
    const toca = RONDAS.filter((r) => r.dia === t.getUTCDay());
    return { lanzamientos: toca.map((v) => lanzamiento(v, hora)), vigilante: true, hombreMuerto: false };
  }
  const toca = VIGILANCIAS.filter((v) => v.cron === cron);
  return { lanzamientos: toca.map((v) => lanzamiento(v, hora)), vigilante: false, hombreMuerto: false };
}

// Por qué el vigilante debe lanzar una vigilancia, o null si no debe. `ultima`
// es su corrida más reciente (o undefined si no tiene ninguna).
export function motivoRelanzar(ultima, ahora) {
  if (!ultima) return "sin ninguna corrida";
  const edad = ahora - Date.parse(ultima.created_at);
  if (ultima.status !== "completed" && edad <= MAX_HORAS_EN_CURSO * HORA_MS) return null;
  const dias = edad / (24 * HORA_MS);
  return dias > MAX_DIAS_SIN_CORRER ? `sin correr hace ${dias.toFixed(1)} días` : null;
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
  if (!r.ok) {
    const e = new Error(`${opciones.method ?? "GET"} ${ruta}: ${r.status} ${await r.text()}`);
    e.status = r.status;
    throw e;
  }
  return r.status === 204 ? null : r.json();
}

const esperar = (ms) => new Promise((listo) => setTimeout(listo, ms));

async function lanzar(env, l, motivo) {
  const ruta = `/repos/${ORG}/${l.repo}/actions/workflows/${l.workflow}/dispatches`;
  let inputs = l.inputs;
  for (let intento = 0; ; ) {
    try {
      await github(env, ruta, { method: "POST", body: JSON.stringify({ ref: "main", inputs }) });
      console.log(`lanzada ${l.repo}/${l.workflow} (${motivo})`);
      return;
    } catch (e) {
      if (e.status === 422 && "origen" in inputs && e.message.includes("Unexpected inputs")) {
        // Un workflow que todavía no declara `origen` rechaza el lanzamiento
        // entero: se lanza sin él antes que dejarlo sin correr.
        const { origen, ...resto } = inputs;
        inputs = resto;
        console.warn(`${l.repo}/${l.workflow} no declara el input origen=${origen}; se lanza sin él`);
        continue;
      }
      if (intento >= REINTENTOS || !reintentable(e.status)) throw e;
      await esperar(ESPERA_REINTENTO_MS[intento]);
      intento += 1;
    }
  }
}

async function vigilante(env, ahora) {
  const hora = new Date(ahora).getUTCHours();
  for (const v of [...VIGILANCIAS, CONGRESO]) {
    // Un error con una vigilancia no impide revisar las demás.
    try {
      const { workflow_runs: runs } = await github(
        env, `/repos/${ORG}/${v.repo}/actions/workflows/${v.workflow}/runs?per_page=1`);
      const motivo = motivoRelanzar(runs[0], ahora);
      if (motivo) await lanzar(env, lanzamiento(v, hora), motivo);
    } catch (e) {
      console.error(`vigilante, ${v.repo}/${v.workflow}:`, e);
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
        "Mientras no corra, nada relanza las cadenas que fallen. Este issue se cierra solo cuando vuelva a correr bien.",
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

export default {
  async scheduled(evento, env) {
    const toca = queToca(evento.cron, evento.scheduledTime);
    // Una falla no detiene lo demás; queda en los logs del Worker.
    const resultados = await Promise.allSettled(
      toca.lanzamientos.map((l) => lanzar(env, l, `cron ${evento.cron}`)));
    resultados.forEach((r, i) => {
      if (r.status !== "rejected") return;
      const l = toca.lanzamientos[i];
      if (l.opcional && [404, 422].includes(r.reason.status)) {
        console.warn(`${l.repo}/${l.workflow} aún no se puede lanzar (${r.reason.status})`);
      } else {
        console.error(r.reason);
      }
    });
    if (toca.vigilante) await vigilante(env, Date.now());
    if (toca.hombreMuerto) {
      try {
        await hombreMuerto(env, Date.now());
      } catch (e) {
        // Con un token sin permiso de Issues (403) o sin el repo del
        // supervisor (404) no hay dónde avisar: se registra y el tic sigue.
        console.error("hombre muerto:", e);
      }
    }
  },
};

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { afterEach, test } from "node:test";

import worker, {
  CRONS, ESPERA_REINTENTO_MS, SUPERVISOR, TIC, TITULO_HOMBRE_MUERTO,
  decidirHombreMuerto, reintentable, tic,
} from "./worker.js";

const utc = (texto) => Date.parse(`${texto}:00Z`);
const HORA = 3_600_000;
const API = "https://api.github.com/repos/OpenCodice/supervisor";
const DISPATCH = `POST ${API}/actions/workflows/supervisor.yml/dispatches`;

const fetchReal = globalThis.fetch;
afterEach(() => { globalThis.fetch = fetchReal; });

const json = (cuerpo, status = 200) => new Response(JSON.stringify(cuerpo), { status });

// Un GitHub de mentira. `dispatch` contesta cada lanzamiento (recibe cuántos
// van); `exitosa` es la fecha de la última corrida exitosa del supervisor y
// `issue`, el del hombre muerto si está abierto. Devuelve las peticiones.
function github({ dispatch = () => new Response(null, { status: 204 }), exitosa = null, issue = null, lectura } = {}) {
  const peticiones = [];
  let lanzamientos = 0;
  globalThis.fetch = async (url, opciones = {}) => {
    const metodo = opciones.method ?? "GET";
    const peticion = { clave: `${metodo} ${String(url).split("?")[0]}`, cuerpo: opciones.body ? JSON.parse(opciones.body) : null };
    peticiones.push(peticion);
    if (peticion.clave === DISPATCH) return dispatch(lanzamientos++);
    if (metodo !== "GET") return json({});
    if (lectura) return lectura();
    if (peticion.clave.endsWith("/runs")) {
      return json({ workflow_runs: exitosa == null ? [] : [{ created_at: new Date(exitosa).toISOString() }] });
    }
    if (peticion.clave.endsWith("/issues")) return json(issue ? [issue] : []);
    return json([]);
  };
  return peticiones;
}

const lanzamientos = (peticiones) => peticiones.filter((p) => p.clave === DISPATCH);
const escrituras = (peticiones) => peticiones.filter((p) => !p.clave.startsWith("GET ") && p.clave !== DISPATCH);
const sinEsperar = () => {
  const esperas = [];
  return { esperas, esperar: async (ms) => { esperas.push(ms); } };
};
// Los registros de las fallas que estas pruebas provocan no van a la salida.
const callado = async (t, f) => {
  t.mock.method(console, "error", () => {});
  t.mock.method(console, "log", () => {});
  return f();
};

// 2026-11-15 es domingo; 16, lunes; 18, miércoles.
const FECHAS = [
  ["lunes 09:00", "2026-11-16T09:00"],
  ["lunes 13:00", "2026-11-16T13:00"],
  ["lunes 09:15", "2026-11-16T09:15"],
  ["martes 18:00", "2026-11-17T18:00"],
  ["miércoles 15:30", "2026-11-18T15:30"],
  ["domingo 00:00", "2026-11-15T00:00"],
  ["domingo 23:45", "2026-11-15T23:45"],
  ["día 1 del mes, 10:00", "2026-12-01T10:00"],
];

for (const [caso, fecha] of FECHAS) {
  test(`el tic solo lanza al supervisor: ${caso}`, async (t) => {
    const ahora = utc(fecha);
    const peticiones = github({ exitosa: ahora - HORA / 4 });
    // El Worker toma la hora del reloj, no del evento.
    t.mock.timers.enable({ apis: ["Date"], now: ahora });
    await callado(t, () => worker.scheduled({ cron: TIC, scheduledTime: ahora }, { GITHUB_TOKEN: "x" }));
    assert.deepEqual(lanzamientos(peticiones).map((p) => p.cuerpo), [{ ref: "main", inputs: { origen: "scheduler" } }]);
    assert.deepEqual(escrituras(peticiones), []);
    for (const p of peticiones) assert.ok(p.clave.includes(`${API}/`), p.clave);
  });
}

test("el supervisor se lanza con origen=scheduler y nada más", () => {
  assert.deepEqual(SUPERVISOR, { repo: "supervisor", workflow: "supervisor.yml", inputs: { origen: "scheduler" } });
});

test("un solo cron, el mismo en wrangler.jsonc y en worker.js", () => {
  const texto = readFileSync(new URL("./wrangler.jsonc", import.meta.url), "utf8");
  // Quita los comentarios de línea sin tocar las cadenas.
  const limpio = texto.replace(/("(?:[^"\\]|\\.)*")|\/\/[^\n]*/g, (_, cadena) => cadena ?? "");
  const { triggers } = JSON.parse(limpio);
  assert.deepEqual(triggers.crons, CRONS);
  assert.deepEqual(CRONS, ["*/15 * * * *"]);
});

test("worker.js no nombra más crons que el del tic", () => {
  const codigo = readFileSync(new URL("./worker.js", import.meta.url), "utf8");
  const crons = codigo.match(/"[^"\n]*(?:\s+[\d*/,A-Z-]+){4}"/g) ?? [];
  assert.deepEqual(crons, [`"${TIC}"`]);
});

test("un lanzamiento que falla por algo pasajero se reintenta en el mismo tic", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const peticiones = github({
    exitosa: ahora,
    dispatch: (n) => (n < 2 ? new Response("caído", { status: 502 }) : new Response(null, { status: 204 })),
  });
  const { esperas, esperar } = sinEsperar();
  const resultado = await callado(t, () => tic({}, { ahora, esperar }));
  assert.deepEqual(resultado, { lanzado: true, hombreMuerto: true });
  assert.equal(lanzamientos(peticiones).length, 3);
  assert.deepEqual(esperas, ESPERA_REINTENTO_MS.slice(0, 2));
});

test("una falla de red también se reintenta", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const peticiones = github({
    exitosa: ahora,
    dispatch: (n) => { if (n === 0) throw new TypeError("fetch failed"); return new Response(null, { status: 204 }); },
  });
  const resultado = await callado(t, () => tic({}, { ahora, esperar: sinEsperar().esperar }));
  assert.equal(resultado.lanzado, true);
  assert.equal(lanzamientos(peticiones).length, 2);
});

test("lo que no va a pasar al reintentar no se reintenta", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const peticiones = github({ exitosa: ahora, dispatch: () => new Response("sin permiso", { status: 403 }) });
  const { esperas, esperar } = sinEsperar();
  const resultado = await callado(t, () => tic({}, { ahora, esperar }));
  assert.equal(resultado.lanzado, false);
  assert.equal(lanzamientos(peticiones).length, 1);
  assert.deepEqual(esperas, []);
});

test("el hombre muerto corre aunque el lanzamiento falle tras sus reintentos", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const peticiones = github({ exitosa: ahora - 5 * HORA, dispatch: () => new Response("caído", { status: 503 }) });
  const { esperas, esperar } = sinEsperar();
  const resultado = await callado(t, () => tic({}, { ahora, esperar }));
  assert.deepEqual(resultado, { lanzado: false, hombreMuerto: true });
  assert.equal(lanzamientos(peticiones).length, 1 + ESPERA_REINTENTO_MS.length);
  assert.deepEqual(esperas, ESPERA_REINTENTO_MS);
  assert.deepEqual(escrituras(peticiones).map((p) => [p.clave, p.cuerpo.title]),
    [[`POST ${API}/issues`, TITULO_HOMBRE_MUERTO]]);
});

test("el supervisor se lanza aunque el hombre muerto falle", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const peticiones = github({ lectura: () => new Response("sin permiso", { status: 403 }) });
  const resultado = await callado(t, () => tic({}, { ahora, esperar: sinEsperar().esperar }));
  assert.deepEqual(resultado, { lanzado: true, hombreMuerto: false });
  assert.equal(lanzamientos(peticiones).length, 1);
});

test("un tic no depende del anterior: tras uno fallido, el siguiente lanza igual", async (t) => {
  const env = { GITHUB_TOKEN: "x" };
  const { esperar } = sinEsperar();
  github({ dispatch: () => new Response("caído", { status: 500 }), lectura: () => new Response("caído", { status: 500 }) });
  const fallido = await callado(t, () => tic(env, { ahora: utc("2026-11-16T09:00"), esperar }));
  assert.deepEqual(fallido, { lanzado: false, hombreMuerto: false });
  assert.deepEqual(env, { GITHUB_TOKEN: "x" });

  const ahora = utc("2026-11-16T09:15");
  const peticiones = github({ exitosa: ahora - HORA });
  const siguiente = await tic(env, { ahora, esperar });
  assert.deepEqual(siguiente, { lanzado: true, hombreMuerto: true });
  assert.equal(lanzamientos(peticiones).length, 1);
});

test("el hombre muerto cierra su issue cuando el supervisor vuelve", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const issue = { number: 7, title: TITULO_HOMBRE_MUERTO, created_at: new Date(ahora - 4 * HORA).toISOString() };
  const peticiones = github({ exitosa: ahora - HORA / 4, issue });
  await callado(t, () => tic({}, { ahora, esperar: sinEsperar().esperar }));
  assert.deepEqual(escrituras(peticiones).map((p) => p.clave),
    [`POST ${API}/issues/7/comments`, `PATCH ${API}/issues/7`]);
  assert.deepEqual(escrituras(peticiones)[1].cuerpo, { state: "closed" });
});

test("el hombre muerto no repite el aviso antes de 6 horas", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const hace = (horas) => new Date(ahora - horas * HORA).toISOString();
  const reciente = github({ issue: { number: 7, title: TITULO_HOMBRE_MUERTO, created_at: hace(2) } });
  await callado(t, () => tic({}, { ahora, esperar: sinEsperar().esperar }));
  assert.deepEqual(escrituras(reciente), []);

  const viejo = github({ issue: { number: 7, title: TITULO_HOMBRE_MUERTO, created_at: hace(7) } });
  await tic({}, { ahora, esperar: sinEsperar().esperar });
  assert.deepEqual(escrituras(viejo).map((p) => p.clave), [`POST ${API}/issues/7/comments`]);
});

test("hombre muerto: la decisión", () => {
  const ahora = utc("2026-11-18T15:30");
  const hace = (horas) => ahora - horas * HORA;
  const decidir = (ultimaExitosa, issue) => decidirHombreMuerto({ ahora, ultimaExitosa, issue });
  // Corre bien.
  assert.equal(decidir(hace(0.25), null), "nada");
  assert.equal(decidir(hace(3), null), "nada");
  assert.equal(decidir(hace(1), { ultimoAviso: hace(2) }), "cerrar");
  // No corre.
  assert.equal(decidir(hace(3.25), null), "abrir");
  assert.equal(decidir(null, null), "abrir");
  assert.equal(decidir(null, { ultimoAviso: hace(0.25) }), "nada");
  assert.equal(decidir(hace(30), { ultimoAviso: hace(5.75) }), "nada");
  assert.equal(decidir(hace(30), { ultimoAviso: hace(6) }), "comentar");
  assert.equal(decidir(null, { ultimoAviso: hace(48) }), "comentar");
});

test("solo se reintenta lo que puede pasar al reintentar", () => {
  for (const status of [undefined, 408, 429, 500, 502, 503]) assert.equal(reintentable(status), true, `${status}`);
  for (const status of [401, 403, 404, 422]) assert.equal(reintentable(status), false, `${status}`);
});

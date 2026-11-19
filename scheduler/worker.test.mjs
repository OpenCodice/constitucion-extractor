import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { afterEach, test } from "node:test";

import worker, {
  CABECERA_VENCIMIENTO, CRONS, ESPERA_REINTENTO_MS, PREFIJO_VENCIMIENTO, REPARACION, SUPERVISOR, TIC,
  TITULO_HOMBRE_MUERTO, decidirHombreMuerto, decidirReparacion, decidirVencimiento, leerVencimiento, reintentable, tic,
  tituloVencimiento,
} from "./worker.js";

const utc = (texto) => Date.parse(`${texto}:00Z`);
const HORA = 3_600_000;
const API = "https://api.github.com/repos/OpenCodice/supervisor";
const DISPATCH = `POST ${API}/actions/workflows/supervisor.yml/dispatches`;
const REPARAR = `POST ${API}/actions/workflows/reparar-infra.yml/dispatches`;

const fetchReal = globalThis.fetch;
afterEach(() => { globalThis.fetch = fetchReal; });

const json = (cuerpo, status = 200) => new Response(JSON.stringify(cuerpo), { status });

// Un GitHub de mentira. `dispatch` contesta cada lanzamiento (recibe cuántos
// van); `exitosa` es la fecha de la última corrida exitosa del supervisor;
// `issue` (o `issues`), los que están abiertos; `comentarios`, los de
// cualquier issue; `vence`, la cabecera de vencimiento del token en cada
// respuesta aceptada; `terminadas`, las corridas terminadas del supervisor y
// `reparaciones`, las de reparar-infra.yml (de la más nueva a la más vieja);
// `reparar` contesta el lanzamiento de una reparación. Devuelve las peticiones.
function github({
  dispatch = () => new Response(null, { status: 204 }), exitosa = null, issue = null, issues, comentarios = [],
  lectura, vence, terminadas = [], reparaciones = [], reparar = () => new Response(null, { status: 204 }),
} = {}) {
  const peticiones = [];
  let lanzamientos = 0;
  const responder = (peticion, metodo) => {
    if (peticion.clave === DISPATCH) return dispatch(lanzamientos++);
    if (peticion.clave === REPARAR) return reparar();
    if (metodo !== "GET") return json({});
    if (lectura) return lectura(peticion);
    if (peticion.clave.endsWith("/reparar-infra.yml/runs")) return json({ workflow_runs: reparaciones });
    if (peticion.clave.endsWith("/runs") && peticion.consulta.includes("status=completed")) {
      return json({ workflow_runs: terminadas });
    }
    if (peticion.clave.endsWith("/runs")) {
      return json({ workflow_runs: exitosa == null ? [] : [{ created_at: new Date(exitosa).toISOString() }] });
    }
    if (peticion.clave.endsWith("/issues")) return json(issues ?? (issue ? [issue] : []));
    return json(peticion.clave.endsWith("/comments") ? comentarios : []);
  };
  globalThis.fetch = async (url, opciones = {}) => {
    const metodo = opciones.method ?? "GET";
    const [ruta, consulta = ""] = String(url).split("?");
    const peticion = { clave: `${metodo} ${ruta}`, consulta, cuerpo: opciones.body ? JSON.parse(opciones.body) : null };
    peticiones.push(peticion);
    const respuesta = await responder(peticion, metodo);
    if (vence !== undefined && respuesta.ok) respuesta.headers.set(CABECERA_VENCIMIENTO, vence);
    return respuesta;
  };
  return peticiones;
}

const lanzamientos = (peticiones) => peticiones.filter((p) => p.clave === DISPATCH);
const reparaciones = (peticiones) => peticiones.filter((p) => p.clave === REPARAR);
const escrituras = (peticiones) => peticiones.filter((p) => !p.clave.startsWith("GET ") && ![DISPATCH, REPARAR].includes(p.clave));
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
    assert.deepEqual(reparaciones(peticiones), []);
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
  assert.deepEqual(resultado, { lanzado: true, hombreMuerto: true, reparacion: true, vencimiento: true });
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
  assert.deepEqual(resultado, { lanzado: false, hombreMuerto: true, reparacion: true, vencimiento: true });
  assert.equal(lanzamientos(peticiones).length, 1 + ESPERA_REINTENTO_MS.length);
  assert.deepEqual(esperas, ESPERA_REINTENTO_MS);
  assert.deepEqual(escrituras(peticiones).map((p) => [p.clave, p.cuerpo.title]),
    [[`POST ${API}/issues`, TITULO_HOMBRE_MUERTO]]);
});

test("el supervisor se lanza aunque el hombre muerto falle", async (t) => {
  const ahora = utc("2026-11-16T09:00");
  const peticiones = github({ lectura: () => new Response("sin permiso", { status: 403 }) });
  const resultado = await callado(t, () => tic({}, { ahora, esperar: sinEsperar().esperar }));
  assert.deepEqual(resultado, { lanzado: true, hombreMuerto: false, reparacion: false, vencimiento: false });
  assert.equal(lanzamientos(peticiones).length, 1);
});

test("un tic no depende del anterior: tras uno fallido, el siguiente lanza igual", async (t) => {
  const env = { GITHUB_TOKEN: "x" };
  const { esperar } = sinEsperar();
  github({ dispatch: () => new Response("caído", { status: 500 }), lectura: () => new Response("caído", { status: 500 }) });
  const fallido = await callado(t, () => tic(env, { ahora: utc("2026-11-16T09:00"), esperar }));
  assert.deepEqual(fallido, { lanzado: false, hombreMuerto: false, reparacion: false, vencimiento: true });
  assert.deepEqual(env, { GITHUB_TOKEN: "x" });

  const ahora = utc("2026-11-16T09:15");
  const peticiones = github({ exitosa: ahora - HORA });
  const siguiente = await tic(env, { ahora, esperar });
  assert.deepEqual(siguiente, { lanzado: true, hombreMuerto: true, reparacion: true, vencimiento: true });
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

// ---- El vencimiento del token del Worker ----

const DIA = 24 * HORA;

test("vencimiento: los formatos de la cabecera", () => {
  const esperado = Date.parse("2027-11-20T06:00:00Z");
  for (const cabecera of [
    "2027-11-20 06:00:00 UTC", "2027-11-20 00:00:00 -0600", "2027-11-20 08:00:00 +0200", "2027-11-20 11:30:00 +05:30",
    "2027-11-20T06:00:00Z", "2027-11-20 06:00:00", " 2027-11-20 06:00:00 UTC ",
  ]) assert.equal(leerVencimiento(cabecera), esperado, cabecera);
  // Sin cabecera el token no vence; una que no se entiende no es lo mismo.
  for (const ausente of [null, undefined, "", "  "]) assert.equal(leerVencimiento(ausente), null);
  for (const rara of ["pronto", "2027-11-20", "20/11/2027 06:00:00 UTC", "2027-13-40 06:00:00 UTC"]) {
    assert.ok(Number.isNaN(leerVencimiento(rara)), rara);
  }
  assert.equal(tituloVencimiento(esperado), "🔑 El token del scheduler vence el 2027-11-20");
  assert.ok(tituloVencimiento(esperado).startsWith(PREFIJO_VENCIMIENTO));
});

test("vencimiento: la decisión", () => {
  const ahora = utc("2026-11-18T15:30");
  const en = (dias) => ahora + dias * DIA;
  const decidir = (vence, issue) => decidirVencimiento({ ahora, vence, issue });
  const aviso = (vence, haceDias) => ({ titulo: tituloVencimiento(vence), ultimoAviso: ahora - haceDias * DIA });
  // No vence, o vence lejos.
  assert.equal(decidir(null, null), "nada");
  assert.equal(decidir(en(365), null), "nada");
  assert.equal(decidir(en(30), null), "nada");
  // Dentro del umbral: se abre una vez y se recuerda cada 7 días.
  assert.equal(decidir(en(29.9), null), "abrir");
  assert.equal(decidir(en(1), null), "abrir");
  assert.equal(decidir(en(20), aviso(en(20), 0.01)), "nada");
  assert.equal(decidir(en(20), aviso(en(20), 6.9)), "nada");
  assert.equal(decidir(en(20), aviso(en(20), 7)), "comentar");
  // Renovado: la fecha cambió. Lejos (o sin fecha) se cierra; cerca, se cierra y se abre el de la fecha nueva.
  assert.equal(decidir(en(365), aviso(en(20), 1)), "cerrar");
  assert.equal(decidir(null, aviso(en(20), 1)), "cerrar");
  assert.equal(decidir(en(25), aviso(en(20), 1)), "reabrir");
});

test("el tic avisa del vencimiento con lo que ya recibió, sin peticiones de más", async (t) => {
  const ahora = utc("2026-11-18T15:30");
  const lejos = github({ exitosa: ahora, vence: "2027-11-20 06:00:00 UTC" });
  assert.deepEqual(await callado(t, () => tic({}, { ahora })), { lanzado: true, hombreMuerto: true, reparacion: true, vencimiento: true });
  const sinFecha = github({ exitosa: ahora });
  await tic({}, { ahora });
  assert.deepEqual(lejos.map((p) => p.clave), sinFecha.map((p) => p.clave));
  assert.deepEqual(escrituras(lejos), []);
  assert.equal(lejos.filter((p) => p.clave === `GET ${API}/issues`).length, 1);

  const cerca = github({ exitosa: ahora, vence: "2026-12-08 00:00:00 -0600" });
  await tic({}, { ahora });
  const [abierto] = escrituras(cerca);
  assert.equal(escrituras(cerca).length, 1);
  assert.equal(abierto.clave, `POST ${API}/issues`);
  assert.equal(abierto.cuerpo.title, "🔑 El token del scheduler vence el 2026-12-08");
  for (const texto of ["2026-12-08 06:00 UTC", "faltan 19 días", "Actions: read and write e Issues: read and write",
    "npx wrangler secret put GITHUB_TOKEN", "constitucion-extractor/scheduler/"]) {
    assert.ok(abierto.cuerpo.body.includes(texto), texto);
  }
});

test("el aviso de vencimiento se repite cada 7 días y se cierra al renovar el token", async (t) => {
  const ahora = utc("2026-11-18T15:30");
  const hace = (dias) => new Date(ahora - dias * DIA).toISOString();
  const vence = "2026-12-08 06:00:00 UTC";
  const issue = (dias) => ({ number: 9, title: "🔑 El token del scheduler vence el 2026-12-08", created_at: hace(dias) });
  const tocar = async (mundo) => { await callado(t, () => tic({}, { ahora })); return escrituras(mundo).map((p) => p.clave); };

  assert.deepEqual(await tocar(github({ exitosa: ahora, vence, issue: issue(3) })), []);
  assert.deepEqual(await tocar(github({ exitosa: ahora, vence, issue: issue(8) })), [`POST ${API}/issues/9/comments`]);
  // Ya se recordó hace dos días: se lee del último comentario del issue.
  assert.deepEqual(await tocar(github({ exitosa: ahora, vence, issue: issue(8), comentarios: [{ created_at: hace(2) }] })), []);

  const cerrar = [`POST ${API}/issues/9/comments`, `PATCH ${API}/issues/9`];
  assert.deepEqual(await tocar(github({ exitosa: ahora, vence: "2027-11-20 06:00:00 UTC", issue: issue(8) })), cerrar);
  assert.deepEqual(await tocar(github({ exitosa: ahora, issue: issue(8) })), cerrar);
  // Renovado por poco tiempo: se cierra el de la fecha vieja y se abre el de la nueva.
  const corto = github({ exitosa: ahora, vence: "2026-12-15 06:00:00 UTC", issue: issue(1) });
  assert.deepEqual(await tocar(corto), [...cerrar, `POST ${API}/issues`]);
  assert.equal(escrituras(corto)[2].cuerpo.title, "🔑 El token del scheduler vence el 2026-12-15");
  // El issue del hombre muerto no es el del vencimiento, ni al revés.
  const ambos = github({ exitosa: ahora, vence, issues: [{ number: 7, title: TITULO_HOMBRE_MUERTO, created_at: hace(1) }, issue(1)] });
  assert.deepEqual(await tocar(ambos), [`POST ${API}/issues/7/comments`, `PATCH ${API}/issues/7`]);
});

test("una falla del aviso de vencimiento no alcanza al tic ni al hombre muerto", async (t) => {
  const ahora = utc("2026-11-18T15:30");
  // Una cabecera que no se entiende: ni se abre ni se cierra nada por ella.
  const rara = github({ exitosa: ahora - 5 * HORA, vence: "pronto", issue: { number: 9, title: `${PREFIJO_VENCIMIENTO}2026-12-08`, created_at: new Date(ahora).toISOString() } });
  assert.deepEqual(await callado(t, () => tic({}, { ahora })), { lanzado: true, hombreMuerto: true, reparacion: true, vencimiento: false });
  assert.deepEqual(escrituras(rara).map((p) => [p.clave, p.cuerpo.title]), [[`POST ${API}/issues`, TITULO_HOMBRE_MUERTO]]);

  // Sin permiso para escribir issues: el lanzamiento sale igual.
  const peticiones = github({ exitosa: ahora, vence: "2026-12-08 06:00:00 UTC" });
  const fetchFalso = globalThis.fetch;
  globalThis.fetch = (url, opciones = {}) => (opciones.method === "POST" && String(url).endsWith("/issues")
    ? Promise.resolve(new Response("sin permiso", { status: 403 })) : fetchFalso(url, opciones));
  assert.deepEqual(await tic({}, { ahora }), { lanzado: true, hombreMuerto: true, reparacion: true, vencimiento: false });
  assert.equal(lanzamientos(peticiones).length, 1);

  // Si el hombre muerto no pudo leer los issues, el aviso los pide por su cuenta.
  let lecturas = 0;
  const solo = github({ vence: "2026-12-08 06:00:00 UTC", lectura: (p) => (p.clave.endsWith("/runs") ? new Response("caído", { status: 500 }) : (lecturas++, json([]))) });
  assert.deepEqual(await tic({}, { ahora }), { lanzado: true, hombreMuerto: false, reparacion: false, vencimiento: true });
  assert.equal(lecturas, 1);
  assert.deepEqual(escrituras(solo).map((p) => p.cuerpo.title), ["🔑 El token del scheduler vence el 2026-12-08"]);

  // Con el token ya rechazado en todo no hay nada que leer ni dónde avisar.
  github({ dispatch: () => new Response("Bad credentials", { status: 401 }), lectura: () => new Response("Bad credentials", { status: 401 }) });
  assert.deepEqual(await tic({}, { ahora }), { lanzado: false, hombreMuerto: false, reparacion: false, vencimiento: true });
});

// ---- La reparación del supervisor ----

const AHORA = utc("2026-11-18T15:30");
const hace = (horas) => new Date(AHORA - horas * HORA).toISOString();
// Corridas terminadas del supervisor, una cada 15 minutos, de la más nueva
// (id 900) a la más vieja.
const corridas = (...conclusiones) => conclusiones.map((conclusion, i) => ({
  id: 900 - i, status: "completed", conclusion, created_at: hace(0.25 * (i + 1)), run_started_at: hace(0.25 * (i + 1)),
}));
const reparacion = ({ huella = "supervisor", status = "completed", creada, terminada = creada, origen = "scheduler" }) => ({
  status,
  created_at: hace(creada),
  updated_at: hace(terminada),
  display_title: `reparar-infra huella=[${huella}] ensayo=[false] base=[] revertir=[] repo=[supervisor] workflow=[supervisor.yml] job=[] paso=[] corrida=[1] origen=[${origen}]`,
});
const INPUTS_REPARACION = { huella: "supervisor", repo: "supervisor", workflow: "supervisor.yml", corrida: "900", origen: "scheduler" };

test("tres fallas seguidas del supervisor: se pide su reparación sobre la última", async (t) => {
  const peticiones = github({ exitosa: AHORA - HORA, terminadas: corridas("failure", "failure", "failure", "success") });
  const resultado = await callado(t, () => tic({}, { ahora: AHORA }));
  assert.deepEqual(resultado, { lanzado: true, hombreMuerto: true, reparacion: true, vencimiento: true });
  assert.deepEqual(reparaciones(peticiones).map((p) => p.cuerpo), [{ ref: "main", inputs: INPUTS_REPARACION }]);
  assert.deepEqual(REPARACION, { repo: "supervisor", workflow: "reparar-infra.yml", huella: "supervisor" });
  // El tic sigue lanzando al supervisor, y todo va al repo del supervisor.
  assert.equal(lanzamientos(peticiones).length, 1);
  for (const p of peticiones) assert.ok(p.clave.includes(`${API}/`), p.clave);
});

test("las canceladas y las saltadas no cuentan, ni como falla ni como éxito", async (t) => {
  const peticiones = github({
    terminadas: corridas("cancelled", "failure", "skipped", "failure", "cancelled", "failure", "success"),
  });
  await callado(t, () => tic({}, { ahora: AHORA }));
  assert.deepEqual(reparaciones(peticiones).map((p) => p.cuerpo.inputs.corrida), ["899"]);
});

test("dos fallas y un éxito: no se pide nada, ni se leen las reparaciones", async (t) => {
  for (const conclusiones of [["failure", "failure", "success"], ["success", "failure", "failure", "failure"],
    ["failure", "success", "failure", "failure"], ["failure", "failure"], ["cancelled", "cancelled", "cancelled"], []]) {
    const peticiones = github({ exitosa: AHORA, terminadas: corridas(...conclusiones) });
    const resultado = await callado(t, () => tic({}, { ahora: AHORA }));
    assert.equal(resultado.reparacion, true);
    assert.deepEqual(reparaciones(peticiones), [], conclusiones.join());
    assert.equal(peticiones.filter((p) => p.clave.includes("reparar-infra.yml")).length, 0);
  }
});

test("con una reparación del supervisor en curso o en cola no se pide otra", async (t) => {
  const rotas = corridas("failure", "failure", "failure");
  for (const status of ["in_progress", "queued", "pending", "waiting", "requested"]) {
    const peticiones = github({ terminadas: rotas, reparaciones: [reparacion({ status, creada: 0.5, origen: "supervisor" })] });
    await callado(t, () => tic({}, { ahora: AHORA }));
    assert.deepEqual(reparaciones(peticiones), [], status);
  }
  // La de otra huella no estorba.
  const ajena = github({ terminadas: rotas, reparaciones: [reparacion({ huella: "abc123", status: "in_progress", creada: 0.5 })] });
  await tic({}, { ahora: AHORA });
  assert.equal(reparaciones(ajena).length, 1);
});

test("tope: dos reparaciones del supervisor en 24 horas", async (t) => {
  const rotas = corridas("failure", "failure", "failure");
  const pedidas = async (lista) => {
    const peticiones = github({ terminadas: rotas, reparaciones: lista });
    await callado(t, () => tic({}, { ahora: AHORA }));
    return reparaciones(peticiones).length;
  };
  assert.equal(await pedidas([reparacion({ creada: 5 }), reparacion({ creada: 23.9 })]), 0);
  assert.equal(await pedidas([reparacion({ creada: 5 }), reparacion({ creada: 24.1 })]), 1);
  assert.equal(await pedidas([reparacion({ creada: 5 }), reparacion({ huella: "abc123", creada: 6 }), reparacion({ huella: "supervisor-x", creada: 7 })]), 1);
  assert.equal(await pedidas([reparacion({ creada: 30 }), reparacion({ creada: 40 }), reparacion({ creada: 50 })]), 1);
});

test("tras una reparación se espera a una corrida del supervisor que empiece después", async () => {
  const decidir = (terminada) => decidirReparacion({
    ahora: AHORA,
    terminadas: corridas("failure", "failure", "failure"),
    reparaciones: async () => [reparacion({ creada: 2, terminada })],
  });
  // La última falla empezó hace 15 minutos.
  assert.equal(await decidir(0.1), null);
  assert.equal(await decidir(0.25), null);
  assert.equal(await decidir(0.5), 900);
});

test("agotar el tiempo o no arrancar también es fallar", async () => {
  const decidir = (...conclusiones) => decidirReparacion({
    ahora: AHORA, terminadas: corridas(...conclusiones), reparaciones: async () => [],
  });
  assert.equal(await decidir("timed_out", "failure", "startup_failure"), 900);
  assert.equal(await decidir("failure", "neutral", "failure", "failure"), null);
});

test("una falla al pedir la reparación no alcanza al tic ni al hombre muerto", async (t) => {
  const rotas = corridas("failure", "failure", "failure");
  const completo = { lanzado: true, hombreMuerto: true, reparacion: false, vencimiento: true };
  const titulos = (peticiones) => escrituras(peticiones).map((p) => [p.clave, p.cuerpo.title]);
  const aviso = [[`POST ${API}/issues`, TITULO_HOMBRE_MUERTO]];

  // GitHub rechaza el lanzamiento: no se reintenta en este tic.
  const rechazado = github({ exitosa: AHORA - 5 * HORA, terminadas: rotas, reparar: () => new Response("caído", { status: 502 }) });
  assert.deepEqual(await callado(t, () => tic({}, { ahora: AHORA })), completo);
  assert.equal(reparaciones(rechazado).length, 1);
  assert.equal(lanzamientos(rechazado).length, 1);
  assert.deepEqual(titulos(rechazado), aviso);

  // No se pueden leer las corridas de reparar-infra: sin saber los topes, no se lanza.
  const lecturas = github({ exitosa: AHORA - 5 * HORA, terminadas: rotas });
  const fetchFalso = globalThis.fetch;
  globalThis.fetch = (url, opciones = {}) => (String(url).includes("/reparar-infra.yml/runs")
    ? Promise.resolve(new Response("caído", { status: 500 })) : fetchFalso(url, opciones));
  assert.deepEqual(await tic({}, { ahora: AHORA }), completo);
  assert.deepEqual(reparaciones(lecturas), []);
  assert.equal(lanzamientos(lecturas).length, 1);
  assert.deepEqual(titulos(lecturas), aviso);

  // Una falla de red al leer las corridas del supervisor.
  const red = github({ exitosa: AHORA - 5 * HORA });
  const otroFalso = globalThis.fetch;
  globalThis.fetch = (url, opciones = {}) => (String(url).includes("status=completed")
    ? Promise.reject(new TypeError("fetch failed")) : otroFalso(url, opciones));
  assert.deepEqual(await tic({}, { ahora: AHORA }), completo);
  assert.equal(lanzamientos(red).length, 1);
  assert.deepEqual(titulos(red), aviso);
});

test("un tic sano gasta una sola petición más en vigilar las fallas del supervisor", async (t) => {
  const peticiones = github({ exitosa: AHORA, terminadas: corridas("success", "failure", "failure") });
  await callado(t, () => tic({}, { ahora: AHORA }));
  assert.deepEqual(peticiones.map((p) => p.clave).sort(), [
    DISPATCH, `GET ${API}/actions/workflows/supervisor.yml/runs`, `GET ${API}/actions/workflows/supervisor.yml/runs`,
    `GET ${API}/issues`,
  ].sort());
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  CRONS, DIARIO, RONDAS, TIC, VIGILANCIAS,
  decidirHombreMuerto, motivoRelanzar, queToca, reintentable,
} from "./worker.js";

const utc = (texto) => Date.parse(`${texto}:00Z`);
const HORA = 3_600_000;
const nombres = (toca) => toca.lanzamientos.map((l) => `${l.repo}/${l.workflow}`);

const SUPERVISOR = "supervisor/supervisor.yml";
const CONGRESO = "congreso-extractor/actualizar-congreso.yml";

// 2026-11-15 es domingo; 16, lunes; 18, miércoles.
const TABLA = [
  ["lunes 09:00, cron de las 09:00", "0 9 * * MON", "2026-11-16T09:00",
    ["fiscal-extractor/vigilar-fiscal.yml", "constitucion-extractor/vigilar-cpeum.yml",
      "constitucion-extractor/vigilar-estatales.yml"]],
  ["lunes 13:00, cron de las 13:00", "0 13 * * MON", "2026-11-16T13:00",
    ["fiscal-extractor/vigilar-federal.yml", "fiscal-extractor/vigilar-leyes-estatales.yml"]],
  ["lunes 09:00, tic", TIC, "2026-11-16T09:00", [SUPERVISOR, CONGRESO]],
  ["lunes 13:00, tic", TIC, "2026-11-16T13:00", [SUPERVISOR, CONGRESO]],
  ["minuto 15", TIC, "2026-11-16T09:15", [SUPERVISOR]],
  ["minuto 30", TIC, "2026-11-16T09:30", [SUPERVISOR]],
  ["minuto 45", TIC, "2026-11-16T09:45", [SUPERVISOR]],
  ["miércoles 15:30, cron diario", DIARIO, "2026-11-18T15:30", ["fiscal-extractor/expandir-estatales.yml"]],
  ["miércoles 15:30, tic", TIC, "2026-11-18T15:30", [SUPERVISOR]],
  ["lunes 15:30, cron diario", DIARIO, "2026-11-16T15:30", []],
  ["domingo 15:30, cron diario", DIARIO, "2026-11-15T15:30", []],
  ["domingo 00:00, tic", TIC, "2026-11-15T00:00", [SUPERVISOR, CONGRESO]],
  ["domingo 09:15, tic", TIC, "2026-11-15T09:15", [SUPERVISOR]],
  ["hora 18, tic", TIC, "2026-11-17T18:00", [SUPERVISOR, CONGRESO]],
  ["un cron que no se declara", "0 0 1 1 *", "2026-11-16T09:00", []],
];

for (const [caso, cron, fecha, esperado] of TABLA) {
  test(`qué se lanza: ${caso}`, () => {
    assert.deepEqual(nombres(queToca(cron, utc(fecha))), esperado);
  });
}

test("todo lo que se lanza lleva origen=scheduler", () => {
  for (const [, cron, fecha] of TABLA) {
    for (const l of queToca(cron, utc(fecha)).lanzamientos) assert.equal(l.inputs.origen, "scheduler");
  }
});

test("el congreso solo publica a las 18:00", () => {
  const publicar = (fecha) => queToca(TIC, utc(fecha)).lanzamientos
    .find((l) => l.workflow === "actualizar-congreso.yml").inputs;
  assert.deepEqual(publicar("2026-11-17T18:00"), { publicar: "si", origen: "scheduler" });
  assert.deepEqual(publicar("2026-11-17T17:00"), { publicar: "no", origen: "scheduler" });
  assert.deepEqual(publicar("2026-11-17T19:00"), { publicar: "no", origen: "scheduler" });
});

test("las vigilancias no llevan más inputs que el origen", () => {
  for (const cron of ["0 9 * * MON", "0 13 * * MON"]) {
    for (const l of queToca(cron, utc("2026-11-16T09:00")).lanzamientos) {
      assert.deepEqual(l.inputs, { origen: "scheduler" });
    }
  }
});

test("solo el supervisor es opcional", () => {
  const toca = queToca(TIC, utc("2026-11-16T09:00")).lanzamientos;
  assert.deepEqual(toca.map((l) => Boolean(l.opcional)), [true, false]);
});

test("el vigilante va con el cron diario y el hombre muerto con el tic", () => {
  const forma = ({ vigilante, hombreMuerto }) => ({ vigilante, hombreMuerto });
  assert.deepEqual(forma(queToca(DIARIO, utc("2026-11-15T15:30"))), { vigilante: true, hombreMuerto: false });
  assert.deepEqual(forma(queToca(TIC, utc("2026-11-15T15:30"))), { vigilante: false, hombreMuerto: true });
  assert.deepEqual(forma(queToca("0 9 * * MON", utc("2026-11-16T09:00"))), { vigilante: false, hombreMuerto: false });
});

test("cada vigilancia y cada ronda tiene un cron que la lanza", () => {
  const lanzadas = new Set(CRONS.flatMap((cron) => {
    // Una semana entera, cada 15 minutos.
    const inicio = utc("2026-11-15T00:00");
    return Array.from({ length: 7 * 96 }, (_, i) => nombres(queToca(cron, inicio + i * HORA / 4))).flat();
  }));
  for (const v of [...VIGILANCIAS, ...RONDAS]) assert.ok(lanzadas.has(`${v.repo}/${v.workflow}`), v.workflow);
});

test("los crons de wrangler.jsonc son los de worker.js", () => {
  const texto = readFileSync(new URL("./wrangler.jsonc", import.meta.url), "utf8");
  // Quita los comentarios de línea sin tocar las cadenas.
  const json = texto.replace(/("(?:[^"\\]|\\.)*")|\/\/[^\n]*/g, (_, cadena) => cadena ?? "");
  const { triggers } = JSON.parse(json);
  assert.deepEqual([...triggers.crons].sort(), [...CRONS].sort());
  assert.equal(new Set(triggers.crons).size, triggers.crons.length);
  // Cloudflare Free admite 5 Cron Triggers por cuenta y otro Worker usa uno.
  assert.ok(triggers.crons.length <= 4);
});

test("vigilante: relanza lo que lleva más de 8 días sin correr", () => {
  const ahora = utc("2026-11-18T15:30");
  const corrida = (horas, status = "completed") =>
    ({ status, created_at: new Date(ahora - horas * HORA).toISOString() });
  assert.equal(motivoRelanzar(undefined, ahora), "sin ninguna corrida");
  assert.equal(motivoRelanzar(corrida(2 * 24), ahora), null);
  assert.equal(motivoRelanzar(corrida(8 * 24 - 1), ahora), null);
  assert.equal(motivoRelanzar(corrida(9 * 24), ahora), "sin correr hace 9.0 días");
});

test("vigilante: una corrida colgada no cuenta como en curso", () => {
  const ahora = utc("2026-11-18T15:30");
  const corrida = (horas, status) => ({ status, created_at: new Date(ahora - horas * HORA).toISOString() });
  assert.equal(motivoRelanzar(corrida(5, "in_progress"), ahora), null);
  assert.equal(motivoRelanzar(corrida(11, "queued"), ahora), null);
  // Colgada pero reciente: aún no pasan los 8 días.
  assert.equal(motivoRelanzar(corrida(13, "in_progress"), ahora), null);
  assert.equal(motivoRelanzar(corrida(9 * 24, "in_progress"), ahora), "sin correr hace 9.0 días");
  assert.equal(motivoRelanzar(corrida(9 * 24, "queued"), ahora), "sin correr hace 9.0 días");
});

test("hombre muerto", () => {
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

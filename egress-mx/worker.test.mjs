import assert from "node:assert/strict";
import { timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { afterEach, test } from "node:test";

// Node no trae la comparación en tiempo constante del runtime de Workers.
crypto.subtle.timingSafeEqual ??= (a, b) => timingSafeEqual(a, b);

const BASE = "https://egress-mx.example.workers.dev";
const LISTA = "https://raw.githubusercontent.com/OpenCodice/constitucion-extractor/main/egress-mx/permitidos.json";
const TRAZA = "https://www.cloudflare.com/cdn-cgi/trace";
const ENV = { TOKEN: "secreto-de-la-vigilancia", TOKEN_ARCHIVO: "secreto-del-archivo" };
const INTEGRADOS = 12;

const fetchReal = globalThis.fetch;
afterEach(() => { globalThis.fetch = fetchReal; });

// Cada prueba carga su propia copia del Worker: la lista de dominios se guarda
// en el módulo y no debe pasar de una prueba a otra.
let copias = 0;
const cargar = async () => (await import(`./worker.js?copia=${copias++}`)).default;

const traza = (colo, loc) => `fl=1f1\nh=www.cloudflare.com\nip=2a06:98c0:3600::103\ncolo=${colo}\nhttp=http/1.1\nloc=${loc}\n`;

// Internet de mentira. `lista` es lo que contesta permitidos.json (una
// función, o los dominios); `traza`, la traza de Cloudflare; `fuente`, lo que
// contesta cualquier otro sitio (sin redirección, salvo que la respuesta
// traiga su propia `url`). Devuelve las peticiones salientes.
function red({ lista = [], traza: trazado = () => new Response(traza("MEX", "MX")), fuente = () => new Response("hola") } = {}) {
  const salientes = [];
  globalThis.fetch = async (url, opciones = {}) => {
    const peticion = { url: String(url), ...opciones };
    salientes.push(peticion);
    if (peticion.url === LISTA) return typeof lista === "function" ? lista() : Response.json({ dominios: lista });
    if (peticion.url === TRAZA) return trazado();
    const respuesta = await fuente(peticion);
    if (!respuesta.url) Object.defineProperty(respuesta, "url", { value: peticion.url });
    return respuesta;
  };
  return salientes;
}

const pedir = (worker, ruta, { token = ENV.TOKEN, cf, ...opciones } = {}) => {
  const request = new Request(`${BASE}${ruta}`, {
    ...opciones,
    headers: { ...(token == null ? {} : { Authorization: `Bearer ${token}` }), ...opciones.headers },
  });
  if (cf) Object.defineProperty(request, "cf", { value: cf });
  return worker.fetch(request, ENV);
};
const descargar = (worker, url, opciones) => pedir(worker, `/?url=${encodeURIComponent(url)}`, opciones);
const aFuentes = (salientes) => salientes.filter((p) => p.url !== LISTA && p.url !== TRAZA);
const callado = (t) => t.mock.method(console, "error", () => {});

test("sin token, o con uno que no es, no se atiende nada", async () => {
  const worker = await cargar();
  const salientes = red();
  for (const ruta of ["/?url=https%3A%2F%2Fwww.senado.gob.mx%2F", "/salud", "/"]) {
    for (const token of [null, "", "otro", `${ENV.TOKEN}x`, ENV.TOKEN.slice(0, -1), "undefined"]) {
      const r = await pedir(worker, ruta, { token });
      assert.equal(r.status, 401, `${ruta} con ${token}`);
      assert.equal(await r.text(), "no autorizado\n");
    }
  }
  assert.deepEqual(salientes, []);
});

test("un Worker sin secrets no acepta ningún token", async () => {
  const worker = await cargar();
  red();
  for (const token of [null, "", "undefined"]) {
    const request = new Request(`${BASE}/salud`, { headers: token == null ? {} : { Authorization: `Bearer ${token}` } });
    assert.equal((await worker.fetch(request, {})).status, 401);
  }
});

test("los dos tokens valen, con Bearer en cualquier caja", async () => {
  const worker = await cargar();
  red();
  assert.equal((await descargar(worker, "https://www.senado.gob.mx/")).status, 200);
  assert.equal((await descargar(worker, "https://www.senado.gob.mx/", { token: ENV.TOKEN_ARCHIVO })).status, 200);
  const r = await descargar(worker, "https://www.senado.gob.mx/", { token: null, headers: { Authorization: `bearer ${ENV.TOKEN}` } });
  assert.equal(r.status, 200);
});

test("un dominio fuera de la lista se rechaza sin pedirle nada", async () => {
  const worker = await cargar();
  const salientes = red({ lista: ["congreso.ejemplo.gob.mx"] });
  for (const url of ["https://example.com/", "https://senado.gob.mx.example.com/", "https://otro.gob.mx/x.pdf",
    "ftp://www.senado.gob.mx/", "file:///etc/passwd"]) {
    const r = await descargar(worker, url);
    assert.equal(r.status, 403, url);
    assert.match(await r.text(), /^dominio no permitido/);
  }
  assert.equal((await pedir(worker, "/")).status, 400);
  assert.equal((await descargar(worker, "no es una url")).status, 400);
  assert.deepEqual(aFuentes(salientes), []);
});

test("un dominio permitido pasa, con el contenido y el código de la fuente", async () => {
  const worker = await cargar();
  const salientes = red({
    fuente: () => new Response("%PDF-1.7", {
      status: 200, headers: { "content-type": "application/pdf", etag: '"abc"', "set-cookie": "sesion=1" },
    }),
  });
  const r = await descargar(worker, "https://www.senado.gob.mx/ley.pdf");
  assert.equal(r.status, 200);
  assert.equal(await r.text(), "%PDF-1.7");
  assert.equal(r.headers.get("content-type"), "application/pdf");
  assert.equal(r.headers.get("etag"), '"abc"');
  assert.equal(r.headers.get("set-cookie"), null);
  const [peticion] = aFuentes(salientes);
  assert.equal(peticion.url, "https://www.senado.gob.mx/ley.pdf");
  assert.equal(peticion.method, "GET");
  // El token de quien llama no viaja a la fuente.
  assert.equal(JSON.stringify(peticion.headers).includes(ENV.TOKEN), false);

  red({ fuente: () => new Response("no está", { status: 404 }) });
  assert.equal((await descargar(worker, "https://www.senado.gob.mx/nada")).status, 404);
});

test("un POST de formulario se reenvía; otros métodos no", async () => {
  const worker = await cargar();
  const salientes = red();
  const r = await descargar(worker, "https://gaceta.diputados.gob.mx/voto", {
    method: "POST", body: "a=1&b=2", headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  assert.equal(r.status, 200);
  const [peticion] = aFuentes(salientes);
  assert.equal(peticion.method, "POST");
  assert.equal(new TextDecoder().decode(peticion.body), "a=1&b=2");
  assert.equal((await descargar(worker, "https://www.senado.gob.mx/", { method: "DELETE" })).status, 405);
  assert.equal(aFuentes(salientes).length, 1);
});

test("los dominios de permitidos.json se suman, solo si son .mx", async () => {
  const worker = await cargar();
  red({ lista: ["congreso.ejemplo.gob.mx", "example.com", "malo.mx/ruta", 7, "MAYUSCULAS.MX"] });
  assert.equal((await descargar(worker, "https://congreso.ejemplo.gob.mx/")).status, 200);
  assert.equal((await descargar(worker, "https://example.com/")).status, 403);
  assert.equal((await descargar(worker, "https://www.senado.gob.mx/")).status, 200);
});

test("sin permitidos.json siguen los dominios integrados", async () => {
  for (const lista of [() => new Response("caído", { status: 500 }), () => { throw new TypeError("fetch failed"); },
    () => new Response("<html>")]) {
    const worker = await cargar();
    red({ lista });
    assert.equal((await descargar(worker, "https://www.senado.gob.mx/")).status, 200);
    assert.equal((await descargar(worker, "https://congreso.ejemplo.gob.mx/")).status, 403);
  }
});

test("una redirección fuera de la lista no se entrega", async (t) => {
  const worker = await cargar();
  red({
    fuente: () => {
      const r = new Response("otra cosa");
      Object.defineProperty(r, "url", { value: "https://example.com/otra" });
      return r;
    },
  });
  callado(t);
  const r = await descargar(worker, "https://www.senado.gob.mx/");
  assert.equal(r.status, 502);
  assert.equal(await r.text(), "redirección a un dominio no permitido: example.com\n");
});

test("si la fuente no responde, 502 con la causa y sin el detalle de la excepción", async (t) => {
  const worker = await cargar();
  const errores = callado(t);
  red({ fuente: () => { throw new DOMException("The operation timed out.", "TimeoutError"); } });
  const lenta = await descargar(worker, "https://www.senado.gob.mx/");
  assert.equal(lenta.status, 502);
  assert.equal(await lenta.text(), "la fuente www.senado.gob.mx no respondió en 60 s\n");

  red({ fuente: () => { throw new TypeError("connect ECONNREFUSED 10.0.0.1:443"); } });
  const cerrada = await descargar(worker, "https://www.senado.gob.mx/");
  assert.equal(cerrada.status, 502);
  assert.equal(await cerrada.text(), "la fuente www.senado.gob.mx no aceptó la conexión\n");
  assert.equal(errores.mock.callCount(), 2);
  assert.match(errores.mock.calls[1].arguments[0], /ECONNREFUSED/);
});

test("/salud: vive, cuenta su lista y dice desde dónde sale, sin tocar ninguna fuente", async () => {
  const worker = await cargar();
  const salientes = red({ lista: ["congreso.ejemplo.gob.mx", "www.senado.gob.mx", "example.com"] });
  // Quien llama entra por Dallas; el Worker sale por Ciudad de México.
  const r = await pedir(worker, "/salud", { cf: { colo: "DFW", country: "US" } });
  assert.equal(r.status, 200);
  assert.match(r.headers.get("content-type"), /^application\/json/);
  assert.deepEqual(await r.json(), {
    ok: true, permitidos: INTEGRADOS + 1, lista_leida: true, colo: "MEX", pais: "MX", colo_entrada: "DFW",
  });
  assert.deepEqual(salientes.map((p) => p.url).sort(), [LISTA, TRAZA].sort());
  assert.equal((await pedir(worker, "/salud", { method: "POST" })).status, 405);
});

test("/salud: el país sale del centro de datos de salida, no de quien llama", async () => {
  for (const [colo, loc, pais] of [["QRO", "MX", "MX"], ["GDL", "US", "MX"], ["DFW", "US", null], ["DFW", "MX", null]]) {
    const worker = await cargar();
    red({ traza: () => new Response(traza(colo, loc)) });
    const salud = await (await pedir(worker, "/salud", { cf: { colo: "MEX", country: "MX" } })).json();
    assert.deepEqual([salud.ok, salud.colo, salud.pais], [true, colo, pais], `${colo} ${loc}`);
  }
});

test("/salud: sin la traza no se afirma ningún país", async (t) => {
  callado(t);
  for (const trazado of [() => new Response("caído", { status: 503 }), () => { throw new TypeError("fetch failed"); },
    () => new Response("sin el campo\n")]) {
    const worker = await cargar();
    red({ traza: trazado });
    const r = await pedir(worker, "/salud");
    assert.equal(r.status, 200);
    assert.deepEqual(await r.json(), {
      ok: true, permitidos: INTEGRADOS, lista_leida: true, colo: null, pais: null, colo_entrada: null,
    });
  }
});

test("/salud: dice si no pudo leer permitidos.json", async () => {
  const worker = await cargar();
  red({ lista: () => new Response("caído", { status: 500 }) });
  const salud = await (await pedir(worker, "/salud")).json();
  assert.deepEqual([salud.ok, salud.permitidos, salud.lista_leida, salud.pais], [true, INTEGRADOS, false, "MX"]);
});

test("la lista integrada está en permitidos.json", () => {
  const { dominios } = JSON.parse(readFileSync(new URL("./permitidos.json", import.meta.url), "utf8"));
  const codigo = readFileSync(new URL("./worker.js", import.meta.url), "utf8");
  const integrados = codigo.slice(codigo.indexOf("const PERMITIDOS"), codigo.indexOf("]);")).match(/"[a-z0-9.-]+"/g);
  assert.equal(integrados.length, INTEGRADOS);
  for (const dominio of integrados) assert.ok(dominios.includes(JSON.parse(dominio)), dominio);
});

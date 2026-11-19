// Descarga, desde un centro de datos de Cloudflare en México, las fuentes
// oficiales cuyos sitios rechazan conexiones de fuera del país (incluidas las
// de GitHub Actions, donde corre la vigilancia). No es un proxy abierto: solo
// atiende a quien trae el token y solo hacia los dominios de la lista.
//
// La lista son estos dominios más los de egress-mx/permitidos.json en main de
// este repo, que la ronda de expansión de fiscal-extractor amplía sin
// desplegar el Worker. Si ese archivo no se puede leer, quedan estos.
//
// GET /salud, con el mismo token, dice si el Worker vive, cuántos dominios
// tiene su lista y desde qué centro de datos sale; no descarga de ninguna
// fuente.

const PERMITIDOS = new Set([
  "legislacion.edomex.gob.mx",
  "www.legisver.gob.mx",
  "legisver.gob.mx",
  "www.congresogto.gob.mx",
  "congresogto.gob.mx",
  "www.congresoqroo.gob.mx",
  "documentos.congresoqroo.gob.mx",
  // Votaciones nominales del Congreso de la Unión (congreso-extractor).
  "sitl.diputados.gob.mx",
  "gaceta.diputados.gob.mx",
  "www.senado.gob.mx",
  "senado.gob.mx",
  // Desde Cloudflare fuera de México, el SIL no contesta (530): lo pide el
  // Worker congreso-archivo por aquí.
  "sil.gobernacion.gob.mx",
]);

const TIEMPO_MAX = 60_000;

const LISTA_URL =
  "https://raw.githubusercontent.com/OpenCodice/constitucion-extractor/main/egress-mx/permitidos.json";
const LISTA_TTL = 2 * 60_000;
// Del archivo solo se aceptan dominios mexicanos: aunque alguien lograra
// escribir en él, no podría abrir el Worker hacia cualquier sitio.
const DOMINIO_MX = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+mx$/;

// `leida`: si el último intento de leer el archivo lo consiguió.
let lista = { dominios: PERMITIDOS, hasta: 0, leida: false };

async function permitidos(env) {
  if (Date.now() < lista.hasta) return lista;
  try {
    // env.LISTA_URL la sustituye para probar con `wrangler dev`.
    const r = await fetch(env.LISTA_URL || LISTA_URL, {
      cf: { cacheTtl: 60, cacheEverything: true },
      signal: AbortSignal.timeout(5_000),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const datos = await r.json();
    const extra = (Array.isArray(datos?.dominios) ? datos.dominios : [])
      .filter((d) => typeof d === "string" && DOMINIO_MX.test(d));
    lista = { dominios: new Set([...PERMITIDOS, ...extra]), hasta: Date.now() + LISTA_TTL, leida: true };
  } catch {
    // Sin el archivo sigue la última lista leída (o la de arriba), y se vuelve
    // a intentar en un minuto.
    lista = { dominios: lista.dominios, hasta: Date.now() + 60_000, leida: false };
  }
  return lista;
}

// Los centros de datos de Cloudflare en México (códigos IATA).
export const COLOS_MX = new Set(["MEX", "QRO", "GDL"]);
const TRAZA_URL = "https://www.cloudflare.com/cdn-cgi/trace";

// Dónde corre el Worker. `request.cf` no sirve: describe el centro de datos
// al que llegó quien llama, y con `placement` el Worker corre en otro. Una
// petición saliente a la traza de Cloudflare la atiende el centro de datos
// desde el que sale, que es lo que ven las fuentes. De su `loc` no se deduce
// nada: es la geolocalización de la IP que pide, no el lugar del Worker.
async function salida(env) {
  try {
    // env.TRAZA_URL la sustituye para probar con `wrangler dev`.
    const r = await fetch(env.TRAZA_URL || TRAZA_URL, { signal: AbortSignal.timeout(5_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const colo = /^colo=([A-Z]{3})\s*$/m.exec(await r.text())?.[1] ?? null;
    return { colo, pais: COLOS_MX.has(colo) ? "MX" : null };
  } catch (e) {
    console.error(`traza: ${e?.name}: ${e?.message}`);
    return { colo: null, pais: null };
  }
}

async function salud(request, env) {
  const [{ dominios, leida }, { colo, pais }] = await Promise.all([permitidos(env), salida(env)]);
  return Response.json({
    ok: true,
    permitidos: dominios.size,
    // false: no se pudo leer permitidos.json y `permitidos` cuenta la última
    // lista leída o la integrada.
    lista_leida: leida,
    colo,
    // "MX" solo si `colo` es un centro de datos mexicano; si no, null.
    pais,
    colo_entrada: request.cf?.colo ?? null,
  });
}

function iguales(a, b) {
  const ea = new TextEncoder().encode(a);
  const eb = new TextEncoder().encode(b);
  if (ea.length !== eb.length) return false;
  return crypto.subtle.timingSafeEqual(ea, eb);
}

export default {
  async fetch(request, env) {
    const token = (request.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
    // TOKEN: la vigilancia en GitHub; TOKEN_ARCHIVO: el Worker congreso-archivo
    // (descarga perpetua de congreso-extractor), por service binding.
    if (![env.TOKEN, env.TOKEN_ARCHIVO].some((t) => t && iguales(token, t))) {
      return new Response("no autorizado\n", { status: 401 });
    }
    const pedida = new URL(request.url);
    if (pedida.pathname === "/salud") {
      return request.method === "GET" ? salud(request, env) : new Response("método no permitido\n", { status: 405 });
    }
    const destino = pedida.searchParams.get("url");
    let url;
    try {
      url = new URL(destino ?? "");
    } catch {
      return new Response("falta ?url=\n", { status: 400 });
    }
    const { dominios } = await permitidos(env);
    if (!["https:", "http:"].includes(url.protocol) || !dominios.has(url.hostname)) {
      return new Response(`dominio no permitido: ${url.hostname}\n`, { status: 403 });
    }
    // POST de formulario: algunas listas oficiales (la Gaceta de Diputados) solo
    // se obtienen enviando su formulario.
    if (!["GET", "POST"].includes(request.method)) {
      return new Response("método no permitido\n", { status: 405 });
    }
    const envio = request.method === "POST"
      ? { method: "POST", body: await request.arrayBuffer(),
          contentType: request.headers.get("Content-Type") ?? "application/x-www-form-urlencoded" }
      : { method: "GET" };
    let r;
    try {
      r = await fetch(url, {
        method: envio.method,
        body: envio.body,
        headers: {
          "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OpenCodice",
          ...(envio.contentType ? { "Content-Type": envio.contentType } : {}),
        },
        redirect: "follow",
        signal: AbortSignal.timeout(TIEMPO_MAX),
      });
    } catch (e) {
      // Quien llama necesita saber que falló la fuente y no el Worker; el
      // detalle de la excepción se queda en los registros.
      console.error(`${url.hostname}: ${e?.name}: ${e?.message}`);
      const causa = e?.name === "TimeoutError"
        ? `no respondió en ${TIEMPO_MAX / 1000} s`
        : "no aceptó la conexión";
      return new Response(`la fuente ${url.hostname} ${causa}\n`, { status: 502 });
    }
    // Una redirección fuera de la lista no se sigue: el contenido debe venir de
    // la fuente oficial.
    if (!dominios.has(new URL(r.url).hostname)) {
      return new Response(`redirección a un dominio no permitido: ${new URL(r.url).hostname}\n`, { status: 502 });
    }
    const cabeceras = new Headers();
    for (const h of ["content-type", "content-length", "etag", "last-modified"]) {
      const v = r.headers.get(h);
      if (v) cabeceras.set(h, v);
    }
    cabeceras.set("x-url-final", r.url);
    return new Response(r.body, { status: r.status, headers: cabeceras });
  },
};

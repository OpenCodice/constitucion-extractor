// Descarga, desde un centro de datos de Cloudflare en México, las fuentes
// oficiales cuyos sitios rechazan conexiones de fuera del país (incluidas las
// de GitHub Actions, donde corre la vigilancia). No es un proxy abierto: solo
// atiende a quien trae el token y solo hacia los dominios de la lista.
//
// La lista son estos dominios más los de egress-mx/permitidos.json en main de
// este repo, que la ronda de expansión de fiscal-extractor amplía sin
// desplegar el Worker. Si ese archivo no se puede leer, quedan estos.

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

let lista = { dominios: PERMITIDOS, hasta: 0 };

async function permitidos(env) {
  if (Date.now() < lista.hasta) return lista.dominios;
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
    lista = { dominios: new Set([...PERMITIDOS, ...extra]), hasta: Date.now() + LISTA_TTL };
  } catch {
    // Sin el archivo sigue la última lista leída (o la de arriba), y se vuelve
    // a intentar en un minuto.
    lista = { dominios: lista.dominios, hasta: Date.now() + 60_000 };
  }
  return lista.dominios;
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
    const destino = new URL(request.url).searchParams.get("url");
    let url;
    try {
      url = new URL(destino ?? "");
    } catch {
      return new Response("falta ?url=\n", { status: 400 });
    }
    const dominios = await permitidos(env);
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

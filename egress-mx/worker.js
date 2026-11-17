// Descarga, desde un centro de datos de Cloudflare en México, las fuentes
// oficiales cuyos sitios rechazan conexiones de fuera del país (incluidas las
// de GitHub Actions, donde corre la vigilancia). No es un proxy abierto: solo
// atiende a quien trae el token y solo hacia los dominios de la lista.

const PERMITIDOS = new Set([
  "legislacion.edomex.gob.mx",
  "www.legisver.gob.mx",
  "legisver.gob.mx",
  "www.congresogto.gob.mx",
  "congresogto.gob.mx",
  // Votaciones nominales del Congreso de la Unión (congreso-extractor).
  "sitl.diputados.gob.mx",
  "gaceta.diputados.gob.mx",
  "www.senado.gob.mx",
  "senado.gob.mx",
]);

const TIEMPO_MAX = 60_000;

function iguales(a, b) {
  const ea = new TextEncoder().encode(a);
  const eb = new TextEncoder().encode(b);
  if (ea.length !== eb.length) return false;
  return crypto.subtle.timingSafeEqual(ea, eb);
}

export default {
  async fetch(request, env) {
    const token = (request.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
    if (!env.TOKEN || !iguales(token, env.TOKEN)) {
      return new Response("no autorizado\n", { status: 401 });
    }
    const destino = new URL(request.url).searchParams.get("url");
    let url;
    try {
      url = new URL(destino ?? "");
    } catch {
      return new Response("falta ?url=\n", { status: 400 });
    }
    if (!["https:", "http:"].includes(url.protocol) || !PERMITIDOS.has(url.hostname)) {
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
    const r = await fetch(url, {
      method: envio.method,
      body: envio.body,
      headers: {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OpenCodice",
        ...(envio.contentType ? { "Content-Type": envio.contentType } : {}),
      },
      redirect: "follow",
      signal: AbortSignal.timeout(TIEMPO_MAX),
    });
    // Una redirección fuera de la lista no se sigue: el contenido debe venir de
    // la fuente oficial.
    if (!PERMITIDOS.has(new URL(r.url).hostname)) {
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

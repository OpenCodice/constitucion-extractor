# egress-mx

Worker de Cloudflare que descarga fuentes oficiales desde México. Lo usa la
vigilancia de `leyes-estatales` para los estados cuyos sitios rechazan
conexiones de fuera del país (en su `RESOLVER`, `"via": "mx"`).

- Solo atiende peticiones con `Authorization: Bearer <token>` y solo hacia los
  dominios de su lista: `PERMITIDOS` en `worker.js` más los `dominios` de
  `permitidos.json`, que el Worker lee de main de este repo
  (raw.githubusercontent.com, cada 2 minutos; si no puede leerlo, sigue con la
  última lista que leyó o, si no, con `PERMITIDOS`). Del archivo solo acepta
  dominios `.mx`.
- Sumar un dominio no requiere desplegar: basta un commit a `permitidos.json`.
  La ronda de expansión de `fiscal-extractor` lo hace sola (con `PR_TOKEN`)
  cuando el sitio de un estado no responde desde GitHub Actions y el dominio
  es oficial (`.gob.mx`, o `.mx` del mismo dominio que la constitución del
  estado; `scripts/expansion.py egress-agregar`). Un dominio que no sea `.mx`
  sí va en `PERMITIDOS` de `worker.js`, y ese cambio se despliega solo.
- El token es el secret `TOKEN` del Worker y, del lado de GitHub, el secret de
  la organización `EGRESS_MX_TOKEN`. La vigilancia solo lo expone a los pasos
  de resolver y descargar, nunca al del agente.
- El Worker `congreso-archivo` (`congreso-extractor/archivo/`) lo llama por
  service binding con su propio token, el secret `TOKEN_ARCHIVO` (el mismo
  valor que su `EGRESS_TOKEN`).
- Uso: `GET https://egress-mx.<cuenta>.workers.dev/?url=<URL oficial>`; un
  `POST` con cuerpo de formulario se reenvía igual (lo usa `congreso-extractor`
  para las listas de votación de la Gaceta).

Si la fuente no responde o tarda más de 60 s, contesta 502 con una línea que
dice cuál fue (`la fuente <dominio> no respondió en 60 s`); los demás errores
propios son 401 (token), 403 (dominio fuera de la lista) y 502 (redirección
fuera de la lista). Lo que conteste la fuente pasa con su mismo código.

## Salud

`GET https://egress-mx.danielcardeenas.workers.dev/salud`, con la misma
cabecera `Authorization: Bearer <token>` (sin ella, 401). No descarga de
ninguna fuente; contesta 200 con:

```json
{"ok": true, "permitidos": 12, "lista_leida": true, "colo": "MEX", "pais": "MX", "colo_entrada": "IAD"}
```

- `permitidos`: cuántos dominios tiene la lista vigente. `lista_leida` es
  `false` si el último intento de leer `permitidos.json` falló: entonces
  cuenta la última lista leída o, si nunca la leyó, solo `PERMITIDOS`.
- `colo`: el centro de datos de Cloudflare desde el que sale el Worker (código
  IATA), o `null` si no se pudo saber. `request.cf` no lo dice: describe el
  centro de datos al que llegó quien llama (va en `colo_entrada`), y con
  `placement` el Worker corre en otro. Sale de una petición del propio Worker
  a `https://www.cloudflare.com/cdn-cgi/trace`, que atiende el centro de datos
  desde el que sale.
- `pais`: `"MX"` si `colo` es un centro de datos mexicano (`COLOS_MX` en
  `worker.js`: MEX, QRO, GDL); si no lo es o no se supo, `null`. Cloudflare no
  garantiza dónde coloca un Worker con `placement` (dice que con mucho volumen
  puede repartirlo), así que esto es lo que hay que vigilar: con `pais` distinto
  de `"MX"`, las fuentes que rechazan IP extranjeras van a fallar. Si
  Cloudflare abre otro centro de datos en México, hay que sumarlo a `COLOS_MX`.

## Pruebas y despliegue

```bash
node --test                      # el Worker con la red simulada: token, lista, redirecciones, 502, /salud
npx wrangler deploy --dry-run
```

Lo despliega `.github/workflows/desplegar-workers.yml` en cada push a main que
cambie `worker.js` o `wrangler.jsonc` (un commit que solo toca
`permitidos.json` no lanza el workflow, y uno que toca otro Worker no republica
este: `scripts/desplegar_worker.sh` compara la huella del código con la
etiqueta de la versión activa). Es un proxy autenticado y un cambio mal
desplegado podría dejarlo abierto, así que tras desplegar el workflow le hace
una prueba de humo con `EGRESS_MX_TOKEN`: sin token o con uno que no es, 401
(también hacia un dominio de la lista); con token y un dominio fuera de la
lista, 403; con token, `/salud` contesta 200 y `ok`. Si no la pasa en cinco
intentos, vuelve a la versión anterior (`wrangler rollback`) y la corrida
falla. Sin `EGRESS_MX_TOKEN` no despliega.

Desplegar no toca los secrets del Worker (`TOKEN`, `TOKEN_ARCHIVO`). Para
cambiar el token:

```bash
cd egress-mx
openssl rand -hex 32 | tee >(npx wrangler secret put TOKEN) | gh secret set EGRESS_MX_TOKEN --org OpenCodice --visibility all
```

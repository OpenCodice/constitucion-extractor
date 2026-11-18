# scheduler

Worker de Cloudflare que hace de reloj de OpenCodice. Sustituye al cron de
GitHub Actions, que es de mejor esfuerzo, dejó de disparar sin aviso y, en
repos públicos, se apaga tras 60 días sin commits. Tiene un solo Cron Trigger
(`*/15 * * * *`) y hace dos cosas en cada tic:

- Lanza `supervisor.yml` de `OpenCodice/supervisor` (`workflow_dispatch` por
  la API de GitHub, con `origen=scheduler`). Es lo único que lanza: qué más
  tiene que correr y cuándo lo decide el supervisor, con los horarios de su
  `cadenas.toml`.
- Hombre muerto: si `supervisor.yml` no tiene ninguna corrida exitosa en las
  últimas 3 horas, abre en `OpenCodice/supervisor` el issue
  «🚨 El supervisor no corre» (o comenta en el que ya esté abierto, como mucho
  una vez cada 6 horas: lo deduce de la fecha del último comentario). Cuando
  vuelve a correr bien, lo cierra con un comentario. Es el único aviso del
  sistema que espera a una persona: si el supervisor no corre, nadie más lo
  va a notar.

Todo el sistema depende de este tic, así que:

- Un lanzamiento que falla por la red, por límite de peticiones o por un error
  de GitHub se reintenta tres veces en el mismo tic (a los 2, 5 y 15 s); un
  401, 403, 404 o 422 no, porque no va a pasar al reintentar. Cada petición
  tiene 20 s para contestar.
- El lanzamiento y el hombre muerto corren a la vez y cada uno por su cuenta:
  si el lanzamiento falla tras sus reintentos, el hombre muerto corre igual, y
  al revés.
- El Worker no guarda estado (no tiene bindings): un tic no lee nada del
  anterior, y el siguiente lanza igual haya pasado lo que haya pasado.
- El cron de `wrangler.jsonc` tiene que ser `TIC` de `worker.js`; lo comprueban
  las pruebas.

No expone URL. Los registros están en Workers Logs del panel de Cloudflare.

Token: secret `GITHUB_TOKEN`, un fine-grained PAT `opencodice-scheduler` de la
organización OpenCodice con Actions: read and write e Issues: read and write
en `OpenCodice/supervisor` (sin Issues, el aviso del hombre muerto falla con
403, queda en los registros y el lanzamiento sigue). Si el token vence, fallan
las dos cosas a la vez; `supervisor.yml` tiene además un cron propio de
respaldo. Vence al año de crearse; al renovarlo:
`npx wrangler secret put GITHUB_TOKEN` desde esta carpeta.

## Pruebas y despliegue

```bash
node --test                      # el tic contra un GitHub simulado, hombre muerto, cron
npx wrangler deploy --dry-run
```

Lo despliega `.github/workflows/desplegar-workers.yml` en cada push a main que
toque esta carpeta, después de esas pruebas, y comprueba con `wrangler
deployments list` que hay un despliegue nuevo. Necesita los secrets de repo
`CLOUDFLARE_API_TOKEN` (permiso Workers Scripts: Edit) y
`CLOUDFLARE_ACCOUNT_ID`; mientras falten, el workflow termina con un aviso y
sin desplegar, y hay que hacerlo a mano con `npx wrangler deploy`. Desplegar no
toca el secret `GITHUB_TOKEN` del Worker. `egress-mx` no se despliega desde CI.

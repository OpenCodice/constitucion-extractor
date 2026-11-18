# scheduler

Worker de Cloudflare que hace de reloj de OpenCodice: lanza workflows
(`workflow_dispatch` por la API de GitHub) con Cron Triggers. Sustituye al cron
de GitHub Actions, que es de mejor esfuerzo, dejó de disparar sin aviso y, en
repos públicos, se apaga tras 60 días sin commits. Todo lo que lanza lleva el
input `origen=scheduler`.

- Tic cada 15 minutos (`TIC`): lanza `supervisor.yml` de
  `OpenCodice/supervisor`, que es quien revisa las cadenas y relanza lo que
  haga falta. Mientras ese repo no exista o su workflow esté deshabilitado
  (404 o 422), lo anota y sigue con lo demás.
- En el tic del minuto 0, además, la actualización del Congreso
  (`actualizar-congreso.yml` de congreso-extractor): a las 18:00 UTC con
  `publicar=si` (abre el PR) y las demás horas con `publicar=no`, que solo le
  piden al Worker `congreso-archivo` las páginas que faltan.
- `VIGILANCIAS` en `worker.js`: qué vigilancia se lanza y con qué cron (los
  lunes a las 09:00 y a las 13:00 UTC).
- Cron diario (`DIARIO`, 15:30 UTC): el vigilante lanza la vigilancia que
  lleve más de 8 días sin ninguna corrida (una corrida sin terminar desde hace
  más de 12 h ya no cuenta como en curso), y `RONDAS` lanza los workflows
  semanales que no son vigilancias el día indicado, para no gastar otro Cron
  Trigger. Hoy, la ronda de expansión de las leyes estatales
  (`expandir-estatales.yml` de fiscal-extractor), los miércoles. El vigilante
  no las relanza: cada ronda decide sola si le toca trabajar y, si una no
  corre, la siguiente hace lo mismo.
- Hombre muerto, con cada tic: si `supervisor.yml` no tiene ninguna corrida
  exitosa en las últimas 3 horas, abre en `OpenCodice/supervisor` el issue
  «🚨 El supervisor no corre» (o comenta en el que ya esté abierto, como mucho
  una vez cada 6 horas: el Worker no guarda estado y lo deduce de la fecha del
  último comentario). Cuando vuelve a correr bien, lo cierra con un
  comentario. Es el único aviso del sistema que espera a una persona: si el
  supervisor no corre, nadie más lo va a notar.
- Un lanzamiento que falla por la red, por límite de peticiones o por un error
  de GitHub se reintenta dos veces en el mismo tic. Si un workflow todavía no
  declara el input `origen` (422), se lanza sin él.
- Los crons de `wrangler.jsonc` tienen que ser los de `CRONS` en `worker.js`:
  son 4 y no caben más (Cloudflare Free admite 5 Cron Triggers por cuenta).
- No expone URL. Los registros están en Workers Logs del panel de Cloudflare.
- Token: secret `GITHUB_TOKEN`, un fine-grained PAT `opencodice-scheduler` de
  la organización OpenCodice con Actions: read and write (todos los repos) e
  Issues: read and write en `OpenCodice/supervisor` (para el hombre muerto;
  sin ese permiso el aviso falla con 403, queda en los registros y lo demás
  sigue). Vence al año de crearse; al renovarlo:
  `npx wrangler secret put GITHUB_TOKEN` desde esta carpeta.

## Pruebas y despliegue

```bash
node --test                      # qué toca en cada fecha, hombre muerto, crons
npx wrangler deploy --dry-run
```

Lo despliega `.github/workflows/desplegar-workers.yml` en cada push a main que
toque esta carpeta, después de esas pruebas, y comprueba con `wrangler
deployments list` que hay un despliegue nuevo. Necesita los secrets de repo
`CLOUDFLARE_API_TOKEN` (permiso Workers Scripts: Edit) y
`CLOUDFLARE_ACCOUNT_ID`; mientras falten, el workflow termina con un aviso y
sin desplegar, y hay que hacerlo a mano con `npx wrangler deploy`. Desplegar no
toca el secret `GITHUB_TOKEN` del Worker. `egress-mx` no se despliega desde CI.

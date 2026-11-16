# scheduler

Worker de Cloudflare que lanza la vigilancia de los repos de datos de OpenCodice
(`workflow_dispatch` por la API de GitHub) con Cron Triggers. Sustituye al cron
de GitHub Actions, que es de mejor esfuerzo, dejó de disparar sin aviso y, en
repos públicos, se apaga tras 60 días sin commits.

- `VIGILANCIAS` en `worker.js`: qué workflow se lanza y cuándo (UTC). Cada
  horario debe estar también en `triggers.crons` de `wrangler.jsonc`.
- Vigilante diario (15:30 UTC): si una vigilancia lleva más de 8 días sin
  ninguna corrida, la lanza.
- No expone URL. Los registros están en Workers Logs del panel de Cloudflare.
- Token: secret `GITHUB_TOKEN`, un fine-grained PAT `opencodice-scheduler` de
  la organización OpenCodice con solo Actions: read and write (todos los
  repos). Vence al año de crearse; al renovarlo:
  `npx wrangler secret put GITHUB_TOKEN` desde esta carpeta.

Se despliega a mano (`npx wrangler deploy`), como `egress-mx`: así este repo,
en el que también publica el agente, no guarda credenciales de Cloudflare.

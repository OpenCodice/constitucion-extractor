# descargas-mx

Worker de Cloudflare que descarga fuentes oficiales desde México. Lo usa la
vigilancia de `leyes-estatales` para los estados cuyos sitios rechazan
conexiones de fuera del país (en su `RESOLVER`, `"via": "mx"`).

- Solo atiende peticiones con `Authorization: Bearer <token>` y solo hacia los
  dominios de `PERMITIDOS` en `worker.js`; para sumar un estado, agrega su
  dominio ahí y vuelve a desplegar.
- El token es el secret `TOKEN` del Worker y, del lado de GitHub, el secret de
  la organización `DESCARGAS_MX_TOKEN`. La vigilancia solo lo expone a los pasos
  de resolver y descargar, nunca al del agente.
- Uso: `GET https://descargas-mx.<cuenta>.workers.dev/?url=<URL oficial>`.

Se despliega a mano (no desde CI, para no guardar credenciales de Cloudflare
en este repo, en el que también publica el agente):

```bash
cd descargas-mx
npx wrangler deploy
openssl rand -hex 32 | tee >(npx wrangler secret put TOKEN) | gh secret set DESCARGAS_MX_TOKEN --org OpenCodice --visibility all
```

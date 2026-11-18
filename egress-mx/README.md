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
  sí va en `PERMITIDOS` y pide desplegar.
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

El código se despliega a mano, también ahora que `desplegar-workers.yml`
despliega el `scheduler`: es un proxy autenticado y un cambio mal desplegado lo
dejaría abierto, así que no lo publica ningún workflow ni ningún agente. La
lista de dominios no necesita despliegue:

```bash
cd egress-mx
npx wrangler deploy
openssl rand -hex 32 | tee >(npx wrangler secret put TOKEN) | gh secret set EGRESS_MX_TOKEN --org OpenCodice --visibility all
```

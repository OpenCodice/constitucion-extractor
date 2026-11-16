# constitucion-extractor — guía para agentes

Convierte el PDF oficial de una constitución mexicana (la federal y las
estatales) en un archivo Markdown por artículo más metadata derivada. Es
código; los datos que produce viven en `constitucion-mexicana` (federal) y
`leyes-estatales` (estados). Esos repos nunca se editan a mano: si un artículo
está mal, se corrige aquí.

## Estructura

- `extractor/perfil.py` — `PerfilFuente`: todo lo que varía entre un PDF y otro
  (regex de artículo, encabezados y pies de página, estilo de ordinal, cómo se
  leen las fechas de reforma). `CPEUM` es el perfil federal.
- `extractor/fuentes.py` — registro de perfiles: `cpeum`, `jalisco`, `cdmx` y
  los de `extractor/estados/` (un módulo por estado).
- `extractor/parse.py` — texto limpio del PDF → lista de `Article`.
- `extractor/normalize.py` — cuerpo crudo → párrafos, notas de reforma en cursiva.
- `extractor/segments.py`, `passages.py`, `locate.py` — metadata derivada:
  bloques con su reforma, pasajes citables y su ubicación en el PDF.
- `extractor/build.py` — escribe `articulos/*.md` y `metadata/`.
- `extractor/validate.py` — invariantes del repo de datos (gate de los PR).
- `extractor/verificar.py` — fidelidad contra el PDF: `cobertura` (cada párrafo
  literal en el PDF y sin texto omitido entre párrafos) y `auditar`.
- `scripts/agente/` — el agente de CI: `brief.md` (su encargo), `correr.sh`
  (lo lanza) y `cerrar.sh` (compuertas deterministas, publica su arreglo).
- `scripts/resolver_pdf.py` — URL vigente del PDF de un estado.
- `scheduler/` — Worker de Cloudflare que lanza cada lunes la vigilancia de los
  repos de datos (y un vigilante diario relanza la que lleve más de 8 días sin
  correr). El cron de GitHub Actions dejó de disparar y no es confiable. Se
  despliega a mano; ver su README.
- `egress-mx/` — Worker de Cloudflare que descarga desde México las fuentes
  cuyos sitios rechazan IP extranjeras (los estados con `"via": "mx"` en su
  `RESOLVER`). Se despliega a mano; ver su README.
- `scripts/pr_summary.py` — cuerpo del PR de vigilancia.
- `scripts/commits_constitucion.py` — hace el commit (o los dos) del documento
  regenerado, con sus trailers; `scripts/trailers.py` los calcula y
  `scripts/validar_commits.py` los comprueba en `revisar-pr` de cada repo de
  datos. `trailers.py` y `validar_commits.py` existen idénticos en
  `fiscal-extractor` (y `tests/test_trailers.py`): un cambio se hace en los dos.
- `.github/workflows/vigilar-cpeum.yml` y `vigilar-estatales.yml` — la
  vigilancia de `constitucion-mexicana` y `leyes-estatales`. Viven aquí, no en
  los repos de datos, para que el historial de esos repos solo tenga cambios de
  texto legal. Las lanza cada lunes el Worker `scheduler` y abren el PR en el
  repo de datos con `PR_TOKEN`. El arreglo del agente solo puede tocar
  `extractor/` y `tests/` (lo impone `scripts/agente/cerrar.sh`).
- `.github/workflows/credenciales.yml` — comprobación mensual de `PR_TOKEN` y
  `CLAUDE_CODE_OAUTH_TOKEN`, las credenciales de organización que usa la
  vigilancia de todos los repos de datos.

## Comandos

```bash
.venv/bin/python -m extractor build   --pdf CPEUM.pdf --out ../constitucion-mexicana
.venv/bin/python -m extractor build   --pdf X.pdf --out ../leyes-estatales/jalisco/constitucion --perfil jalisco
.venv/bin/python -m extractor validar --out ../constitucion-mexicana
.venv/bin/python -m extractor auditar --pdf CPEUM.pdf --out ../constitucion-mexicana
.venv/bin/python -m extractor verificar --sin-llm --pdf CPEUM.pdf --out ../constitucion-mexicana
.venv/bin/python -m pytest -q          # ~80 s; usa CPEUM.pdf de la raíz como fixture
```

`auditar` revisa todos los artículos; `verificar` solo los que difieren de
`HEAD` en el repo de datos. `verificar` sin `--sin-llm` añade una revisión por
API de OpenAI; es una herramienta manual opcional y la CI no la usa.

## Commits de datos y sus trailers

Cada commit de `constitucion-mexicana` y `leyes-estatales` lleva, además del
título, trailers de git calculados por código, nunca por el agente (su
veredicto solo dice si la extracción es fiel):

```
Reforma CPEUM (DOF 2026-10-07): arts. 82, 116, 122

Documento: cpeum
Tipo: reforma
Publicacion: 2026-10-07
Publicacion-Origen: notas
Medio: DOF
Articulos-Modificados: 082, 116, 122
Fuente: https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf
Fuente-Sha256: cefb525a…
Extractor: OpenCodice/constitucion-extractor@e3ae3f5
```

- `Documento`: `cpeum` o `<estado>/constitucion`. `Medio`: `DOF`, o en un
  estado la parte de `PerfilFuente.fuente` antes de " — " (el título usa sus
  iniciales: `P.O.`).
- `Tipo` por la causa: el archivo oficial descargado (el `.doc` en los estados
  que publican Word) igual al de `fuente/` → `correccion`; distinto → se
  reconstruye el PDF de `fuente/` con el extractor actual: lo que eso cambia
  respecto de lo publicado es un primer commit `correccion` (con la fuente
  anterior) y el resto, la `reforma`, que trae el PDF nuevo a `fuente/`.
  Documento nuevo → `alta`.
- `Publicacion`: fechas de reforma nuevas en la metadata (`notas`); si no hay,
  la versión de la portada (`portada`). Solo en `reforma` y `alta`.
- `Articulos-Adicionados` / `-Modificados` / `-Derogados` en una reforma
  (derogado: el cuerpo pasa a "Se deroga"/"Derogado", o el archivo
  desaparece); `Articulos-Corregidos` en una corrección. Claves de archivo.
- `revisar-pr` del repo de datos corre `scripts/validar_commits.py` sobre cada
  commit del PR y lo fusiona con rebase.

Para el historial existente, `trailers.calcular(documento, tipo, rutas,
lector_antes, lector_despues)` sobre dos árboles (`lector_git(repo, rev)`) y
`trailers.tipo_historico(...)` dan el mensaje sin Fuente ni Extractor;
`trailers.formatear` lo arma.

## Al cambiar el parser

- La compuerta es `auditar`: tras tu cambio no puede listar artículos que antes
  no listaba, en ninguna fuente. Pruébalo con el PDF de cada repo de datos
  (`fuente/CPEUM.pdf`, `{estado}/constitucion/fuente/constitucion.pdf`).
- Prefiere un patrón general a un caso especial por artículo, y agrega una
  prueba de regresión en `tests/`.
- Un cambio aquí modifica texto ya publicado en la siguiente vigilancia. Es lo
  esperado; ese commit sale como corrección de extracción (`Tipo: correccion`).
- No relajes `verificar.py` ni pruebas existentes para que algo pase.

## Agregar un estado

1. Un módulo `extractor/estados/<slug>.py` (guion → guion bajo) con su
   `PERFIL` y su `RESOLVER`; el slug es el de `ENTIDADES` en
   `extractor/estados/__init__.py`.
2. Construir en `leyes-estatales/{estado}/constitucion/` y dejar `auditar` en
   cero problemas.
3. Regenerar la tabla del README de `leyes-estatales` con
   `python scripts/readme_estatales.py ../leyes-estatales`.
4. Marcar `LISTO = True` en su módulo y regenerar `estados.json`
   (`python scripts/estados_json.py`; una prueba exige que esté al día). La
   vigilancia de `leyes-estatales` toma los estados de `resolver_pdf.py
   --matriz` y constitucion.app lee `estados.json`. Un estado que no logra
   quedar fiel, o cuyo PDF oficial no es alcanzable, lleva `LISTO = False` y un
   `MOTIVO` en lenguaje llano, que se publica en constitucion.app/leyes.

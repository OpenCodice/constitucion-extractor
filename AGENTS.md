# constitucion-extractor — guía para agentes

Convierte el PDF oficial de una constitución mexicana (la federal y las
estatales) en un archivo Markdown por artículo más metadata derivada. Es
código; los datos que produce viven en `constitucion-mexicana` (federal) y
`leyes-estatales` (estados). Esos repos nunca se editan a mano: si un artículo
está mal, se corrige aquí.

## Estructura

- `extractor/perfil.py` — `PerfilFuente`: todo lo que varía entre un PDF y otro
  (regex de artículo, encabezados y pies de página, estilo de ordinal, cómo se
  leen las fechas de reforma: de las notas del texto con `fechas_de`, o de una
  tabla aparte con `reformas_de`, como Jalisco). `CPEUM` es el perfil federal.
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
  (lo lanza) y `cerrar.sh` (compuertas deterministas en dos fases:
  `compuertas` sin secretos y `publicar`, que sube su arreglo). En un alta,
  `brief-revision.md` (revisión completa por bloques). `impacto.sh` +
  `brief-impacto.md`: el agente que solo juzga si cada corrección es mejora.
  `publicar_registro.sh` sube a main los registros de `verificaciones/`.
- `scripts/impacto.py` — registro de correcciones confirmadas
  (`verificaciones/impacto/*.jsonl`: documento, artículo, sha256 del PDF y del
  texto antes y después, veredicto), su exigencia sobre los commits de una
  vigilancia (`pendientes-commits`, `cerrar`, `exigir`) y el agrupado de
  cambios iguales para que el agente revise pocos.
- `scripts/impacto_corpus.py` — reconstruye todas las constituciones
  publicadas desde su `fuente/` con el extractor en disco y lista cada
  artículo que cambiaría (y regresiones de cobertura).
- `scripts/revision.py` — revisión completa de un alta: bloques de artículos
  con el texto crudo de sus páginas, y el resultado en
  `verificaciones/altas/*.jsonl` con cada hallazgo (no se vuelve a pagar con el
  mismo PDF y extractor). En fiscal-extractor, esos hallazgos los toma la
  reparación autónoma de las leyes federales y estatales; aquí el agente de la
  vigilancia ya repara el extractor cuando la extracción tiene un defecto.
- `.github/workflows/impacto.yml` — en cada push a main que toca `extractor/`
  (un commit a mano incluido) mide su impacto en todo lo publicado y confirma
  las correcciones con el agente.
- `scripts/resolver_pdf.py` — URL vigente del PDF de un estado. CDMX sale de
  la Consejería Jurídica (data.consejeria.cdmx.gob.mx), no del Congreso, cuyo
  PDF se quedó en 2019. `certs/` guarda los intermedios TLS que algunos sitios
  no envían; los usan el resolver y la descarga de la vigilancia.
- `scheduler/` — Worker de Cloudflare que lanza cada lunes la vigilancia de los
  repos de datos (y un vigilante diario relanza la que lleve más de 8 días sin
  correr), y cada miércoles, con el mismo cron diario (`RONDAS`), la ronda de
  expansión de las leyes estatales (`expandir-estatales.yml` de
  fiscal-extractor). El cron de GitHub Actions dejó de disparar y no es
  confiable. Se despliega a mano; ver su README.
- `egress-mx/` — Worker de Cloudflare que descarga desde México las fuentes
  cuyos sitios rechazan IP extranjeras (los estados con `"via": "mx"` en su
  `RESOLVER`). Su código se despliega a mano; su lista de dominios es
  `egress-mx/permitidos.json`, que lee de main sin desplegarse y que la ronda
  de expansión de fiscal-extractor amplía sola. Ver su README.
- `scripts/pr_summary.py` — cuerpo del PR de vigilancia.
- `scripts/commits_constitucion.py` — hace el commit (o los dos) del documento
  regenerado, con sus trailers (con `--verificadas`, no publica un documento
  cuya corrección no esté confirmada); `scripts/trailers.py` los calcula y
  `scripts/validar_commits.py` los comprueba antes de fusionar (ver
  `revisar-pr.yml`). `trailers.py`, `validar_commits.py`, `validar_pr.sh`,
  `impacto.py`, `revision.py`, `agente/impacto.sh`, `agente/brief-impacto.md`,
  `agente/brief_revision.py`, `agente/publicar_registro.sh` y
  `.github/workflows/revisar-pr.yml` existen idénticos en `fiscal-extractor` (y
  `tests/test_trailers.py`, `tests/test_impacto.py`): un cambio se hace en los
  dos.
- `.github/workflows/revisar-pr.yml` (reutilizable) y `scripts/validar_pr.sh` —
  el gate de los PR de los repos de datos, que así no necesitan workflows
  propios.
  Cada vigilancia lo llama tras abrir su PR (y se puede lanzar a mano con
  `gh workflow run revisar-pr.yml -f repo=OpenCodice/<repo> -f pr=<n> -f
  prefijo=reforma/` para un PR que quedó abierto). El job `validar`, sin
  secretos, corre `validar_pr.sh` sobre el sha de la cabeza del PR:
  `extractor validar` de cada documento (en `leyes-estatales`, cada
  `{estado}/constitucion` con su perfil y las leyes `{estado}/{ley}` con el
  `validar` de fiscal-extractor) y `validar_commits.py` sobre cada commit.
  Solo si pasó, `fusionar` (con `PR_TOKEN`) fusiona con rebase un PR de la
  rama de la vigilancia con la etiqueta `verificado`, atado a ese sha
  (`--match-head-commit`): si la cabeza cambió, no se fusiona. También publica
  el resultado como commit status (`validar-externo`), solo informativo:
  `PR_TOKEN` no tiene el permiso «Commit statuses», así que la protección de
  main no puede exigirlo. El gate es que solo este job fusiona, y solo lo
  validado.
- `.github/workflows/vigilar-cpeum.yml` y `vigilar-estatales.yml` — la
  vigilancia de `constitucion-mexicana` y `leyes-estatales`. Viven aquí, no en
  los repos de datos, para que el historial de esos repos solo tenga cambios de
  texto legal. Las lanza cada lunes el Worker `scheduler` y abren el PR en el
  repo de datos con `PR_TOKEN`. El arreglo del agente solo puede tocar
  `extractor/` y `tests/` (lo impone `scripts/agente/cerrar.sh`).
- `leyes-estatales` también guarda las demás leyes de cada estado
  (`{estado}/{ley}/`, `fuentes.json`), que produce y vigila fiscal-extractor
  (`vigilar-leyes-estatales.yml`, ver su AGENTS.md). Esta vigilancia solo toca
  `{estado}/constitucion/`. `scripts/readme_estatales.py` regenera las tablas
  del README (estados, con esas leyes, y automatización, entre sus marcas); lo
  corre `vigilar-leyes-estatales.yml` y va en su commit `Tipo: indice`. Los trailers de los dos se validan con
  `scripts/validar_commits.py` (Documento `<estado>/<clave>`), y cualquier PR
  de `leyes-estatales` pasa por `validar_pr.sh` completo: constituciones y
  leyes.
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
  Documento nuevo → `alta`. Una corrección que no cambia el texto de ningún
  artículo (solo metadata) es `metadatos`, con título `Metadatos de <sigla>:
  <archivos>`; una `correccion` sin artículos la rechaza el validador.
- `Publicacion`: fechas de reforma nuevas en la metadata (`notas`); si no hay,
  la versión de la portada (`portada`). Solo en `reforma` y `alta`.
- `Articulos-Adicionados` / `-Modificados` / `-Derogados` en una reforma
  (derogado: el cuerpo pasa a "Se deroga"/"Derogado", o el archivo
  desaparece); `Articulos-Corregidos` en una corrección. Claves de archivo.
- `revisar-pr.yml` corre `scripts/validar_commits.py` sobre cada commit del PR
  y lo fusiona con rebase.

El historial de los dos repos se reescribió el 2026-11-17 (la final): cada
constitución empieza en su alta y sigue solo con sus reformas reales, todas
extraídas con el extractor de ese día desde el archivo de su `fuente/`, con
todos los trailers (también Fuente, Fuente-Sha256 y Extractor). Ese mismo día
una última reescritura solo quitó del historial la infraestructura (`.github/`,
`AGENTS.md`, `CLAUDE.md`, `.gitignore`; ver el `AGENTS.md` raíz). Desde
entonces no se reescribe: los hashes son estables. `trailers.calcular(documento, tipo,
rutas, lector_antes, lector_despues)` sobre dos árboles (`lector_git(repo,
rev)`) y `trailers.formatear` dan el mensaje de cualquier commit.

## Al cambiar el parser

- La compuerta es `auditar`: tras tu cambio no puede listar artículos que antes
  no listaba, en ninguna fuente. Pruébalo con el PDF de cada repo de datos
  (`fuente/CPEUM.pdf`, `{estado}/constitucion/fuente/constitucion.pdf`).
- Prefiere un patrón general a un caso especial por artículo, y agrega una
  prueba de regresión en `tests/`.
- Un cambio aquí modifica texto ya publicado, y eso solo se publica como
  corrección (`Tipo: correccion`) si cada artículo que cambia está confirmado
  como mejora contra el PDF en `verificaciones/impacto/`. Al llegar a main,
  `impacto.yml` reconstruye todas las constituciones publicadas, lista lo que
  cambia y el agente lo juzga; lo rechazado o sin juzgar no se publica (la
  vigilancia rehace sus commits sin esa corrección y deja el documento como
  estaba). Antes de hacer push, corre `python scripts/impacto_corpus.py
  --trabajo /tmp/impacto --cpeum ../constitucion-mexicana --estatales
  ../leyes-estatales` (unos 2 min) y mira lo que cambia: lo que no sea mejora
  no debe entrar.
- Un arreglo del agente en la vigilancia pasa por lo mismo antes de entrar: si
  algo de lo que cambia en el corpus empeora o no se puede confirmar, se
  descarta entero.
- No relajes `verificar.py` ni pruebas existentes para que algo pase.

## Agregar un estado

1. Un módulo `extractor/estados/<slug>.py` (guion → guion bajo) con su
   `PERFIL` y su `RESOLVER`; el slug es el de `ENTIDADES` en
   `extractor/estados/__init__.py`.
2. Construir en `leyes-estatales/{estado}/constitucion/` y dejar `auditar` en
   cero problemas. Su primera vigilancia no lo publica solo con eso: el agente
   lo revisa entero contra el PDF, por bloques (`scripts/revision.py`), y solo
   se da de alta sin hallazgos. Puedes adelantarlo con
   `python scripts/revision.py planear …` y revisar tú los bloques.
3. La tabla del README de `leyes-estatales` la regenera la siguiente
   vigilancia de las leyes estatales (`scripts/readme_estatales.py`).
4. Marcar `LISTO = True` en su módulo y regenerar `estados.json`
   (`python scripts/estados_json.py`; una prueba exige que esté al día). La
   vigilancia de `leyes-estatales` toma los estados de `resolver_pdf.py
   --matriz` y constitucion.app lee `estados.json`. Un estado que no logra
   quedar fiel, o cuyo PDF oficial no es alcanzable, lleva `LISTO = False` y un
   `MOTIVO` en lenguaje llano, que se publica en constitucion.app/leyes.

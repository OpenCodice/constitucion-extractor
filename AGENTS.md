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
- `extractor/fuentes.py` — registro de perfiles: `cpeum`, `jalisco`, `cdmx`.
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
- `scripts/pr_summary.py` — cuerpo del PR de vigilancia.
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

## Al cambiar el parser

- La compuerta es `auditar`: tras tu cambio no puede listar artículos que antes
  no listaba, en ninguna fuente. Pruébalo con el PDF de cada repo de datos
  (`fuente/CPEUM.pdf`, `{estado}/constitucion/fuente/constitucion.pdf`).
- Prefiere un patrón general a un caso especial por artículo, y agrega una
  prueba de regresión en `tests/`.
- Un cambio aquí modifica texto ya publicado en la siguiente vigilancia. Es lo
  esperado; ese PR sale titulado como corrección de extracción.
- No relajes `verificar.py` ni pruebas existentes para que algo pase.

## Agregar un estado

1. Perfil nuevo en `extractor/fuentes.py` y su resolver en
   `scripts/resolver_pdf.py`.
2. Construir en `leyes-estatales/{estado}/constitucion/` y dejar `auditar` en
   cero problemas.
3. Agregar el estado a la matriz de `vigilar-estatales.yml` y a `ESTADOS` en
   `revisar-pr.yml` de `leyes-estatales`.

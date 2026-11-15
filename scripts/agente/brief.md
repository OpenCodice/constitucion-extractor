# Verificar y, si hace falta, reparar una extracción

Trabajas en `constitucion-extractor`, el código que convierte PDFs oficiales de
constituciones mexicanas (la federal y las estatales) en un archivo Markdown por
artículo. Ese texto se versiona en git como registro público de la ley vigente,
y esta corrida terminará en un commit automático sin revisión humana. Por eso
lo único que importa es que el texto extraído diga exactamente lo que dice el
PDF: ni una palabra de más, ni una de menos, ni fuera de lugar.

## Situación

El vigilante semanal descargó el PDF vigente y regeneró el repo de datos. Hay
artículos que cambiaron respecto de la versión anterior (lista abajo). Puede
ser una reforma real, un cambio de formato del PDF que el extractor no maneja
(pies o encabezados de página nuevos, encabezados de capítulo con otro estilo,
saltos de página a media oración), o las dos cosas a la vez.

- Extractor (tu directorio de trabajo, repo git): `__EXTRACTOR__`
- Repo de datos regenerado: `__OUT__` (los `.md` están en `articulos/`)
- PDF vigente: `__PDF__`
- Perfil de la fuente: `__PERFIL__` (definido en `extractor/perfil.py` / `extractor/fuentes.py`)
- Para regenerar: `__BUILD__`
- Versión anterior de un artículo: `git -C __OUT__ show HEAD:./articulos/NNN.md`

Artículos cambiados (`git status`):

```
__CAMBIADOS__
```

Una comprobación determinista (`python -m extractor verificar --sin-llm`, basada
en `cobertura` de `extractor/verificar.py`) ya revisó que cada párrafo extraído
esté literal en el texto limpio del PDF y que no quede texto sin extraer entre
párrafos. Su resultado:

```
__COBERTURA__
```

Esa comprobación no ve todo: compara contra el texto ya filtrado por el propio
extractor, así que no detecta un pie de página que el extractor no reconoce y
dejó colado dentro de un artículo, ni texto de un encabezado estructural pegado
al cuerpo, ni un artículo que absorbió a su vecino. Eso te toca a ti.

## Qué hacer

1. Lee con `pdfplumber` las páginas del PDF donde vive cada artículo cambiado y
   compáralas con el `.md` nuevo. No te fíes de la versión anterior del repo ni
   de tu memoria de la ley: la fuente de verdad es este PDF. Si son muchos
   artículos, revísalos todos igual; puedes escribir scripts para hacerlo.
2. Si la extracción es fiel, no toques nada.
3. Si hay un defecto de extracción, corrígelo en el código del extractor (el
   perfil de la fuente o el parser), de la forma más general que el caso
   permita —un patrón, no un parche para un artículo—, y agrega una prueba de
   regresión en `tests/`. Regenera con el comando de arriba y vuelve a comparar
   contra el PDF hasta que quede fiel.
4. Antes de terminar, si cambiaste código: `python -m pytest -q` debe pasar y
   `python -m extractor auditar --pdf __PDF__ --out __OUT__ --perfil __PERFIL__`
   no puede listar artículos que no estén ya en `__TRABAJO__/base.json` (la
   línea base antes de tu cambio). Un arreglo que rompe otro artículo se
   descarta entero.

## Límites

- Nunca edites a mano los archivos del repo de datos: su contenido solo puede
  salir de correr el extractor. Después de ti, el pipeline descarta el repo de
  datos y lo regenera con tu versión del extractor, así que una edición manual
  no sobrevive y solo esconde el problema.
- No modifiques `extractor/verificar.py` ni las pruebas existentes para que
  pasen; son la compuerta que decide si tu arreglo se publica.
- No hagas commit ni push; el pipeline lo hace si las compuertas pasan.
- Si no logras una extracción fiel, dilo en el veredicto. Un "no pude" honesto
  deja el cambio en revisión humana; un "fiel" equivocado publica ley falsa.

## Entrega

Escribe `__TRABAJO__/veredicto.json` con esta forma, y nada más como salida final:

```json
{
  "fiel": true,
  "reparado": false,
  "titulo_commit": "solo si reparado: una línea que describa el arreglo",
  "resumen": "dos o tres frases: qué cambió en la ley y, si aplica, qué defecto había y cómo lo arreglaste",
  "unidades": [{"clave": "082", "veredicto": "fiel", "nota": "qué verificaste"}]
}
```

`fiel` es verdadero solo si TODOS los artículos cambiados, tal como quedan
después de tu trabajo, reproducen el PDF. `veredicto` por unidad: `fiel`,
`artefacto` o `incierto`.

import re

from ..perfil import perfil_estatal, version_ultima_reforma

LISTO = True

PERFIL = perfil_estatal(
    ambito="nuevo-leon",
    clave="nle",
    nombre="Constitución Política del Estado Libre y Soberano de Nuevo León",
    fuente="Periódico Oficial del Estado de Nuevo León — H. Congreso del Estado de Nuevo León",
    url_fuente=("https://www.hcnl.gob.mx/trabajo_legislativo/leyes/pdf/"
                "CONSTITUCION%20POLITICA%20DEL%20ESTADO%20LIBRE%20Y%20SOBERANO%20DE%20NUEVO%20LEON.pdf"),
    texto_original="1917-12-16",
    label_ordinal="plano",
    version_de=version_ultima_reforma,
    # El número de página va suelto en su propia línea; sin esto se pega a media frase.
    page_footer_re=re.compile(r"\d{1,3}$"),
)

# Nombre estable: el Congreso sobrescribe el mismo archivo en cada reforma.
RESOLVER = {"tipo": "directo", "url": PERFIL.url_fuente}

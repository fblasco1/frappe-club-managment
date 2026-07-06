# Importación de inscripciones desde padrón por actividad

## Contexto

CSV `socios_actividades_mapeadas.csv` generado desde el Excel «SOCIOS POR ACTIVIDAD» con columnas:

- `nro_socio`, `nombre`, `actividad_padron`, `actividades_mapeadas` (separadas por ` | `)

Las etiquetas legacy de básquet (`BASQUET MASCULINO | TIRA AZUL | U9`) se normalizan a la actividad única **Basquet** con grupos `Masculino / Azul`, etc. (`basquet_estructura_unificada.md`).

## Scenario: mapeo de etiquetas a selección Frappe

Given una etiqueta `GIMNASIA ARTISTICA 2 VECES POR SEMANA`
When se parsea la etiqueta
Then devuelve actividad `Gimnasia Artistica`, grupo `2 Clases por Semana`.

Given una etiqueta `BASQUET MASCULINO | TIRA AZUL | U9`
When se parsea la etiqueta
Then devuelve actividad `Basquet`, grupo `Masculino / Azul`, equipo `U9`.

Given una etiqueta `CENTRO DE JUBILADOS`
When se procesa la fila
Then no crea `Inscripcion Actividad` y marca al socio como categoría `Jubilado` si aplica.

Given una etiqueta `CUOTA FEDERATIVA DE VOLEY` o `CUOTA FEDERATIVA BASQUET - MINIBASQUET`
When se procesa la fila
Then no crea inscripción (cargo federativo aparte); registra advertencia.

## Scenario: importación por nro de padrón

Given un socio existente con `nro_socio_padron` = `11264`
And CSV con actividades `LIGA TABI | BASQUET MASCULINO | TIRA AZUL | U9`
When se ejecuta el import con `dry_run=False`
Then crea inscripciones activas para Futbol (TABI A) y Basquet (Masculino / Azul / U9)
And no duplica inscripciones ya activas.

## Scenario: importación local con copia de producción

Given backup reciente de `gestion.icdpedroechague.com.ar`
When se restaura en devcontainer y se ejecuta `import_socios_actividades_padron` con `dry_run=False`
Then las inscripciones quedan en local para validación antes del deploy a producción.

# Spec: Socio — contacto y domicilio estructurado

Refactor del DocType `Socio` para teléfonos separados, email opcional en migración/padrón
y domicilio desglosado alineado al CSV del padrón y a la futura app de socio.

**Ruta:** `club_management/specs/socio_contacto_domicilio.md`

---

## Scenario: teléfono fijo opcional y móvil distinto

Given el DocType `Socio`
When Secretaría o la migración de padrón cargan un registro
Then existe el campo `telefono_fijo` (opcional)
And existe el campo `telefono_movil` (opcional en esta iteración; la app de socio exigirá completitud más adelante)
And no existe el campo legacy `telefono`.

---

## Scenario: email vacío permitido en padrón / alta incompleta

Given un socio importado del padrón sin email en el CSV
When se inserta el documento con `ignore_mandatory=True` (script de migración)
Then `email` queda vacío (string vacío / null)
And la inserción no fabrica placeholders de correo.

---

## Scenario: email y móvil obligatorios en altas normales

Given un alta de Socio desde Secretaría, validación de solicitud o formulario estándar
When se intenta crear el documento sin `email` o sin `telefono_movil`
Then la operación falla con `MandatoryError` o validación equivalente
And la migración masiva del padrón sigue siendo la única excepción (`ignore_mandatory=True`).

---

## Scenario: domicilio desglosado y jerarquía geográfica

Given el DocType `Socio`
Then los campos de domicilio son `calle`, `numero`, `piso`, `departamento`
And la jerarquía geográfica en formulario es `provincia` → `ciudad` → `localidad_barrio` → `codigo_postal`
And no existe el campo legacy `domicilio` ni `localidad` (reemplazado por `localidad_barrio`).

---

## Scenario: migración de datos legacy en base

Given filas existentes con `telefono`, `domicilio` o `localidad` poblados
When corre el patch `migrate_socio_contacto_domicilio`
Then `telefono` se copia a `telefono_movil` si este está vacío
And `domicilio` se copia a `calle` si esta está vacía
And `localidad` se copia a `localidad_barrio` si esta está vacía
And las columnas legacy se eliminan.

---

## Scenario: importación CSV de padrón mapea columnas nuevas

Given una fila CSV con `teléfono`, `tel_movil`, `email`, `calle`, `numero`, `piso`, `departamento`, `provincia`, `ciudad`, `localidad_barrio`
When `build_socio_payload` procesa la fila
Then cada valor de `teléfono` y `tel_movil` pasa por `parsear_telefono`
And el número limpio con longitud ≥ 10 se asigna a `telefono_movil`
And el número limpio con longitud &lt; 10 se asigna a `telefono_fijo`
And `email` queda vacío si el CSV no trae valor
And los campos de domicilio se copian 1:1 sin concatenar en un único `domicilio`.

---

## Scenario: heurística `parsear_telefono` en migración de padrón

Given un valor crudo de teléfono del CSV (con guiones, espacios, paréntesis o prefijo `+`)
When se ejecuta `parsear_telefono(numero_crudo)`
Then el valor se reduce a dígitos únicamente
And si queda vacío retorna `None`
And si la longitud del número limpio es ≥ 10 retorna tipo `"Celular"`
And si la longitud es &lt; 10 retorna tipo `"Fijo"`.

---

## Scenario: teléfonos inválidos en reporte de choques

Given una fila del padrón cuyo `teléfono` o `tel_movil` tiene menos de 6 dígitos tras limpiar
When `migrate_padron_csv` procesa la fila
Then el socio se inserta omitiendo ese número
And el identificador de la fila figura en el reporte de choques bajo **Teléfonos Inválidos**
And el contador de fallidos no incrementa por este motivo.

---

## Scenario: Solicitud Asociacion y Tutor No Socio alineados

Given los DocTypes `Solicitud Asociacion` y `Tutor No Socio`
Then comparten el mismo modelo de contacto (`telefono_fijo`, `telefono_movil` reqd, `email` reqd)
And domicilio desglosado (`calle`, `numero`, `piso`, `departamento`, `provincia`, `ciudad`, `localidad_barrio`, `codigo_postal`)
And el portal/API acepta nombres legacy (`telefono` → `telefono_movil`, `localidad` → `localidad_barrio`).

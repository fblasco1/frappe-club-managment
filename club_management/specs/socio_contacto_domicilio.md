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
Then `telefono_fijo` ← `teléfono`, `telefono_movil` ← `tel_movil`, `email` vacío si CSV vacío
And los campos de domicilio se copian 1:1 sin concatenar en un único `domicilio`.

---

## Scenario: Solicitud Asociacion y Tutor No Socio alineados

Given los DocTypes `Solicitud Asociacion` y `Tutor No Socio`
Then comparten el mismo modelo de contacto (`telefono_fijo`, `telefono_movil` reqd, `email` reqd)
And domicilio desglosado (`calle`, `numero`, `piso`, `departamento`, `provincia`, `ciudad`, `localidad_barrio`, `codigo_postal`)
And el portal/API acepta nombres legacy (`telefono` → `telefono_movil`, `localidad` → `localidad_barrio`).

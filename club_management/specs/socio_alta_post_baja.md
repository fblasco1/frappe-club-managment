# Spec: Alta de Socio posterior a baja

Un socio dado de baja (`estado = Baja`) debe poder **volver a ser socio**
sin crear un documento nuevo. Secretaría reutiliza el mismo `Socio`
(mismo DNI y número).

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `socio_minimo.md`,
`cuotas_sociales_suscripcion.md`, `inscripcion_gestion_desk.md`  
**Módulo:** `members/`  
**Fuera de alcance:** restaurar automáticamente inscripciones o becas previas;
crear un segundo `Socio` con el mismo DNI.

---

## Modelo

- Transición server-side `Baja` → `Activo` vía `dar_alta_socio`.
- `estado` sigue siendo read-only en el formulario.
- Se conserva `numero_socio` / `name`.
- **Antigüedad (`fecha_alta`):** se conserva si el alta ocurre **dentro de los
  6 meses** posteriores a la baja (inclusive). Si pasaron **más de 6 meses**,
  `fecha_alta` se reinicia a la fecha de hoy (nueva antigüedad, p. ej. Vitalicio).
- La ventana se mide desde el timestamp de la baja
  (`ultimo_cambio_estado_en` mientras el socio está en `Baja`).
- Al pasar a `Activo` se re-sincroniza la suscripción de cuota social
  (la baja la había cancelado).
- Las inscripciones históricas en `Baja` **no** se reactivan solas:
  Secretaría puede inscribir de nuevo con el flujo Desk existente.

---

## Scenario: Secretaría da de alta a un socio en Baja (dentro de 6 meses)

Given un `Socio` con `estado = Baja`
And la baja ocurrió hace 6 meses o menos
And un usuario con rol `Secretaria`
When ejecuta **Dar de alta** (opcionalmente con motivo)
Then `estado` pasa a `Activo`
And se registra auditoría (`ultimo_cambio_estado_*`, motivo)
And el `name` / `numero_socio` no cambian
And `fecha_alta` permanece con el valor anterior (se conserva la antigüedad).

---

## Scenario: alta después de más de 6 meses reinicia la antigüedad

Given un `Socio` con `estado = Baja` y `fecha_alta` de la primera activación
And la baja ocurrió hace **más de 6 meses**
When Secretaría ejecuta **Dar de alta**
Then `estado` pasa a `Activo`
And `numero_socio` no cambia
And `fecha_alta` se setea a la fecha de hoy
And la antigüedad (Vitalicio, etc.) se calcula desde esta nueva alta.

---

## Scenario: no se crea un segundo Socio por el mismo DNI

Given un `Socio` en `Baja` con `dni` conocido
When Secretaría quiere que esa persona vuelva a ser socio
Then usa **Dar de alta** sobre el documento existente
And un alta nueva con el mismo DNI sigue bloqueada por unicidad.

---

## Scenario: alta restaura suscripción de cuota social

Given un `Socio` que tenía suscripción de cuota activa
And Secretaría lo dio de baja (suscripciones canceladas)
When ejecuta **Dar de alta**
Then vuelve a existir una suscripción vigente de cuota social para su `Customer`
And no se emite factura inmediata (`submit_invoice = 0`).

---

## Scenario: no se puede dar de alta si no está en Baja

Given un `Socio` con `estado` distinto de `Baja` (p. ej. `Activo` o `Moroso`)
When Secretaría invoca `dar_alta_socio`
Then recibe `frappe.ValidationError`
And el `estado` no cambia.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When invoca `dar_alta_socio` o la API Desk `dar_alta`
Then recibe `PermissionError`.

---

## UI Desk

Given el formulario `Socio` abierto por Secretaría
And `estado = Baja`
When se muestra el grupo **Operación Secretaría**
Then aparece la acción **Dar de alta**
And no aparece **Dar de baja**
When el socio pasa a `Activo`
Then vuelven las acciones habituales (inscribir, marcar moroso, dar de baja, etc.).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `members/services/socio_operaciones_secretaria.py` (`dar_alta_socio`) |
| Transición / antigüedad | `members/services/socio_transitions.py` |
| API whitelist | `members/api/socio_operaciones_desk.py` (`dar_alta`) |
| Client script | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_socio_operaciones_secretaria.py`, `members/tests/test_suscripciones_socio_integracion.py` |

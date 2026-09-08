# Spec: Corregir número de socio (provisional → definitivo)

**Relacionado:** `socio_minimo.md`, `socio_alta_edicion_secretaria.md`  
**Módulo:** `members/`

El `numero_socio` es el `name` (PK) y en el formulario es inmutable. Secretaría /
System Manager deben poder **reasignar** un número provisional a uno definitivo
mediante un servicio que renombra el documento y actualiza enlaces.

Caso operativo local: socios `12239`–`12246` cargados con número provisional;
cuando exista el número de carnet/histórico correcto, se corrige con este flujo.

---

## Scenario: Secretaría corrige número provisional a uno libre

Given un `Socio` existente con `name` / `numero_socio` = `12239`
And no existe otro `Socio` con `numero_socio` = `5001`
When invoca `corregir_numero_socio(socio="12239", nuevo_numero=5001)`
Then el documento pasa a `name` = `"5001"` y `numero_socio` = 5001
And los Link/Dynamic Link a `"12239"` quedan apuntando a `"5001"`
And el socio antiguo `"12239"` ya no existe

---

## Scenario: destino ocupado falla

Given ya existe `Socio` `5001`
When intenta `corregir_numero_socio(socio="12239", nuevo_numero=5001)`
Then recibe `frappe.ValidationError` (número ya asignado)
And el socio `12239` no cambia

---

## Scenario: mismo número es no-op exitoso

Given `Socio` `12239`
When `corregir_numero_socio(socio="12239", nuevo_numero=12239)`
Then no falla y el socio permanece `12239`

---

## Scenario: acceso restringido

Given usuario sin rol `Secretaria` ni `System Manager`
When invoca la API Desk
Then recibe `PermissionError`

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `members/services/corregir_numero_socio.py` |
| API | `members/api/socio_operaciones_desk.py` → `corregir_numero_socio` |
| UI | botón en `socio.js` (Operación Secretaría) |
| Tests | `members/tests/test_corregir_numero_socio.py` |

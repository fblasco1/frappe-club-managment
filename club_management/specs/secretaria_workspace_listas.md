# Spec: Listas operativas en workspace Secretaría

Panel Desk para rol `Secretaria`: además de las number cards, dos listas
preview (máx. 5 filas) con enlace **Ver más** a la lista completa filtrada.

---

## Scenario: solicitudes pendientes — las más antiguas primero

Given existen más de 5 `Solicitud Asociacion` con `workflow_state = Pendiente`
When Secretaria abre el workspace **Secretaría** o llama al endpoint del panel
Then el sistema devuelve como máximo **5** solicitudes
And están ordenadas por `creation` **ascendente** (la más vieja primero)
And cada fila muestra al menos `nombre`, `dni` y fecha de ingreso
And un enlace **Ver más** abre la lista de `Solicitud Asociacion` filtrada a `Pendiente`.

---

## Scenario: socios morosos — mayor deuda primero

Given existen socios con `estado = Moroso` y distintos `saldo_deuda`
When Secretaria consulta el panel
Then devuelve como máximo **5** socios morosos
And están ordenados por `saldo_deuda` **descendente**
And cada fila muestra **identificador** (`name` del Socio, p. ej. `SOC-2026-0001`),
**nombre y apellido**, **categoría**, **estado**, **actividad** (vacía o asignada)
y el **saldo de deuda**
And **Ver más** abre la lista de `Socio` filtrada a `Moroso`.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When intenta llamar al endpoint del panel
Then recibe error de permisos (no ve datos de otros socios/solicitudes).

---

## Notas

- `saldo_deuda` en `Socio` es moneda de solo lectura; la integración de cobranza
  (ERPNext / SIRO) lo actualizará en sprints posteriores. Hasta entonces puede ser 0.

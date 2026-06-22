# Spec: Operación interna Secretaría (MVP sin solicitudes ni grupo familiar)

Desk orientado a secretaría interna: ABM socios, cobranza manual y actividades.
**Fuera de alcance en esta fase:** flujo público de solicitud de asociación y gestión
de grupo familiar (segunda implementación).

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `socio_alta_edicion_secretaria.md`,
`cobranza_periodica_mensual.md`

---

## Scenario: workspace Secretaría sin solicitudes ni grupos familiares

Given un usuario con rol `Secretaria`
When abre el workspace **Secretaría**
Then no ve enlaces ni atajos a `Solicitud Asociacion` ni `Grupo Familiar`
And no ve number cards de solicitudes pendientes ni aprobados pendientes de pago
And sigue viendo socios morosos, socios activos, cuotas inline y lista de morosos.

---

## Scenario: panel Desk sin lista de solicitudes

Given Secretaría en el workspace **Secretaría**
When carga el panel custom de listas
Then no aparece la sección «Solicitudes pendientes de revisión»
And sigue apareciendo la lista de socios morosos y cuotas sociales.

---

## Scenario: formulario Socio oculta grupo familiar y solicitud de origen

Given Secretaría abre un formulario `Socio` (nuevo o existente)
When visualiza la sección de vínculos
Then los campos `grupo_familiar` y `solicitud_origen` no se muestran
And para `categoria = Menor` sigue siendo obligatorio `tipo_tutor` y `tutor`.

---

## Scenario: alta guiada menor exige tutor adulto sin grupo familiar

Given Secretaría usa **Alta guiada** con `categoria = Menor`
When intenta crear sin `tipo_tutor` o `tutor`
Then recibe error de validación
When completa tutor (Socio o Tutor No Socio) sin `grupo_familiar`
Then el socio se crea correctamente.

---

## Scenario: generación de deuda mensual con fechas válidas en ERPNext

Given un `Socio` `Activo` con `Customer` ERPNext
And la fecha de referencia del período es anterior a hoy (generación tardía en el mes)
When se ejecuta `generar_deuda_mensual_socio`
Then `posting_date` no es anterior a hoy
And `due_date` es mayor o igual a `posting_date`
And la factura se submittea sin error de validación ERPNext.

---

## Scenario: generación de deuda el día configurado del mes

Given hoy es `dia_generacion_deuda` del mes
And un socio elegible
When corre `generar_deuda_mensual_socio` con `reference_date = hoy`
Then `posting_date` = hoy
And `due_date` = `dia_primer_vencimiento` del mismo mes calendario (si aún no pasó).

---

## Próximo entregable relacionado

Consulta y liquidación manual por equipo y rango de fechas: `liquidacion_equipo_deuda_rango.md`.

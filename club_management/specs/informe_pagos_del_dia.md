# Spec: Informe de pagos del día (legado)

> **Estado:** absorbido por **Cobranza por fechas** (`informes_secretaria_menu.md`, `informe_rendicion_cobranza_secretaria.md`).  
> El Script Report `Pagos del dia` permanece como alias (mismo día = Desde=Hasta) pero **no** figura en el menú de Informes.

Cierre diario de cobranza — usar **Cobranza por fechas** con Desde = Hasta.

**Relacionado:** `informes_secretaria_menu.md`, `informe_rendicion_cobranza_secretaria.md`, `cobro_multi_factura_medios_mixtos.md`

---

## Scenario: no visible como ítem de menú

Given un usuario Secretaría en Desk
When abre la sección **Informes**
Then **no** ve **Pagos del dia** ni **Recaudacion por concepto**
And sí ve **Cobranza por fechas**, **Pagos por equipo** y **Deuda por actividad**.

---

## Scenario: header con total y medios

Given cobros del día en Efectivo y Transferencia
When Secretaría abre **Cobranza por fechas** (o el alias legado) filtrado por esa fecha
Then el encabezado (summary) muestra el **total recaudado**
And un total por cada **medio de pago**
And el summary **no** mezcla los totales por concepto (van al pie del listado).

---

## Scenario: listado ordenado por apellido y nombre

Given varios socios con cobros el mismo día
When se genera el informe
Then el listado detalla cada cobro/concepto (socio, concepto, medio, monto)
And está ordenado por **apellido** y luego **nombre** del socio.

---

## Scenario: totales finales por concepto

Given cobros del día aplicados a cuota social y arancel/actividad
When se genera el informe
Then al final del listado aparecen totales por concepto (p. ej. Cuota Social, Arancel actividad)
And la suma de conceptos coincide con el total del día (tolerancia de redondeo).

---

## Scenario: día sin cobros

Given fecha sin Payment Entry
When se abre el informe
Then listado vacío y totales en cero.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/informe_pagos_del_dia.md` |
| Servicio | `members/services/informe_pagos_del_dia.py` |
| Report | `members/report/pagos_del_dia/` |
| Nav | `CLUB_DESK_REPORTS`, sidebar Secretaría, `club_desk_navigation.js` |
| Tests | `members/tests/test_informe_pagos_del_dia.py` |

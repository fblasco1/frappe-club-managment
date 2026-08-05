# Spec: Informe de pagos del día

Cierre diario de cobranza en **Gestión de Socios → Informes**.

**Relacionado:** `cobro_multi_factura_medios_mixtos.md`, `secretaria_workspace_panel_kpis.md`, `mvp_operacion_secretaria_sin_pagos.md`

---

## Scenario: visible en Informes de Gestión de Socios

Given un usuario Secretaría en Desk
When abre la sección **Informes** del workspace Secretaría / Gestión de Socios
Then ve el enlace **Pagos del dia** junto a Deuda/Pagos por equipo y Deuda por actividad.

---

## Scenario: header con total y medios

Given cobros del día en Efectivo y Transferencia
When Secretaría abre **Pagos del dia** filtrado por esa fecha
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

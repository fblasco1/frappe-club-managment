# Spec: Pagos por equipo (aranceles y liquidación entrenador)

Secretaría consulta los **aranceles cobrados** de socios inscriptos en una
actividad / grupo / equipo en un rango de fechas, y la **liquidación del 80 %**
para el entrenador según la política configurada.

**Relacionado:** `liquidacion_equipo_deuda_rango.md`, `activities_jerarquia.md`

---

## Scenario: informe visible en Gestión de Actividades

Given Secretaría en el workspace **Gestión de Actividades**
When abre la sección **Informes**
Then ve el enlace **Pagos por equipo**
And al ejecutarlo navega al Script Report con filtros en cascada.

---

## Scenario: arancel pagado por socio del equipo

Given socio con inscripción activa en `Equipo Actividad` E
And el ítem de arancel de E es `ITEM-ARANCEL`
And una factura del mes con línea `ITEM-ARANCEL` totalmente cobrada
And otra factura del mes solo con cuota social cobrada
When Secretaría ejecuta **Pagos por equipo** filtrando por E en ese mes
Then la fila del socio muestra **solo** el importe cobrado de `ITEM-ARANCEL`
And **no** incluye la cuota social ni otros ítems.

---

## Scenario: liquidación entrenador con porcentaje configurable

Given `Equipo Actividad` E con `pct_liquidacion_entrenador` = 70
And socio con arancel pagado en rango = 10.000
When Secretaría ejecuta **Pagos por equipo** filtrando por E
Then `liquidacion_entrenador` = 7.000
And la columna **% entrenador** muestra 70.

---

## Scenario: porcentaje por defecto

Given equipo sin `pct_liquidacion_entrenador` definido
And `Club Settings.pct_liquidacion_entrenador_default` = 80
When se calcula la liquidación
Then se aplica el 80 % por defecto.

---

## Scenario: varios equipos en un mismo informe

Given entrenador a cargo de equipos E1 (70 %) y E2 (90 %)
And aranceles cobrados en el rango: 10.000 en E1 y 5.000 en E2
When Secretaría selecciona ambos equipos en **Pagos por equipo**
Then ve una fila agregada por socio con `pagos_en_rango` = 15.000
And `liquidacion_entrenador` = 7.000 + 4.500 = 11.500
And puede ver el total de liquidación en el pie del reporte.

---

## Scenario: liquidación entrenador al 80 % (default histórico)

Given socio con `arancel_pagado_en_rango` = 10.000 en el reporte
When Secretaría consulta la columna de liquidación
Then ve `liquidacion_entrenador` = 8.000 (80 % del arancel pagado).

---

## Scenario: cobro de cuota no cuenta como arancel

Given factura con cuota social y arancel en la misma factura
And un `Payment Entry` imputado al concepto «Cuota Social …»
When se calcula el arancel pagado del equipo
Then el importe de arancel cobrado es **0** (no se prorratea el pago de cuota)
And un excedente de mora sobre la cuota tampoco se cuenta como arancel.

---

## Scenario: cobro de tira imputado al arancel

Given la misma SI mixta
And un `Payment Entry` con referencia de informe «PRE-MINI A U9» / «MINI A U11» / «CADETES A U15» (tira Azul)
When se calcula el arancel pagado
Then se asigna el monto imputado a la línea de arancel (Minibasquet o Formativas Azul)
And no se reduce la línea de cuota social

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When ejecuta el reporte
Then recibe error de permisos.

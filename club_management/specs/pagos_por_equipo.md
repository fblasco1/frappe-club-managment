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

## Scenario: mora del arancel cuenta en Pagos por equipo

Given arancel de tira con tarifa $28.500
And cobro del informe «INFA A U13» por $31.350 (mora 10 % incluida) en agosto
When Secretaría ejecuta **Pagos por equipo** con rango agosto y fecha de **cobro**
Then `pagos_en_rango` del socio incluye **$31.350** (base + mora)
And no solo $28.500 de la línea de factura.

---

## Scenario: rango por fecha de cobro

Given factura de julio con arancel impago
And cobro del arancel en agosto según informe
When el reporte filtra agosto por fecha de **Payment Entry**
Then el arancel cobrado en agosto aparece en el reporte
And no queda excluido por `posting_date` de la factura de julio.

---

## Scenario: dos equipos con el mismo ítem y distinto porcentaje

Given socio con inscripciones activas en E1 (70 %) y E2 (90 %)
And ambos equipos resuelven al **mismo** `item_arancel`
When se calcula la liquidación del socio
Then el arancel cobrado se cuenta **una sola vez**
And se liquida con el % del equipo por el que entró al filtro (no se duplica el importe)
And si ambos equipos están en el filtro se usa el % de la inscripción con equipo asignado.

---

## Scenario: cantidad de pagos sin duplicar facturas

Given socio con dos inscripciones que comparten `item_arancel`
And una única factura con arancel cobrado en el rango
When se arma la fila del reporte
Then `cantidad_pagos` = 1 (facturas únicas, no suma por inscripción).

---

## Scenario: períodos cobrados visibles

Given cobros en agosto de aranceles con `periodo_cobro` 07/2026 y 08/2026
When Secretaría ejecuta el reporte con rango agosto
Then la fila del socio muestra `periodos_cobrados` = «07/2026, 08/2026»
And el total `pagos_en_rango` incluye ambos cobros.

---

## Scenario: conciliación contra el CSV consolidado

Given el CSV consolidado del mes con subtotal de aranceles deportivos
When se ejecuta `total_arancel_cobrado_en_rango(fecha_desde, fecha_hasta)` (sin filtro de equipo)
Then devuelve el total de arancel imputado por fecha de PE en el rango
And ese total se cruza contra el subtotal de aranceles del CSV en el
  verificador de cuadratura.

---

## Scenario: SUPERIOR B (básquet Amarillo) con factura histórica mal etiquetada

Given socio inscripto en `Basquet / Masculino / Amarillo / SUPERIOR`
And el ítem del equipo es `BASQUET / SUPERIOR / AMARILLO`
And el cobro del informe «SUPERIOR B» quedó facturado como `ICDPE-VOLEY-FEDERADO` (mapeo legacy erróneo)
And un `Payment Entry` en agosto imputa ese arancel
When Secretaría ejecuta **Pagos por equipo** filtrando ese equipo en agosto
Then la fila del socio muestra el importe cobrado del arancel Superior
And el concepto «SUPERIOR B» del informe resuelve a `BASQUET / SUPERIOR / AMARILLO`.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When ejecuta el reporte
Then recibe error de permisos.

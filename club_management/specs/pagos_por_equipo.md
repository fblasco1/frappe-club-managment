# Spec: Pagos por equipo (aranceles y liquidación entrenador)

Secretaría consulta los **aranceles cobrados** de socios inscriptos en una
actividad / grupo / equipo en un rango de fechas, y la **liquidación del 80 %**
para el entrenador según política del club.

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

## Scenario: liquidación entrenador al 80 %

Given socio con `arancel_pagado_en_rango` = 10.000 en el reporte
When Secretaría consulta la columna de liquidación
Then ve `liquidacion_entrenador` = 8.000 (80 % del arancel pagado).

---

## Scenario: pago parcial proporcional

Given factura con cuota social y arancel en la misma factura
And el socio pagó el 50 % del total de la factura
When se calcula el arancel pagado
Then se asigna el 50 % del monto de la línea de arancel (proporcional).

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When ejecuta el reporte
Then recibe error de permisos.

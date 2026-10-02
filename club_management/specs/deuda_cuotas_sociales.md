# Spec: Informe «Deuda cuotas sociales»

Script Report para Secretaría: cuánto adeuda cada socio **solo en concepto de cuota social**
(sin aranceles de actividades, gimnasio ni cuotas federativas).

---

## Scenario: una fila por socio con sus períodos adeudados

Given un socio con facturas de cuota social impagas de 09/2026 y 10/2026
When Secretaría ejecuta **Deuda cuotas sociales** sin filtros
Then ve una fila del socio con:
- períodos adeudados «09/2026, 10/2026» (ordenados cronológicamente)
- cantidad de períodos = 2
- deuda = suma de la cuota social impaga de ambos períodos

---

## Scenario: solo cuenta la línea de cuota social

Given una factura impaga con cuota social $36.000 y un arancel de actividad $20.000
When se ejecuta el informe
Then la deuda del socio es $36.000

---

## Scenario: cobros parciales imputados por concepto

Given una factura con cuota social y arancel
And un cobro que imputó el arancel completo (la cuota sigue impaga)
When se ejecuta el informe
Then la deuda muestra la cuota completa (imputación por línea, igual que el panel de cobro)

Given un cobro que pagó la cuota social completa
Then el período no aparece como adeudado

---

## Scenario: filtros

Given socios de distintas categorías y estados
When filtra por **período desde / hasta** (MM/YYYY), **categoría** o **estado**
Then solo ve las filas y períodos que cumplen el filtro
And los socios en estado «Baja» se incluyen solo si se filtra explícitamente por ese estado.

---

## Scenario: resumen

When ejecuta el informe
Then ve tarjetas con: socios con deuda, períodos adeudados y total adeudado.

---

## Scenario: permisos

Given usuario sin rol Secretaria ni System Manager
When intenta abrir el informe
Then Frappe lo rechaza (roles del Report).

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Report | `members/report/deuda_cuotas_sociales/` |
| Servicio | `members/services/deuda_cuotas_sociales.py` |
| Menú | sidebar Secretaría (`secretaria_workspace_sidebar.SECRETARIA_EXTRA_REPORTS`) |
| Tests | `members/tests/test_deuda_cuotas_sociales.py` |

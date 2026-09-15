# Spec: Deuda por actividad

Deuda de **aranceles** desglosada por actividad, con subtotales por **grupo/tira** y **equipo/categoría** en un rango de fechas.

**Relacionado:** `liquidacion_equipo_deuda_rango.md`, `informes_secretaria_menu.md`, `activities_jerarquia.md`

---

## Scenario: informe visible en menú

Given Secretaría
When abre el menú de informes
Then ve **Deuda por actividad** (junto a Cobranza por fechas y Pagos por equipo).

---

## Scenario: filtros

Given el Script Report **Deuda por actividad**
When Secretaría lo abre
Then tiene filtros `fecha_desde` y `fecha_hasta` (requeridos)
And opcionalmente `actividad` para acotar una sola actividad.

---

## Scenario: deuda de aranceles por equipo con subtotales

Given socios inscriptos en Basquet con equipos/grupos distintos y facturas de arancel pendientes en el rango
When Secretaría ejecuta **Deuda por actividad**
Then ve filas de detalle por **equipo/categoría** (con actividad y grupo)
And tras los equipos de un mismo grupo, una fila **Subtotal** del grupo
And tras los grupos de una actividad, una fila **Subtotal** de la actividad
And al final una fila **Total**
And los montos son **solo deuda de arancel** (no cuota social genérica del club).

---

## Scenario: sin deudores de arancel

Given el rango sin aranceles impagos en inscripciones activas
When se ejecuta el reporte
Then la grilla queda vacía (sin filas de total huérfanas) o solo indica ausencia de datos según implementación testeada.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | `specs/deuda_por_actividad.md` |
| Servicio | `members/services/liquidacion_equipo.py` (`get_deuda_por_actividad_*`) |
| Report | `members/report/deuda_por_actividad/` |
| Tests | `members/tests/test_liquidacion_equipo.py` |

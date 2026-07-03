# Spec: Deuda por actividad

Resumen de deuda pendiente desglosada por **actividad deportiva**.

**Relacionado:** `liquidacion_equipo_deuda_rango.md`, `activities_jerarquia.md`

---

## Scenario: informe visible en Secretaría

Given Secretaría en workspace **Secretaría** o **Gestión de Actividades**
When abre **Deuda por actividad**
Then ve un Script Report con filtro de rango de fechas
And una fila por cada actividad con inscripciones activas.

---

## Scenario: desglose por actividad

Given socios con facturas pendientes en el rango
When Secretaría ejecuta el reporte
Then cada fila muestra:
  **deuda_cuota_social**, **deuda_arancel**, **deuda_cuota_federativa** y **deuda_total**
  de los socios inscriptos en esa actividad
And **promedio_meses_deuda** = media de `cantidad_meses_deuda` de socios deudores (> 0) de la actividad
And **socios_deudores** = cantidad de socios con deuda > 0 en el rango.

---

## Scenario: fila de total

Given el reporte con varias actividades
When Secretaría lo ejecuta
Then ve una fila **Total** con la suma de todas las columnas monetarias
And el promedio de meses es ponderado por socios deudores.

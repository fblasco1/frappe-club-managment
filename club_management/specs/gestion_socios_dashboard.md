# Spec: Dashboard Gestión de Socios (workspace Secretaría)

Panel Desk para rol `Secretaria`: responde al instante cuántos somos, quiénes
entraron/se fueron en el mes, quiénes están en mora (`estado = Moroso`), tendencia de
recaudación y medios de pago.

**Relacionado:** `secretaria_workspace_panel_kpis.md`, `secretaria_workspace_listas.md`

---

## Scenario: total de socios activos segmentado

Given existen socios con `estado != Baja` en distintas categorías
When Secretaria consulta el dashboard
Then ve el **total** de socios activos (no dados de baja) en la card KPI
And el desglose por segmento (**Mayores**, **Menores**, **Adherentes**, **Jubilados**)
  se muestra en un **gráfico de barras** en la fila inferior, junto al gráfico de medios de pago.

---

## Scenario: tasa de cobrabilidad del mes

Given facturas del período corriente (`periodo_cobro = MM/YYYY`) con líneas de cuota social
When Secretaria consulta el dashboard
Then ve el **% recaudado** = monto cobrado de cuotas / monto emitido × 100
And debajo del porcentaje ve **Total cobrado** y **Saldo por cobrar** del mes (emitido − cobrado)
And si no hay deuda emitida en el mes, muestra 0 %.

---

## Scenario: altas vs bajas del mes en curso

Given socios con `fecha_alta` en el mes de referencia
And socios dados de baja (`estado = Baja`) con `ultimo_cambio_estado_en` en ese mes
When Secretaria consulta el dashboard
Then ve un ratio **+altas / -bajas** del mes en curso (ej. `+2 / -1`).

---

## Scenario: socios en mora

Given socios con `estado = Moroso` (marcados tras segundo vencimiento o por Secretaría)
And socios activos con deuda del mes corriente aún no vencida
When Secretaria consulta el dashboard
Then la card **Socios en mora** cuenta solo los de `estado = Moroso`
And no incluye activos que solo deben el período en curso
And muestra el **monto total adeudado** (suma de `saldo_deuda` de morosos)
And **Ver más** abre `Socio` filtrado a `Moroso`.

---

## Scenario: gráfico tendencia de recaudación

Given facturación y cobros de cuotas sociales en un mes calendario
When Secretaria consulta el dashboard
Then ve un gráfico de línea con **recaudado** y **emitido** por **día del mes** (1 … último día)
And puede elegir el **mes** a visualizar con un selector (por defecto el mes en curso)
And al cambiar el mes solo se actualiza el gráfico de tendencia (sin recargar todo el panel)
And el resto de KPIs del panel siguen referidos al mes en curso salvo el gráfico de tendencia.

---

## Scenario: gráfico distribución por medio de pago

Given `Payment Entry` submitted del mes contra facturas de socios
When Secretaria consulta el dashboard
Then ve un gráfico de torta agrupado en:
**Efectivo** (`Cash`, `Cheque`),
**Tarjeta** (`Credit Card`, `Bank Draft`),
**Transferencia** (`Wire Transfer`),
**Otro** (demás modos).

---

## Scenario: tabla solicitudes pendientes

Given `Solicitud Asociacion` con `workflow_state` en `Pendiente` o `Requiere Corrección`
When Secretaria consulta el dashboard
Then ve una tabla con las más antiguas primero (máx. 5)
And cada fila muestra nombre, DNI y fecha
And al hacer clic en una fila abre el formulario Desk de esa solicitud
And **Ver más** abre la lista filtrada a esos estados.

---

## Scenario: acciones rápidas

Given Secretaria en el dashboard
When usa las acciones rápidas
Then puede abrir **Nueva alta de socio** (flujo guiado existente)
And **Emitir cupón / Registrar cobro** abre socios con deuda pendiente
And **Enviar recordatorio masivo** aparece deshabilitado (futuro).

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When intenta consultar el endpoint del dashboard
Then recibe error de permisos.

# Spec: Dashboard Gestión de Socios (workspace Secretaría)

Panel Desk para rol `Secretaria`: responde al instante cuántos somos, quiénes
entraron/se fueron en el mes, quiénes deben dinero (1–3 meses), tendencia de
recaudación y medios de pago.

**Relacionado:** `secretaria_workspace_panel_kpis.md`, `secretaria_workspace_listas.md`

---

## Scenario: total de socios activos segmentado

Given existen socios con `estado != Baja` en distintas categorías
When Secretaria consulta el dashboard
Then ve el **total** de socios activos (no dados de baja)
And un desglose sutil: **Mayores** (`Activo`, `2° Hermano`, `3° Hermano`),
**Menores** (`Menor`), **Adherentes** (`Adherente`), **Jubilados** (`Jubilado`, `Vitalicio`).

---

## Scenario: tasa de cobrabilidad del mes

Given facturas del período corriente (`periodo_cobro = MM/YYYY`) con líneas de cuota social
When Secretaria consulta el dashboard
Then ve el **% recaudado** = monto cobrado de cuotas / monto emitido × 100
And si no hay deuda emitida en el mes, muestra 0 %.

---

## Scenario: altas vs bajas del mes en curso

Given socios con `fecha_alta` en el mes de referencia
And socios dados de baja (`estado = Baja`) con `ultimo_cambio_estado_en` en ese mes
When Secretaria consulta el dashboard
Then ve un ratio **+altas / -bajas** del mes en curso (ej. `+2 / -1`).

---

## Scenario: socios en mora de 1 a 3 meses

Given socios con facturas mensuales impagas en 1, 2 o 3 períodos distintos (sin recargo)
When Secretaria consulta el dashboard
Then ve la **cantidad** de esos socios
And el **monto total** (`saldo_deuda` sumado de ellos)
And **Ver más** abre `Socio` filtrado a `Moroso` o con deuda.

---

## Scenario: gráfico tendencia de recaudación

Given histórico de facturación mensual de cuotas (últimos 12 meses)
When Secretaria consulta el dashboard
Then ve un gráfico de línea con **recaudado real** y **emitido proyectado** por mes.

---

## Scenario: gráfico distribución por medio de pago

Given `Payment Entry` submitted del mes contra facturas de socios
When Secretaria consulta el dashboard
Then ve un gráfico de torta agrupado en:
**Débito automático** (`Credit Card`, `Bank Draft`),
**Efectivo / POS** (`Cash`, `Cheque`),
**Transferencia** (`Wire Transfer`).

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

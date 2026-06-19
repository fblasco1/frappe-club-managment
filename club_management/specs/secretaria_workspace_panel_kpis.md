# Spec: Panel KPI del workspace Secretaría

Panel custom en Desk (rol `Secretaria`): botón de alta, métricas del mes y cuotas
editables. Reemplaza el encabezado «Panel Secretaría» y las number cards nativas.

**Relacionado:** `secretaria_workspace_listas.md`, `cobranza_periodica_mensual.md`

---

## Scenario: encabezado operativo sin título estático

Given Secretaria abre el workspace **Secretaría**
When carga el panel custom
Then no ve el encabezado «Panel Secretaría»
And ve el botón **Nuevo socio** (alta guiada) como acción principal.

---

## Scenario: tarjeta socios en mora

Given existen socios con `estado = Moroso`
When Secretaria consulta el panel
Then ve una card **Socios en mora** con la cantidad total de morosos
And debajo ve el **monto total adeudado** (suma de `saldo_deuda` de esos socios)
And un enlace **Ver más** abre la lista de `Socio` filtrada a `Moroso`.

---

## Scenario: tarjeta cantidad de socios con variación mensual

Given existen socios con `estado != Baja`
When Secretaria consulta el panel
Then ve la **cantidad total** de socios
And un indicador de variación respecto al cierre del mes anterior (delta numérico)
And **Ver más** abre el listado general de `Socio` (excluyendo `Baja`).

---

## Scenario: porcentaje cuotas sociales recaudadas en el mes

Given facturas mensuales del período corriente (`periodo_cobro = MM/YYYY`) con líneas de cuota social
When Secretaria consulta el panel
Then ve el **% recaudado** = monto cobrado de cuotas / monto emitido × 100
And si no hay deuda emitida en el mes, muestra 0 %.

---

## Scenario: porcentaje aranceles recaudados con detalle por actividad

Given facturas del período con líneas de arancel de inscripciones activas
When Secretaria consulta el panel
Then ve el **% recaudado global** de aranceles del mes
And puede desplegar un detalle con **% por actividad** (agrupado por `Inscripcion Actividad.actividad`).

---

## Scenario: cuotas sociales colapsables

Given `Club Settings` con filas en `cuotas_categoria`
When Secretaria ve la sección de cuotas en el panel
Then la tabla está **colapsada** por defecto
And puede expandirla para editar montos y guardar.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When intenta consultar el endpoint del panel
Then recibe error de permisos.

# Spec: Panel KPI del workspace Secretaría

Panel custom en Desk (rol `Secretaria`): botón de alta, métricas del mes y cuotas
editables. Reemplaza el encabezado «Panel Secretaría» y las number cards nativas.

**Relacionado:** `secretaria_workspace_listas.md`, `cobranza_periodica_mensual.md`

---

## Scenario: encabezado operativo sin título estático

Given Secretaria abre el workspace **Secretaría** (label visible **Socios**)
When carga el panel custom
Then no ve el encabezado «Panel Secretaría»
And ve el botón **+ Nuevo Socio** (alta guiada) como acción principal
And no ve «Emitir cupón / Registrar cobro» ni «Registrar Nuevo Gasto / Comprobante».

---

## Scenario: tarjeta socios en mora

Given existen socios con `estado = Moroso`
When Secretaria consulta el panel
Then ve una card **Socios en mora** con la cantidad total de morosos
And debajo ve el **monto total adeudado** (suma de `saldo_deuda` de esos socios)
And ve el desglose de clasificación de mora (**1–3 meses** / **4+ meses**) con cantidad y monto
And un enlace **Ver más** abre la lista de `Socio` filtrada a `Moroso`.

---

## Scenario: tarjeta cantidad de socios con variación mensual

Given existen socios con `estado != Baja`
When Secretaria consulta el panel
Then ve la **cantidad total** de socios
And un indicador de variación respecto al cierre del mes anterior (delta numérico)
And **Ver más** abre el listado general de `Socio` (excluyendo `Baja`).

---

## Scenario: tasa de cobrabilidad con dropdown de vista y subfiltro

Given facturas del período corriente con cuotas, aranceles y otros conceptos
When Secretaria abre el panel
Then ve **una card** «Tasa de cobrabilidad del mes» con un **dropdown de vista** (Total, Cuotas sociales, Aranceles, CTO COMP, Federativas, Otros)
And al elegir **Cuotas sociales** puede filtrar por **categoría** de cuota (Activo, Menor, …)
And al elegir **Aranceles** puede filtrar por **actividad**
And al elegir **Otros** / **CTO COMP** / **Federativas** puede filtrar por **concepto informe**
And la card muestra % recaudado, total cobrado y saldo por cobrar del corte seleccionado
And «Ver informe» abre el reporte con filtros acordes a la vista
And **no** hay cards separadas duplicando la misma información.

---

## Scenario: elegir el período de la tasa de cobrabilidad

Given la card «Tasa de cobrabilidad del mes» muestra por defecto el período corriente (`MM/YYYY`)
When Secretaria elige otro **mes** en el selector de período de la card
Then la card se recalcula para ese `periodo_cobro` (% recaudado, total cobrado, saldo por cobrar, vistas y detalle)
And el encabezado muestra el período elegido
And «Ver informe» abre el reporte con fechas y `periodo_cobro` del mes elegido
And el resto del panel (KPIs de socios, gráficos) **no** se recarga.

Given un usuario sin rol `Secretaria` ni `System Manager`
When consulta la cobrabilidad de un período por API
Then recibe `PermissionError`.

---

## Scenario: porcentaje cuotas sociales recaudadas en el mes

Given facturas mensuales del período corriente (`periodo_cobro = MM/YYYY`) con líneas de cuota social
When Secretaria elige vista **Cuotas sociales** en la card de cobrabilidad
Then ve el **% recaudado** = monto cobrado de cuotas / monto emitido × 100
And debajo del porcentaje ve **Total cobrado** y **Saldo por cobrar** del mes (o de la categoría filtrada)
And si no hay deuda emitida en el mes, muestra 0 %.

Given líneas con el ítem legado `CLUB-Cuota-Social-Base` (facturas emitidas antes de la consolidación)
When se calcula la vista **Cuotas sociales**
Then esas líneas cuentan como cuota social por su código, aunque la descripción o el grupo del ítem no lo indiquen.

---

## Scenario: porcentaje aranceles recaudados con detalle por actividad

Given facturas del período con líneas de arancel de inscripciones activas
When Secretaria elige vista **Aranceles** en la card de cobrabilidad
Then puede seleccionar una **actividad** en el subfiltro
And ve el **% recaudado** de esa actividad (o global si «Todas»).

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

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
And ve el desglose de clasificación de mora (**1 mes** / **2 meses** / **3 meses** / **+4 meses**) con cantidad y monto
And un enlace **Ver más** abre la lista de `Socio` filtrada a `Moroso`.

---

## Scenario: clasificación de mora por meses vencidos

Given un socio (`estado != Baja`) con facturas impagas (`outstanding_amount > 0`)
And cada factura tiene `periodo_cobro` `MM/YYYY` (los sufijos `-MORA` / `-REC` cuentan como su mes base)
When se calcula la clasificación a la fecha de hoy
Then un mes cuenta como **vencido** solo si hoy es posterior a su **2.º vencimiento** (`Club Settings.dia_segundo_vencimiento`)
And el socio se ubica por **cantidad de meses vencidos impagos** distintos: **1 mes**, **2 meses**, **3 meses** o **+4 meses**
And un socio que solo debe el mes en curso antes del 2.º vencimiento **no** aparece en la clasificación
And cada tramo muestra cantidad de socios y monto (`saldo_deuda` sumado).

---

## Scenario: tarjeta cantidad de socios con variación mensual

Given existen socios con `estado != Baja`
When Secretaria consulta el panel
Then ve la **cantidad total** de socios
And un indicador de variación respecto al cierre del mes anterior (delta numérico)
And el desglose por categoría **Activo**, **Menor**, **Adherente**, **Vitalicio** y **Jubilado** con cantidad y % del total
And `2° Hermano` / `3° Hermano` cuentan como **Menor** o **Activo** según la edad
And **Ver más** abre el listado general de `Socio` (excluyendo `Baja`).

---

## Scenario: altas vs bajas con actividades de mayor movimiento

Given inscripciones a actividades dadas de alta (`fecha_inscripcion`) o de baja (cambio de `estado` a `Baja` registrado en el historial de versiones) en los **últimos 30 días**
When Secretaria consulta el panel
Then la card **Altas vs bajas** sigue mostrando `+altas / -bajas` de socios del mes
And debajo lista las **3 actividades** con más movimientos (altas + bajas de inscripciones) en los últimos 30 días
And cada actividad muestra sus altas y bajas por separado
And si no hubo movimientos, muestra «Sin movimientos en actividades».

---

## Scenario: resumen y corte al día en la tendencia de recaudación

Given el gráfico **Tendencia de recaudación** de un mes y vista elegidos
When Secretaria lo consulta
Then arriba del gráfico ve un resumen: **Emitido**, **Recaudado**, **% cobrado** y **Saldo** del mes y vista
And si el mes elegido es el **mes en curso**, la serie se dibuja solo hasta el día de hoy (sin días futuros planos)
And los meses pasados se dibujan completos.

---

## Scenario: filtros del panel con estilo del portal

Given los filtros de la card de cobrabilidad y del gráfico de tendencia
When Secretaria los usa
Then cada filtro tiene etiqueta en mayúsculas y controles del mismo alto con el estilo del portal (`club-portal-field`)
And la **vista** del gráfico de tendencia se elige con botones tipo pill (una opción activa resaltada con el color del área).

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

# Spec: Deuda por actividad

Deuda de **aranceles** desglosada por actividad, con subtotales por **grupo/tira** y **equipo/categoría**, y detalle mínimo por **socio deudor**, en un rango de fechas.

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

## Scenario: árbol colapsable padre → hijos

Given socios inscriptos en Basquet con equipos/grupos distintos y facturas de arancel pendientes en el rango
When Secretaría ejecuta **Deuda por actividad**
Then las filas siguen orden **padre primero, hijos debajo** (compatible con el treeView de Frappe DataTable)
And la primera fila es **Total** (`indent` 0)
And bajo el Total, cada **actividad** aparece como subtotal (`indent` 1) **antes** de sus grupos
And bajo cada actividad, cada **grupo/tira** aparece como subtotal (`indent` 2) **antes** de sus equipos
And bajo cada grupo, cada **equipo/categoría** aparece (`indent` 3) **antes** de sus socios
And al expandir un nivel se ven solo las subcategorías / detalle inmediato de ese padre
And los montos son **solo deuda de arancel** (no cuota social genérica del club).

---

## Scenario: detalle mínimo por socio deudor

Given un equipo con dos socios con deuda de arancel en el rango
When se ejecuta el reporte
Then bajo la fila del equipo hay una fila por **socio deudor** (`indent` 4)
And cada fila de socio muestra el nombre del socio y su **deuda de arancel** individual
And la fila del equipo acumula la suma de esas deudas y el conteo de socios deudores
And los subtotales de grupo, actividad y Total reflejan la misma agregación.

---

## Scenario: socios deudores con porcentaje sobre el padrón de la categoría

Given en un equipo hay 2 socios con inscripción activa y solo 1 con deuda de arancel en el rango
When se ejecuta el reporte
Then la columna **Socios deudores** en filas de agregación (Total, actividad, grupo, equipo) muestra `N (P%)`
And `N` es la cantidad de socios deudores de arancel en esa categoría
And `P` es el porcentaje entero de `N` sobre el **total de socios con inscripción activa** (no Baja) en esa misma categoría de agregación
And en filas hoja de socio la columna muestra `1` (sin porcentaje).

---

## Scenario: sin equipo/categoría se omite ese nivel

Given socios con deuda de arancel en un grupo **sin** `equipo_actividad`
When se ejecuta el reporte
Then **no** aparece una fila placeholder «Sin equipo / categoría»
And los socios deudores se listan **directamente bajo el subtotal del grupo** (`indent` 3)
And si el mismo grupo también tiene equipos con nombre, esos equipos siguen en `indent` 3 con sus socios en `indent` 4 (hermanos del nivel equipo).

---

## Scenario: PDF en A4 vertical legible

Given Secretaría genera el PDF del informe **Deuda por actividad**
When abre el diálogo de PDF / impresión
Then la orientación por defecto es **Portrait** (vertical)
And el tamaño de página es **A4**
And el PDF usa la plantilla del reporte (no la grilla Desk completa)
And muestra solo **Nivel / Socio**, **Deuda aranceles** y **Socios deudores** (sin columnas redundantes de actividad/grupo/equipo)
And el nombre del socio aparece completo (con N° de socio) sin cortarse por falta de ancho
And se incluyen **todas** las filas del árbol (no solo las visibles/expandidas en pantalla).

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
| Report | `members/report/deuda_por_actividad/` (`.py` / `.js` / `.html` PDF) |
| Tests | `members/tests/test_liquidacion_equipo.py` |

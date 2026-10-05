# Spec: Deuda por actividad

Deuda de cada actividad desagregada en **cuota social** y **arancel**, con subtotales por
**grupo/tira** y **equipo/categoría**, y detalle por **socio deudor**, en un rango de fechas.
Los socios que hacen **más de una actividad** se agregan aparte en **Multiactividad** para no
duplicar su cuota social.

**Relacionado:** `liquidacion_equipo_deuda_rango.md`, `informes_secretaria_menu.md`, `activities_jerarquia.md`,
`deuda_cuotas_sociales.md`

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

## Scenario: columnas de deuda

Given cualquier fila del informe
Then muestra **Cuota social** (deuda de cuota social impaga), **Arancel** (deuda de arancel de
la(s) inscripción(es)) y **Total** (= cuota social + arancel)
And la cuota social se reconoce con el ítem de Club Settings y el ítem legado
`CLUB-Cuota-Social-Base`
And las cuotas federativas y otros cargos **no** suman en estas columnas.

---

## Scenario: árbol colapsable padre → hijos

Given socios inscriptos en Basquet con equipos/grupos distintos y facturas pendientes en el rango
When Secretaría ejecuta **Deuda por actividad**
Then las filas siguen orden **padre primero, hijos debajo** (compatible con el treeView de Frappe DataTable)
And la primera fila es **Total** (`indent` 0)
And bajo el Total, cada **actividad** aparece como subtotal (`indent` 1) **antes** de sus grupos
And bajo cada actividad, cada **grupo/tira** aparece como subtotal (`indent` 2) **antes** de sus equipos
And bajo cada grupo, cada **equipo/categoría** aparece (`indent` 3) **antes** de sus socios
And al expandir un nivel se ven solo las subcategorías / detalle inmediato de ese padre.

---

## Scenario: expandir / colapsar con clic en la fila padre

Given el informe **Deuda por actividad** renderizado en Desk con el árbol colapsado en nivel 1
When el usuario hace clic en la flecha **o en el texto** de una fila padre (p. ej. "Subtotal Basquet")
Then la fila se expande mostrando sus hijos inmediatos
And un segundo clic en la misma fila la colapsa
And las filas hoja (socios) no reaccionan al clic
And la flecha tiene un área de clic ampliada (no solo el ícono de 16 px).

---

## Scenario: socio de una sola actividad

Given un socio con inscripción activa solo en Basquet
And factura pendiente en el rango con cuota social $10.000 y arancel de Basquet $5.000
When se ejecuta el reporte
Then el socio figura bajo Basquet (en su grupo/equipo) con cuota social 10.000, arancel 5.000 y total 15.000
And la actividad, el grupo, el equipo y el Total acumulan esos montos.

Given un socio de una sola actividad con dos inscripciones en ella (dos grupos/equipos)
Then su cuota social se cuenta **una sola vez** (en la primera inscripción)
And un arancel con el mismo ítem en ambas inscripciones se cuenta una sola vez.

---

## Scenario: socio en más de una actividad → Multiactividad

Given un socio con inscripciones activas en Basquet y en Patín
And deuda en el rango: cuota social $10.000, arancel Basquet $5.000 y arancel Patín $3.000
When se ejecuta el reporte
Then el socio **no** figura bajo Basquet ni bajo Patín
And aparece bajo el agregado **Multiactividad** (`indent` 1, después de las actividades) con
cuota social 10.000, arancel 8.000 y total 18.000
And la columna **Actividades** de su fila lista ambas actividades
And el Total incluye esos montos una sola vez.

Given el filtro `actividad` = Basquet
Then Multiactividad solo incluye socios que, entre sus actividades, tienen Basquet.

---

## Scenario: socios sin actividad con deuda de cuota social

Given un socio (no Baja) sin inscripciones activas y con cuota social impaga en el rango
When se ejecuta el reporte **sin** filtro de actividad
Then aparece bajo el agregado **Sin actividad** (`indent` 1, al final) con su cuota social
And el Total la incluye.

Given se filtra por una actividad
Then el agregado **Sin actividad** no aparece.

---

## Scenario: socios deudores con porcentaje sobre el padrón de la categoría

Given en un equipo hay 2 socios con inscripción activa y solo 1 con deuda en el rango
When se ejecuta el reporte
Then la columna **Socios deudores** en filas de agregación muestra `N (P%)`
And `N` es la cantidad de socios con deuda (cuota social o arancel) en esa agregación
And `P` es el porcentaje entero de `N` sobre el **total de socios con inscripción activa** (no Baja)
de esa agregación (en Multiactividad: socios multiactividad del alcance)
And en **Sin actividad** se muestra solo `N`
And en el **Total** el padrón incluye además a los socios (no Baja) sin actividad cuando no hay filtro de actividad
And en filas hoja de socio la columna muestra `1` (sin porcentaje).

---

## Scenario: sin equipo/categoría se omite ese nivel

Given socios con deuda en un grupo **sin** `equipo_actividad`
When se ejecuta el reporte
Then **no** aparece una fila placeholder «Sin equipo / categoría»
And los socios deudores se listan **directamente bajo el subtotal del grupo** (`indent` 3)
And si el mismo grupo también tiene equipos con nombre, esos equipos siguen en `indent` 3 con sus socios en `indent` 4 (hermanos del nivel equipo).

---

## Scenario: socios en Baja

Given un socio en estado `Baja`
Then no figura en el informe (igual que antes; su deuda se consulta en «Deuda cuotas sociales» filtrando Baja).

---

## Scenario: PDF en A4 vertical legible

Given Secretaría genera el PDF del informe **Deuda por actividad**
When abre el diálogo de PDF / impresión
Then la orientación por defecto es **Portrait** (vertical)
And el tamaño de página es **A4**
And el PDF usa la plantilla del reporte (no la grilla Desk completa)
And muestra **Nivel / Socio**, **Cuota social**, **Arancel**, **Total** y **Socios deudores** (sin columnas redundantes de actividad/grupo/equipo)
And el nombre del socio aparece completo (con N° de socio) sin cortarse por falta de ancho
And se incluyen **todas** las filas del árbol (no solo las visibles/expandidas en pantalla).

---

## Scenario: sin deudores

Given el rango sin cuota social ni aranceles impagos
When se ejecuta el reporte
Then la grilla queda vacía (sin filas de total huérfanas).

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | `specs/deuda_por_actividad.md` |
| Servicio | `members/services/liquidacion_equipo.py` (`get_deuda_por_actividad_*`) |
| Report | `members/report/deuda_por_actividad/` (`.py` / `.js` / `.html` PDF) |
| Tests | `members/tests/test_liquidacion_equipo.py` |

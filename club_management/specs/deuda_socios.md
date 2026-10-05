# Spec: Informe «Deuda de socios»

Script Report único para Secretaría que **reemplaza en el menú** a «Deuda cuotas sociales» y
«Deuda por actividad» (ambos siguen existiendo por URL). Muestra cuánto adeuda cada socio de
**cuota social** y de **arancel** de sus actividades, con los filtros de «Deuda cuotas sociales».

---

## Qué cuenta como deuda

Given facturas de venta enviadas (`docstatus` 1), no notas de crédito, con saldo pendiente
When se ejecuta el informe
Then la **cuota social** es el saldo de las líneas con el ítem de Club Settings o el ítem legado
`CLUB-Cuota-Social-Base`
And el **arancel** es el saldo de las líneas cuyo ítem es el arancel de alguna inscripción del socio
(equipo → grupo → actividad, con sus ítems equivalentes)
And las cuotas federativas y otros cargos **no** suman
And si la factura tiene cobros parciales, el saldo se imputa por línea (igual que el panel de cobro).

---

## Scenario: filtros (iguales a Deuda cuotas sociales + actividad)

Given socios de distintas categorías, estados y actividades
When filtra por **período desde / hasta** (MM/AAAA, sobre el período de cobro de la factura),
**categoría**, **estado**, **socio**, **actividad**, **grupo / tira** o **equipo / categoría**
Then solo ve socios y períodos que cumplen todos los filtros
And un período con formato inválido muestra un error claro
And el selector de grupo solo ofrece grupos de la actividad elegida, y el de equipo solo equipos del grupo elegido.

Given un socio en estado «Baja» con deuda
When no se filtra por estado
Then no aparece
When se filtra por estado «Baja»
Then aparece, ubicado en las actividades de sus inscripciones (aunque estén dadas de baja).

---

## Scenario: concepto

Given un socio que debe cuota social $10.000 y arancel $5.000 del mismo período
When el filtro **Concepto** es «Todo» (por defecto)
Then ve columnas Cuota social $10.000, Arancel $5.000 y Total $15.000
When el concepto es «Solo cuota social»
Then solo ve la columna Cuota social con $10.000
And los socios que solo deben arancel no aparecen
When el concepto es «Solo arancel»
Then solo ve la columna Arancel con $5.000
And los socios que solo deben cuota social no aparecen.

---

## Scenario: vista «Lista de socios»

Given socios con deuda
When elige **Vista = Lista de socios**
Then ve **una fila por socio** con: socio, apellido y nombre, categoría, estado, teléfono,
actividades, períodos adeudados (ordenados cronológicamente), cantidad de períodos y montos
And las filas se ordenan por más períodos, luego mayor deuda, luego nombre.

---

## Scenario: vista «Por actividad» (árbol)

Given socios inscriptos en distintas actividades / grupos / equipos con deuda
When elige **Vista = Por actividad** (por defecto)
Then la primera fila es **Total** (`indent` 0)
And debajo, cada actividad es un subtotal (`indent` 1) → grupo (`indent` 2) → equipo (`indent` 3) → socios
And si la inscripción no tiene equipo, el socio cuelga del grupo (`indent` 3)
And cada fila de socio muestra estado, teléfono y períodos adeudados
And cada subtotal muestra «Socios deudores» como «N (P%)» sobre el padrón de ese nivel
(socios que cumplen los filtros de socio, con deuda o sin ella).

Given un socio inscripto en **más de una actividad**
Then aparece una sola vez, bajo **Multiactividad** (`indent` 1), con la lista de sus actividades
And no se suma en el subtotal de cada actividad.

Given un socio con dos inscripciones en la misma actividad
Then la cuota social se cuenta **una sola vez** (en la primera inscripción).

Given un socio sin inscripciones que debe cuota social
When no hay filtro de actividad / grupo / equipo
Then aparece bajo **Sin actividad** (`indent` 1), al final.

---

## Scenario: resumen

When ejecuta el informe
Then ve tarjetas con: socios con deuda, períodos adeudados y los montos del concepto elegido
(cuota social, arancel y total adeudado con «Todo»).

---

## Scenario: rendimiento

Given los datos de producción
When se ejecuta sin filtros
Then responde en menos de 15 segundos (umbral en que Frappe pasa el informe a «preparado»)
And no consulta facturas socio por socio.

---

## Scenario: permisos

Given un usuario sin rol Secretaria ni System Manager
When intenta abrir el informe
Then Frappe lo rechaza (roles del Report).

---

## Scenario: menú

When Secretaría abre la sidebar de Socios o de Actividades
Then ve «Deuda de socios»
And ya no ve «Deuda cuotas sociales» ni «Deuda por actividad».

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Report | `members/report/deuda_de_socios/` (json, py, js, html A4) |
| Servicio | `members/services/deuda_socios.py` |
| Menú | `secretaria_workspace_sidebar`, `actividades_workspace_sidebar`, `inicio_workspace.CLUB_DESK_REPORTS`, boots JS |
| Tests | `members/tests/test_deuda_socios.py` |

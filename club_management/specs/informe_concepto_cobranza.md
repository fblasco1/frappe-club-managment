# Spec: Cruce concepto informe ↔ ítem / línea de factura (cobranza masiva)

El informe Excel agrupa cobros por **concepto** (p. ej. «Adicional Basquet Escuelita»,
«C FED U15/U17 MASC»). En ERPNext la deuda del mes suele estar en **Sales Invoice**
con una o más líneas (cuota + arancel + cargos extra).

La carga masiva debe imputar **solo la línea** que corresponde al concepto del
informe, aplicando mora **solo** si el ítem es cuota social o arancel de actividad
(spec `recargos_mora_dos_tramos.md`: +10 % post día 10, +15 % post día 20).

Federativas, cargos extra (p. ej. expediente FEBAMBA) y similares **no** llevan mora.

---

## Scenario: adicional arancel en factura multi-línea

Given una SI impaga del período con cuota social + arancel escuelita básquet
And una fila del informe «Adicional Basquet Escuelita» por el monto del arancel
When `fecha_pago` es anterior al día 11 del mes del período
Then el monto exigido es el del arancel (línea `ICDPE-BASQUET-ESCUELITA`)
And al aplicar se crea un `Payment Entry` parcial contra esa SI por ese importe
And no exige el total cuota+arancel.

---

## Scenario: mora solo sobre la línea cruzada

Given la misma SI y concepto de arancel
And `fecha_pago` el día 15 del mes del período (post 1.er vencimiento)
When se calcula el monto exigido
Then aplica +10 % **solo** sobre el valor vigente de esa línea de arancel
And no suma mora de la cuota social de la misma factura.

---

## Scenario: cuota federativa sin mora

Given una SI impaga con ítem `ICDPE-CUOTA-FEDERATIVA-voley`
And fila del informe «CUOTA FEDER VOLEY» o «C FED …» de vóley
When `fecha_pago` es posterior al día 20
Then el monto exigido es el outstanding de esa línea / factura sin recargo
And se puede imputar el cobro.

---

## Scenario: cuota complementaria por descripción de cargo extra

Given una SI impaga con línea `ICDPE-CARGO-VARIOS` y descripción
«CTO COMP BASQ TIRA A/B/FLEX (08/2026)»
And una fila del informe «CTO COMP BASQ TIRA A/B/FLEX» por $6.000
When se procesa con `fecha_pago` posterior al día 20
Then el monto exigido es $6.000 (sin mora)
And se imputa cobro parcial contra esa SI.

---

## Scenario: variantes de título CTO COMP (fuzzy)

Given una SI impaga con descripción «CTO COMP BASQUE TIRA A/B/FLEX (08/2026)»
And fila del informe «CTO COMP BASQ TIRA A/B/FLEX»
When se busca la línea a imputar
Then `cuotas_complementarias_equivalentes` devuelve True
And se imputa el cobro.

Given la misma SI ya saldada (outstanding 0)
And fila del informe con concepto equivalente
When falla el match por impagas
Then la inconsistencia se clasifica como `ya_saldada`, no `sin_factura_impaga`.

---

Given cargo extra «EXPEDIENTE FEBAMBA» (total $250.000, cuotas de $83.333)
When el informe trae una fila «EXPEDIENTE FEBAMBA» por $83.333
Then se busca SI impaga cuya línea coincida con ese cargo (por ítem o descripción)
And el monto exigido es $83.333 (sin mora).

---

## Mapeos informe → ítem (Secretaría)

| Concepto informe | Ítem / destino |
|------------------|----------------|
| EXPEDIENTE FEBAMBA | Cargo extra / multa (`ICDPE-MULTA` o SI con texto FEBAMBA; cuotas $83.333) |
| CUOTA FEDER VOLEY | `ICDPE-CUOTA-FEDERATIVA-voley` |
| C.FED / C FED U21 MASC, U15/U17 MASC, U13 MASC, U9/U11 MASC, U21 FLEX, U15/U17 FLEX, U13 FLEX, SUPERIOR FLEX | `ICDPE-CUOTA-FEDERATIVA-basquet-masculino` |
| C.FED / C FED U13 FEM, U15/U17 FEM | `ICDPE-CUOTA-FEDERATIVA-basquet-femenino` |
| Adicional Basquet Escuelita | `ICDPE-BASQUET-ESCUELITA` |
| Adicional Patin 1° Nivel | `ICDPE-PATIN-MINI` |
| Adicional Voley Escuela | `ICDPE-VOLEY-ESCUELA` |
| Adicional Voley Mayor y Voley Menor | `ICDPE-VOLEY-FEDERADO` |
| Arancel Danza | `ICDPE-DANZA` |
| Arancel Tae Kwon-do | `ICDPE-TAEKWONDO` |
| AVANZADO 3 | `ICDPE-PATIN-AVANZADO` |
| ARTISTICA 1 CLASE | `ICDPE-GIMNASIA-ARTISTICA-1-CLASE` |
| Cuota Social * | ítem de cuota según categoría en el texto del informe |
| Cuota Social Menor Hijo 2º | categoría **2° Hermano** (mismo ítem de cuota) |
| Cuota Social Menor Hijo 3 | categoría **3° Hermano** (mismo ítem de cuota) |

Equipos / etiquetas de tira (U17 FLEX, PRE-MINI A/B U9, …): alias de arancel mensual.

**PRE-MINI A U9** = tira **U9 Azul** → `ICDPE-BASQUET-MASCULINO-MINIBASQUET` (no Escuelita).
**MINI A U11** = **U11 Azul** → el mismo ítem Minibasquet.
**INFA A / Infantiles A U13** = **U13 Azul** → Minibasquet.
**CADETES A U15 / JUVENILES A U17 / LIGA APROX A U21** = tira **Azul** → `ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL`.
Tira B = Amarillo (Minibasquet U9–U13 o Formativas Amarilla U15+).
«Adicional Basquet Escuelita» es el único concepto que va a `ICDPE-BASQUET-ESCUELITA`.
**SUPERIOR B** (concepto del informe de cobranza) = equipo **Basquet / Masculino / Amarillo / SUPERIOR**
→ ítem `BASQUET / SUPERIOR / AMARILLO` (no confundir con el equipo de vóley «Superior B» del padrón).

### Cuota Complementaria (`CTO COMP …`)

Cargo extra temporal (**Cuota Complementaria**), ítem habitual `ICDPE-CARGO-VARIOS`,
monto variable por actividad/grupo. Se factura con **título/descripción** tipo
«CTO COMP BASQ TIRA A/B/FLEX (08/2026)». **Sin mora.**

| Informe | Descripción en SI (ejemplo) |
|---------|----------------------------|
| CTO COMP BASQ TIRA A y B | CTO COMP BASQ TIRA A/B/FLEX (equivale a «A/B/FLEX») |
| CTO COMP BASQ ESC/FEM | CTO COMP BASQ ESC/FEM / BASQUET ESC/FEM |
| CTO COMP BASQ TIRA A/B/FLEX | CTO COMP BASQ / BASQUET TIRA A/B/FLEX |
| CTO COMP FUT ESC | CTO COMP FUTBOL ESC |
| CTO COMP FUTBOL FAFI/TABI | CTO COMP FUTBOL TABI/FAFI |
| CTO COMP PATIN ADULTOS / INICIAL / INTERMEDIO | mismo texto en descripción |
| CTO COMP VOLEY / VOLEY ESC | mismo texto en descripción |
| Adicional Voley Menor | `ICDPE-VOLEY-FEDERADO` |
| FUNCIONAL GAP | Arancel Funcional GAP Prof. Noelia (`ICDPE-FUNCIONAL-1-CLASE` / `2-CLASES`) |

---

## Scenario: facturación masiva desde informe (cargo pendiente, sin SI)

Given filas del informe con concepto `CTO COMP …` clasificadas como `sin_factura_impaga`
And el socio tiene `Cargo Socio` recurrente `Pendiente` con título equivalente (fuzzy)
And no existe SI del período para ese título
When Secretaría ejecuta `bulk_facturar_cto_comp_informe.run`
Then se emite la SI del período con `prepagar_cargo_socio`
And filas sin cargo pendiente equivalente quedan en `sin_cargo_pendiente` del log.

---

## Scenario: alta masiva de cargo desde informe

Given filas CTO COMP del informe sin SI del período ni `Cargo Socio` equivalente
When Secretaría ejecuta `bulk_alta_cargo_cto_comp_informe.run`
Then crea `Cargo Socio` recurrente `Pendiente`, ítem `ICDPE-CARGO-VARIOS`, monto del informe
And `fecha_desde` = mes del primer período del informe para ese socio/concepto
And no factura automáticamente (`facturar_mes_corriente=false`)
When corre el pipeline (`run_pipeline`)
Then factura con `bulk_facturar_cto_comp_informe` y aplica cobranzas con `bulk_payments`.

---

## Scenario: facturación masiva sin factura (cuota / arancel / federativa)

Given filas del informe o del log `apply_cobranzas` con código `sin_factura_impaga`
And el concepto **no** es `CTO COMP …`
And no existe ninguna SI del período para el socio
When Secretaría ejecuta `bulk_facturar_sin_factura_informe.run`
Then por cada par socio/período se llama `generar_cargo_socio` (cuota + aranceles pendientes)
And si la línea del concepto sigue ausente (p. ej. cuota federativa), se emite SI puntual
  con el ítem resuelto por `resolver_item_codes_concepto` y monto del informe
When corre `run_pipeline`
Then aplica cobranzas con `bulk_payments` sobre el Excel del informe.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Mapeo + búsqueda | `scripts/informe_concepto_cobranza.py` |
| Mora por línea | `members/services/mora_al_cobro.py` |
| Cobro parcial | `members/services/cobranza_manual.py` |
| Bulk | `scripts/bulk_payments.py` |
| Facturación CTO COMP informe | `scripts/bulk_facturar_cto_comp_informe.py` |
| Alta cargo CTO COMP informe | `scripts/bulk_alta_cargo_cto_comp_informe.py` |
| Facturación sin factura (no CTO COMP) | `scripts/bulk_facturar_sin_factura_informe.py` |
| Tests | `tests/test_informe_concepto_cobranza.py`, `tests/test_bulk_payments.py`, `tests/test_bulk_facturar_sin_factura_informe.py` |

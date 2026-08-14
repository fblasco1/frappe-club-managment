# Vóley y fútbol ICDPE — aranceles mensuales por tira/grupo

## Modelo

- **Cobro operativo:** `Grupo Actividad.item` es la fuente cuando la inscripción no tiene equipo
  (cascada: equipo → grupo → actividad).
- Equipos pueden conservar el mismo ítem para roster futuro.
- **Basquet** sigue con arancel por equipo (grupos sin `item`).
- Sin packs CLASES.

## Vóley — ítems ERPNext (cuenta 412001, CC `Voley - ICDPE`)

Solo **dos** aranceles (etiquetado único):

| item_code | Nombre | Monto ARS | Uso |
|-----------|--------|-----------|-----|
| `ICDPE-VOLEY-FEDERADO` | `ARANCEL MENSUAL - VOLEY/FEDERADO` | 30.500 | Grupo **Tira** (U11–Superior) |
| `ICDPE-VOLEY-ESCUELA` | `ARANCEL MENSUAL - VOLEY/ESCUELA` | 21.500 | **Escuela Adolescente** y **Escuelita Minivoley** |

Legacy (`ICDPE-VOLEY-TIRA-*`, `…ESCUELA-ADOLESCENTE`, `…ESCUELITA-MINIVOLEY`) se remapean y deshabilitan.

## Scenario: facturas legacy remapean a canónico

Given líneas de Sales Invoice Item con `ICDPE-VOLEY-TIRA-30500` o `ICDPE-VOLEY-ESCUELITA-MINIVOLEY`
And la estructura de grupos ya usa `ICDPE-VOLEY-FEDERADO` / `ICDPE-VOLEY-ESCUELA`
When corre el remapeo de facturas Vóley (patch / consolidate)
Then esas líneas pasan a `ICDPE-VOLEY-FEDERADO` y `ICDPE-VOLEY-ESCUELA`
And **Deuda por actividad** clasifica el arancel de Vóley (no queda en $0).

## Scenario: informe acepta equivalencias legacy sin remapeo previo

Given una inscripción cuyo ítem resuelto es `ICDPE-VOLEY-FEDERADO`
And la factura pendiente aún tiene línea `ICDPE-VOLEY-TIRA-30500`
When se calcula el desglose de deuda en rango
Then el monto de esa línea cuenta como **deuda_arancel**.

## Scenario: vóley federado (tira)

Given `Voley Femenino` / grupo `Tira` con `item = ICDPE-VOLEY-FEDERADO`
When se resuelve el arancel (con o sin equipo)
Then devuelve `ICDPE-VOLEY-FEDERADO` con tarifa 30.500.

## Scenario: vóley tira sin equipo

Given inscripción en `Voley Femenino` / `Tira` **sin** `equipo_actividad`
When se resuelve el arancel
Then usa el ítem del grupo Federado (`ICDPE-VOLEY-FEDERADO`).

## Scenario: vóley escuela / escuelita

Given `Voley Femenino` / `Escuelita Minivoley` o `Escuela Adolescente`
When se resuelve el arancel solo con grupo
Then devuelve `ICDPE-VOLEY-ESCUELA` con tarifa 21.500.

## Fútbol — estructura

- **3 tiras competitivas:** FAFI y TABI A ($27.500).
- **Escuelita:** opera como **TABI B** ($24.500).

| item_code | Monto ARS | Grupo |
|-----------|-----------|-------|
| ICDPE-FUTBOL-FAFI | 27.500 | FAFI |
| ICDPE-FUTBOL-TABI-A | 27.500 | TABI A |
| ICDPE-FUTBOL-TABI-B | 24.500 | TABI B (escuelita) |

## Scenario: fútbol FAFI solo grupo

Given inscripción en `Futbol` / `FAFI` **sin** equipo
When se resuelve el arancel
Then devuelve `ICDPE-FUTBOL-FAFI` con tarifa 27.500.

## Scenario: fútbol TABI B

Given `Futbol` / `TABI B` / `2018/2019` (o solo grupo)
When se resuelve el arancel
Then devuelve `ICDPE-FUTBOL-TABI-B` con tarifa 24.500.

## Scenario: fútbol escuelita es TABI B

Given `Futbol` tiene grupos FAFI, TABI A y TABI B
And la escuelita no es un cuarto grupo aparte
When se inscribe un socio en `TABI B` / `2020/2021`
Then devuelve `ICDPE-FUTBOL-TABI-B` con tarifa 24.500.

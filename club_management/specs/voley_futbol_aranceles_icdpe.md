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

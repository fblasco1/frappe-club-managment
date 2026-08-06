# Vóley y fútbol ICDPE — aranceles mensuales por tira/grupo

## Modelo

- **Cobro operativo:** `Grupo Actividad.item` es la fuente cuando la inscripción no tiene equipo
  (cascada: equipo → grupo → actividad).
- Equipos pueden conservar el mismo ítem para roster futuro.
- **Basquet** sigue con arancel por equipo (grupos sin `item`).
- Sin packs CLASES.

## Vóley — ítems ERPNext (cuenta 412001, CC `Voley - ICDPE`)

| item_code | Monto ARS | Uso |
|-----------|-----------|-----|
| ICDPE-VOLEY-TIRA-30500 | 30.500 | **Tira unificada (Formativas)** — todas las categorías U11–Superior |
| ICDPE-VOLEY-ESCUELA-ADOLESCENTE | 21.500 | Escuela Adolescente |
| ICDPE-VOLEY-ESCUELITA-MINIVOLEY | 21.500 | Escuelita Minivoley |
| ICDPE-VOLEY-TIRA-21500 | 21.500 | Legacy U11-U12; no usar en Tira unificada |

## Scenario: vóley tira unificada Formativas

Given `Voley Femenino` / grupo `Tira` con `item = ICDPE-VOLEY-TIRA-30500`
When se resuelve el arancel (con o sin equipo)
Then devuelve `ICDPE-VOLEY-TIRA-30500` con tarifa 30.500.

## Scenario: vóley tira U12 sin equipo

Given inscripción en `Voley Femenino` / `Tira` **sin** `equipo_actividad`
When se resuelve el arancel
Then usa el ítem del grupo Formativas (`ICDPE-VOLEY-TIRA-30500`).

## Scenario: vóley escuelita minivoley

Given `Voley Femenino` / `Escuelita Minivoley` (grupo con ítem)
When se resuelve el arancel solo con grupo
Then devuelve `ICDPE-VOLEY-ESCUELITA-MINIVOLEY` con tarifa 21.500.

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

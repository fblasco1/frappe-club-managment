# Vóley y fútbol ICDPE — aranceles mensuales por categoría

## Modelo

- Aranceles mensuales por equipo (`Equipo Actividad.item`), igual que básquet.
- Sin packs CLASES.

## Vóley — ítems ERPNext (cuenta 412001, CC `Voley - ICDPE`)

| item_code | Monto ARS | Equipos |
|-----------|-----------|---------|
| ICDPE-VOLEY-TIRA-21500 | 21.500 | Tira U11, U12 |
| ICDPE-VOLEY-TIRA-30500 | 30.500 | Tira U13–U21, Superior A, Superior B |
| ICDPE-VOLEY-ESCUELA-ADOLESCENTE | 21.500 | Escuela Adolescente |
| ICDPE-VOLEY-ESCUELITA-MINIVOLEY | 21.500 | Escuelita Minivoley |

## Scenario: vóley tira U12

Given `Voley Femenino` / `Tira` / `U12`
When se resuelve el arancel
Then devuelve `ICDPE-VOLEY-TIRA-21500` con tarifa 21.500.

## Scenario: vóley superior A

Given equipo `Superior A` bajo `Tira`
When se resuelve el arancel
Then devuelve `ICDPE-VOLEY-TIRA-30500` con tarifa 30.500.

## Scenario: vóley escuelita minivoley

Given `Voley Femenino` / `Escuelita Minivoley`
When se resuelve el arancel
Then devuelve `ICDPE-VOLEY-ESCUELITA-MINIVOLEY` con tarifa 21.500.

## Fútbol — estructura

- **3 tiras competitivas:** FAFI y TABI A ($27.500).
- **Escuelita:** opera como **TABI B** ($24.500), con categorías por año de nacimiento agrupado.

| item_code | Monto ARS | Grupo |
|-----------|-----------|-------|
| ICDPE-FUTBOL-FAFI | 27.500 | FAFI |
| ICDPE-FUTBOL-TABI-A | 27.500 | TABI A |
| ICDPE-FUTBOL-TABI-B | 24.500 | TABI B (escuelita) |

## Scenario: fútbol FAFI 2016

Given `Futbol` / `FAFI` / `2016`
When se resuelve el arancel
Then devuelve `ICDPE-FUTBOL-FAFI` con tarifa 27.500.

## Scenario: fútbol TABI B

Given `Futbol` / `TABI B` / `2018/2019`
When se resuelve el arancel
Then devuelve `ICDPE-FUTBOL-TABI-B` con tarifa 24.500.

## Scenario: fútbol escuelita es TABI B

Given `Futbol` tiene grupos FAFI, TABI A y TABI B
And la escuelita no es un cuarto grupo aparte
When se inscribe un socio en `TABI B` / `2020/2021`
Then devuelve `ICDPE-FUTBOL-TABI-B` con tarifa 24.500.

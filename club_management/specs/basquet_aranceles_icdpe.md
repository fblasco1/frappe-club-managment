# Básquet ICDPE — aranceles mensuales por categoría

## Modelo

- **No existen** ítems «Packs CLASES» para el club: solo **aranceles mensuales** según categoría / asiduidad.
- El arancel se resuelve: `Equipo Actividad.item` → `Grupo Actividad.item` → `Actividad.item`.
- Cada categoría (U9, U11, …) puede tener un ítem distinto aunque compartan tira.
- Actividad operativa única: **Basquet** (`basquet_estructura_unificada.md`).
- Centro de costo ERPNext único: **Deportes - Basquet - ICDPE** (`basquet_cost_center_consolidado.md`).

## Ítems ERPNext (cuenta 412001)

| item_code | Monto ARS |
|-----------|-----------|
| ICDPE-BASQUET-MASCULINO-MINIBASQUET | 28.500 |
| ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL | 28.500 |
| ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA | 26.500 |
| ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX | 26.500 |
| ICDPE-BASQUET-ESCUELITA | 21.000 |
| ICDPE-BASQUET-FEMENINO-SUP | 26.500 |

## Scenario: Masculino / Azul U13 usa minibásquet

Given `Basquet` / `Masculino / Azul` / equipo `U13`
And el equipo tiene `item = ICDPE-BASQUET-MASCULINO-MINIBASQUET`
When se resuelve el arancel de una inscripción a ese equipo
Then devuelve `ICDPE-BASQUET-MASCULINO-MINIBASQUET` con tarifa 28.500
And el `Item Default.selling_cost_center` es `Deportes - Basquet - ICDPE`.

## Scenario: Masculino / Azul U15 usa formativas azul

Given equipo `U15` bajo `Masculino / Azul`
And `item = ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL`
When se resuelve el arancel
Then devuelve `ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL` con tarifa 28.500.

## Scenario: packs CLASES retirados

Given existían ítems `ICDPE-PACKS-CLASES-*`
When corre el patch `retire_packs_clases_items`
Then esos ítems quedan `disabled = 1` y no se crean de nuevo en el seed.

## Scenario: seed estructura básquet unificada

Given patch `sync_basquet_aranceles_icdpe`
Then la actividad **Basquet** tiene grupos Masculino / Azul, Masculino / Amarillo, Masculino / Flex, Femenino / Formativa, Femenino / Superior y Mixto / Escuela
And cada equipo listado por Secretaría tiene su `item` enlazado.

## Scenario: escuelita mixta

Given actividad **Basquet** con grupo `Mixto / Escuela` y equipos `U7 / U9` y `U11 / U13`
When se resuelve el arancel de una inscripción a `U7 / U9`
Then devuelve `ICDPE-BASQUET-ESCUELITA` con tarifa 21.000.

## Scenario: básquet femenino

Given actividad **Basquet** con grupo `Femenino / Formativa`
Then equipos U9–U17 usan `ICDPE-BASQUET-ESCUELITA`
And grupo `Femenino / Superior` con equipo `Superior Fem` usa `ICDPE-BASQUET-FEMENINO-SUP`.


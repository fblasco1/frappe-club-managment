# Patín y otras actividades ICDPE — aranceles mensuales

## Modelo

- **Cobro operativo:** `Grupo Actividad.item` cuando la inscripción no tiene equipo
  (cascada equipo → grupo → actividad).
- Equipos pueden compartir el mismo ítem del grupo.
- Actividades planas usan `usa_grupos = 0` e ítem en la actividad.

## Patín Artístico — grupos y equipos

| Grupo | Monto ARS | Equipos |
|-------|-----------|---------|
| Patin Avanzado | 42.000 | A, B, C1, C2 |
| Patin Intermedio | 36.000 | 1, 2 |
| Patin Mini | 20.500 | (único) |
| Patin Teens | 20.500 | (único) |
| Adulto | 26.500 | (único) |
| Patin Danza | 29.500 | (único) |

## Scenario: patín avanzado equipo B

Given `Patin Artistico` / `Patin Avanzado` / `B`
When se resuelve el arancel
Then devuelve `ICDPE-PATIN-AVANZADO` con tarifa 42.000.

## Scenario: patín avanzado solo grupo

Given inscripción en `Patin Artistico` / `Patin Avanzado` **sin** equipo
When se resuelve el arancel
Then usa `Grupo Actividad.item` = `ICDPE-PATIN-AVANZADO`.

## Scenario: patín mini

Given `Patin Artistico` / `Patin Mini`
When se resuelve el arancel
Then devuelve `ICDPE-PATIN-MINI` con tarifa 20.500.

## Scenario: patín adulto

Given `Patin Artistico` / `Adulto`
When se resuelve el arancel
Then devuelve `ICDPE-PATIN-ADULTO` con tarifa 26.500.

## Otras actividades con grupos (frecuencia / tipo de pase)

| Actividad | Grupos | Ítems |
|-----------|--------|-------|
| Gimnasia Artistica | 1 / 2 clases por semana | 15.500 / 20.500 |
| Boxeo | 1 / 2 / 3 clases por semana | 14.500 / 26.000 / 38.000 |
| Yoga | 1 / 2 clases por semana | 23.500 / 28.500 |
| Gimnasio Fitness | No Socio / Socio | 44.000 / 22.000 |
| Iniciacion Deportiva | 1 / 2 clases por semana | 15.500 / 20.500 |

## Scenario: iniciación deportiva 1 clase

Given `Iniciacion Deportiva` / `1 Clase por Semana`
When se resuelve el arancel
Then devuelve `ICDPE-INICIACION-DEPORTIVA-1-CLASE` con tarifa 15.500.

## Scenario: gimnasio socio

Given `Gimnasio Fitness` / `Socio`
When se resuelve el arancel
Then devuelve `ICDPE-GYM-PASE-LIBRE-SOCIO` con tarifa 22.000.

## Actividades planas (`usa_grupos = 0`)

| Actividad | item_code | Monto ARS |
|-----------|-----------|-----------|
| Danza | ICDPE-DANZA | 15.500 |
| Taekwondo | ICDPE-TAEKWONDO | 21.500 |
| Shui Lu | ICDPE-SHUI-LU | 37.000 |
| Ritmos Latinos | ICDPE-RITMOS-LATINOS | 21.500 |

## Scenario: gimnasia 2 clases

Given `Gimnasia Artistica` / `2 Clases por Semana`
When se resuelve el arancel
Then devuelve `ICDPE-GIMNASIA-ARTISTICA-2-CLASES` con tarifa 20.500.

## Scenario: danza plana

Given `Danza` con `usa_grupos = 0`
When se resuelve el arancel desde la actividad
Then devuelve `ICDPE-DANZA` con tarifa 15.500.

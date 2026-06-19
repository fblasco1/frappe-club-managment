# Cuotas sociales y suscripción ERPNext

Montos por categoría en `members/data/cuotas_sociales_vigentes.py`.  
Suscripción mensual **solo cuota social** (`CLUB-Cuota-Social-Base`).

## Scenario: Setup cuota social única

Given ERPNext Subscriptions disponible
When se ejecuta `sync_cuotas_sociales_club()`
Then existe el ítem `CLUB-Cuota-Social-Base` y el plan `Plan Cuota Social Base`
And cada fila de `Club Settings.cuotas_categoria` apunta a ese ítem con el monto vigente de su categoría

## Scenario: Validación de solicitud

When Secretaría valida una solicitud (`Validar` → `Validada`)
Then se crea `Customer` y `Subscription` activa al plan de cuota social del ítem configurado

## Scenario: Baja de socio

When el socio pasa a estado `Baja`
Then se cancelan sus suscripciones de cuota social activas

## Scenario: Retiro seed aranceles Mayo 2026

When se ejecuta `retire_aranceles_mayo_2026`
Then se eliminan ítems `ICDPE-ARANCEL-MAYO26-*` y sus planes/precios
And se deshabilitan los grupos/tiras creados por ese seed
And **no** se crean suscripciones por inscripción a actividades

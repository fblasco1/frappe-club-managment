# Cuotas sociales y suscripción ERPNext

Montos por categoría en `members/data/cuotas_sociales_vigentes.py`.  
Suscripción mensual de **cuota social** (`CLUB-Cuota-Social-Base`) y, en el modelo objetivo,
**un plan por arancel** de cada inscripción activa.

**Calendario y facturación:** ver **`cobranza_suscripcion_mensual_unificada.md`**
(emisión día 1, 1.er vencimiento día 10, 2.º vencimiento último día del mes).
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

## Scenario: Alta posterior a baja

When Secretaría da de alta a un socio en `Baja` (`socio_alta_post_baja.md`)
Then se re-sincroniza la suscripción de cuota social del `Customer`

## Scenario: Retiro seed aranceles Mayo 2026

When se ejecuta `retire_aranceles_mayo_2026`
Then se eliminan ítems `ICDPE-ARANCEL-MAYO26-*` y sus planes/precios
And se deshabilitan los grupos/tiras creados por ese seed
And **no** se crean suscripciones por inscripción a actividades *(legacy seed Mayo 2026)*

## Scenario: arancel de actividad en suscripción *(objetivo)*

Given un socio activo inscripto en una actividad con ítem de arancel
When la inscripción queda activa
Then se agrega el plan de arancel a la suscripción del socio
And la deuda mensual se emite el día 1 con vencimientos según `cobranza_suscripcion_mensual_unificada.md`

*(Implementación pendiente; hoy los aranceles entran solo vía job `generar_deuda_mensual_socio`.)*
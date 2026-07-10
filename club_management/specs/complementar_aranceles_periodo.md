# Spec: Complementar aranceles de un período ya facturado (solo cuota)

Cuando el job mensual emitió **solo cuota social** (p. ej. `incluir_aranceles_en_deuda_mensual = 0`) y luego se habilitan aranceles, Secretaría debe poder emitir **solo los aranceles faltantes** del mismo período sin duplicar cuota ni ítems ya facturados.

**Relacionado:** `cobranza_periodica_mensual.md`, `cobranza_config_club_settings.md`

---

## Scenario: socio con cuota julio y aranceles pendientes

Given un `Socio` `Activo` con inscripciones `Activa`
And ya existe `Sales Invoice` del período `07/2026` con línea de cuota social
And los ítems de arancel de esas inscripciones **no** están en ninguna factura del período
When se ejecuta `complementar_aranceles_periodo_socio(S, reference_date=2026-07-01)`
Then se crea una nueva `Sales Invoice` submitted con `periodo_cobro = 07/2026`
And las líneas son **solo** aranceles de inscripciones activas
And `remarks` indica aranceles del período (distinto de «cuota mensual»)
And `Socio.saldo_deuda` se sincroniza.

---

## Scenario: idempotencia aranceles

Given el socio ya tiene todos los aranceles del período facturados
When se vuelve a ejecutar `complementar_aranceles_periodo_socio`
Then no se crea factura (`None`).

---

## Scenario: batch todos los elegibles

Given socios `Activo` o `Moroso` con aranceles pendientes en el período
When se ejecuta `complementar_aranceles_periodo_socios(reference_date=2026-07-01)`
Then procesa cada socio elegible
And devuelve resumen con facturas creadas, omitidos y errores.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `members/services/cobranza_periodica.py` |
| Tests | `members/tests/test_complementar_aranceles_periodo.py` |
| Script ops | `scripts/emitir_aranceles_periodo.py` |

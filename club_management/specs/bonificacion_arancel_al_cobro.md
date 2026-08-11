# Spec: Bonificación de arancel al cobro

Descuento puntual del **arancel** (p. ej. clase no dada / no recuperada), masivo o
individual, aplicado al **Registrar cobro** — no al generar la deuda mensual.
Distinto de `Beca Socio` (beneficio continuo al facturar).

**Relacionado:** `recargos_mora_dos_tramos.md`, `registrar_cobro_fecha.md`,
`beca_socio.md`, `cobro_multi_factura_medios_mixtos.md`

---

## Modelo

DocType **`Bonificacion Arancel`**:

| Campo | Rol |
|-------|-----|
| `periodo_cobro` | `MM/YYYY` del mes bonificado |
| `actividad` / `grupo_actividad` / `equipo_actividad` | Alcance masivo (al menos uno si no hay socio) |
| `socio` | Opcional; si está → individual; vacío → masiva |
| `tipo_descuento` | `Porcentaje` \| `Monto fijo` |
| `valor` | % o monto |
| `motivo` | Obligatorio |
| `estado` | `Activa` / `Anulada` |

`Club Settings.item_bonificacion_arancel`: ítem ERPNext para la línea de la nota de crédito.

**Qué descuenta:** solo montos de líneas de arancel de la SI (no cuota social ni cargos extra).

**Combinación:** se suman bonificaciones aplicables (masiva + individual); tope = suma de líneas de arancel de esa SI.

**Orden con mora:** 1) exigido con mora; 2) restar bonificación; 3) total = `max(0, exigido − bonif)`.

**Contabilidad al confirmar cobro:** Credit Note (`Sales Invoice` `is_return=1` contra la SI origen) idempotente + `Payment Entry` por el neto.

---

## Scenario: matching masivo por grupo y período

Given una `Bonificacion Arancel` Activa sin `socio`, con `grupo_actividad = G`, `periodo_cobro = 08/2026`, `tipo_descuento = Porcentaje`, `valor = 25`
And un socio con inscripción activa en ese grupo
And una SI del período `08/2026` con línea de arancel $28.500 (y opcionalmente cuota)
When se previsualiza el cobro de esa SI
Then el monto de bonificación sobre arancel es `28.500 × 0,25 = 7.125`
And el total a cobrar baja en ese monto (tras mora si aplica).

---

## Scenario: matching individual

Given una `Bonificacion Arancel` Activa con `socio = S`, `periodo_cobro = 08/2026`, `Monto fijo = 5.000`
And SI de S en `08/2026` con arancel ≥ 5.000
When se previsualiza el cobro
Then bonificación = 5.000.

---

## Scenario: tope en líneas de arancel

Given arancel en la SI = 10.000 y bonificación fija = 50.000
When se calcula
Then bonificación aplicada = 10.000 (no supera el arancel).

---

## Scenario: no aplica a factura solo de cuota social

Given SI con únicamente línea de cuota social
And bonificación masiva vigente para el período
When se previsualiza
Then `monto_bonificacion = 0`.

---

## Scenario: preview no crea credit note

Given bonificación aplicable
When Secretaría llama preview (sin confirmar)
Then no se crea Credit Note
And el resumen muestra la bonificación (−) y el total neto.

---

## Scenario: confirmar cobro crea CN + PE

Given bonificación aplicable y `item_bonificacion_arancel` configurado
When Secretaría confirma Registrar cobro
Then se crea Credit Note submitted (`is_return=1`, `return_against` = SI origen) por el monto bonificado
And el Payment Entry salda el neto
And un segundo cobro/preview no duplica la misma CN (idempotencia por remarks / vínculo).

---

## Scenario: Desk — alta

Given rol Secretaria
When abre Socio → **Nueva bonificación arancel**
Then el formulario abre con `socio` precargado
When abre Grupo Actividad → **Nueva bonificación arancel**
Then el formulario abre con `grupo_actividad` (y actividad) precargados.

---

## Seguridad

- APIs Desk exigen `ensure_secretaria_operacion_access`.
- No exponer bonificaciones/datos de otro socio vía API de lectura de socio.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| DocType | `members/doctype/bonificacion_arancel/` |
| Servicio | `members/services/bonificacion_arancel.py` |
| Enganche cobro | `mora_al_cobro.py` / `cobranza_desk.py` |
| UI | `socio.js`, `grupo_actividad.js`, `equipo_actividad.js` |
| Tests | `members/tests/test_bonificacion_arancel_al_cobro.py` |

# Spec: Corregir tarifas CTO COMP Básquet de un período (impagas)

En noviembre 2026 las cuotas complementarias de básquet cambiaron:

| Concepto | Monto nuevo |
|----------|------------:|
| `CTO COMP BASQ ESC/FEM` (Escuelita + Femenino) | 6.000 |
| Resto `CTO COMP BASQ…` (p. ej. TIRA A/B/FLEX) | 7.000 |

Secretaría debe poder alinear **facturas impagas** y **cargos Pendiente** del período sin tocar cobros ya aplicados.

**Relacionado:** `informe_concepto_cobranza.md`, `cargo_extra_socio.md`, `fix_tarifas_arancel_impagas.py`

---

## Scenario: dry-run detecta SI impaga ESC/FEM a corregir

Given una `Sales Invoice` submitted con `periodo_cobro = 11/2026`, `outstanding_amount > 0`
And una línea cuya descripción equivale a `CTO COMP BASQ ESC/FEM` con `rate = 4000`
When se ejecuta `run(periodo_cobro="11/2026", dry_run=True)`
Then el reporte lista la factura en `facturas` con `old_rate=4000`, `new_rate=6000`
And la factura no se modifica.

---

## Scenario: dry-run detecta SI impaga TIRA a corregir

Given una SI impaga `11/2026` con descripción `CTO COMP BASQ TIRA A/B/FLEX (11/2026)` a `rate = 6000`
When corre el dry-run
Then figura con `new_rate=7000`.

---

## Scenario: apply protege producción / local

When `run(..., dry_run=False)` sin `confirm`
Then lanza `ValidationError` y no modifica datos.
When en local `confirm="local-dev"` o en prod `confirm="APPLY_PROD"`
Then permite el apply.

---

## Scenario: apply parchea SI impaga e idempotencia

Given la SI ESC/FEM del primer escenario
When `run(..., dry_run=False, confirm="local-dev")`
Then la línea queda en `rate=6000` y `outstanding_amount` / totales se ajustan por la diferencia
And un segundo apply no vuelve a cambiarla (`sin_cambio` / ausente de parcheables).

---

## Scenario: SI con pagos no se toca

Given una SI del período con línea CTO COMP BASQ y `outstanding_amount < grand_total` (o `outstanding_amount = 0`)
When corre `run` con `solo_impagas=True` (default)
Then no aparece entre las facturas a parchear.

---

## Scenario: cargo Pendiente se actualiza

Given un `Cargo Socio` `estado=Pendiente` con título `CTO COMP BASQUET TIRA A/B/FLEX` y `monto=6000`
When corre apply
Then el cargo queda en `monto=7000`.

---

## Scenario: no basquet / no CTO COMP ignorados

Given una SI impaga con `CTO COMP VOLEY ESC` o un arancel `ICDPE-BASQUET-…`
When corre `run`
Then no se modifica.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Script | `scripts/fix_tarifas_cto_comp_basquet_impagas.py` |
| Tests | `tests/test_fix_tarifas_cto_comp_basquet_impagas.py` |

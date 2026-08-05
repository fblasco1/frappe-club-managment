# Spec: Prepago / cancelación adelantada de cargos extras

Secretaría debe poder cobrar **meses hacia adelante** de un `Cargo Socio`
recurrente (p. ej. cancelación total de la **cuota federativa** del resto del
período), generando las facturas de los meses futuros y registrando el cobro en
un solo acto o en pasos separados.

**Relacionado:** `flujo_cobranzas.md`, `cargo_extra_socio.md`,
`cargo_extra_conceptos_y_facturacion.md`, `cobro_multi_factura_medios_mixtos.md`

---

## Definiciones

- **Prepago de cargo recurrente:** emitir SI por cada mes restante entre
  `max(mes_corriente, fecha_desde)` y `fecha_hasta` (inclusive), con
  `periodo_cobro` de cada mes, mismo ítem/monto del cargo (o monto override
  explícito), y marcar el cargo de forma que **no** vuelva a entrar en la
  deuda mensual automática para esos períodos.
- **Cancelación total:** prepago de **todos** los meses restantes del rango
  vigente del cargo.

No aplica a `modo_cobro = Unico` (ya se factura al crear).

---

## Scenario: facturar meses futuros de un cargo recurrente

Given un `Cargo Socio` `Recurrente`, `Pendiente`, `fecha_desde = 2026-03-01`,
`fecha_hasta = 2026-12-31`, monto 5000, ítem federativo
And hoy es 2026-07-15
And ya existe SI del período `07/2026` para ese ítem (o no)
When Secretaría ejecuta **Prepagar cargo** / **Cancelación total** eligiendo
meses `08/2026` … `12/2026` (o «todos los restantes»)
Then se crean SI submitted una por mes, `periodo_cobro` = cada mes
And cada SI tiene una línea con el ítem y monto del cargo
And los períodos ya facturados se omiten (idempotencia)
And el cargo queda en estado que evite doble facturación mensual
  (p. ej. `Facturado` si no quedan meses, o flag/`meses_prepagados` /
  `fecha_hasta` ajustada — **elegir en implementación:** preferir
  **registrar períodos cubiertos** y excluirlos en `build_invoice_items_for_socio`)
And `Socio.saldo_deuda` refleja las nuevas SI.

---

## Scenario: cobrar cancelación total con medios mixtos

Given SI generadas por prepago aún con outstanding
When Secretaría usa **Registrar cobro** seleccionando esas SI
And paga con Efectivo + Transferencia (suma = total)
Then se aplican las reglas de `cobro_multi_factura_medios_mixtos.md`
And las SI del prepago quedan saldadas.

---

## Scenario: prepago + job mensual no duplica

Given meses `08/2026`–`12/2026` ya prepagados para el cargo
When corre `generar_deuda_mensual_socios` en agosto
Then la factura mensual **no** incluye de nuevo ese cargo extra para agosto.

---

## Scenario: no prepagar meses anteriores al rango del cargo

Given `fecha_desde = 2026-03-01`
When Secretaría intenta prepagar `02/2026`
Then error de validación.

---

## Scenario: permisos

Given usuario sin `Secretaria` / `System Manager`
When invoca la API de prepago
Then `PermissionError`.

---

## UI Desk

- En formulario `Cargo Socio` (y/o desde `Socio`): botón
  **Prepagar / cancelación total**.
- Diálogo: lista de meses restantes con checkbox (default todos), monto
  estimado, confirmar → crea SI.
- Opcional: checkbox «Registrar cobro ahora» que abre el flujo de cobro
  compuesto con esas SI preseleccionadas.

---

## Artefactos esperados

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/cargo_extra_prepago_adelantado.md` |
| Servicio | `members/services/cargo_socio.py` (o `cargo_extra_prepago.py`) |
| API | `members/api/cargo_extra_desk.py` / `cobranza_desk.py` |
| JS | `cargo_socio.js` y/o `socio.js` |
| Tests | `members/tests/test_cargo_extra_prepago.py` |

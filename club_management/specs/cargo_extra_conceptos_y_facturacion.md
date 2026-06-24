# Spec: Cargo extra por conceptos de la actividad + facturación inmediata

Al generar un **cargo extra** a un socio, la Secretaría debe poder elegir
únicamente entre:

1. **Conceptos asociados a las actividades en las que el socio está inscripto**
   (p. ej. *cuota federativa*, *campus* u otro cargo vinculado a ese deporte), y
2. **Conceptos generales** que no pertenecen a ninguna actividad (p. ej.
   *multa*, *cargo varios*, *colonias*, *eventos*, *indumentaria*).

Además, el cargo extra de cobro **Único** debe quedar **facturado** apenas se
crea (sin un segundo paso manual). Los cargos **Recurrentes** siguen entrando en
la deuda mensual (no se facturan al instante).

**Relacionado:** `cargo_extra_socio.md`, `cobranza_periodica_mensual.md`,
`deuda_socio_desk.md`

---

## Modelo de asociación actividad → concepto

No existe un campo explícito que ligue una actividad con sus conceptos
cobrables. El nexo confiable es el **centro de costo** (`selling_cost_center`
del `Item Default`): el arancel mensual y la cuota federativa de un mismo
deporte comparten centro de costo.

Por lo tanto, los conceptos sugeridos para un socio se derivan así:

- Por cada **inscripción `Activa`** del socio se resuelve su **ítem de arancel**
  (cascada equipo → grupo → actividad) y su **centro de costo**.
- Se ofrecen **todos los ítems vendibles** (`is_stock_item = 0`, `disabled = 0`)
  que comparten esos centros de costo, **excluyendo el arancel mensual**
  (ese se cobra vía «Generar cargo», no como cargo extra).
- Se agregan los **conceptos generales** (ítems de los grupos generales y/o
  códigos generales conocidos que existan en el sitio).

---

## Scenario: conceptos por actividad inscripta

Given un `Socio` con inscripción `Activa` en una actividad cuyo arancel y cuota
federativa comparten centro de costo `CC-A`
And otra actividad con centro de costo `CC-B` en la que el socio **no** está
inscripto
When la Secretaría abre «Nuevo cargo extra» para ese socio
Then la lista de conceptos incluye la **cuota federativa de `CC-A`**
And **excluye** el arancel mensual de `CC-A`
And **excluye** cualquier ítem de `CC-B`.

---

## Scenario: conceptos generales sin actividad

Given ítems generales (p. ej. `Multa`) en un grupo general
When la Secretaría abre «Nuevo cargo extra» para un socio sin inscripciones
Then la lista de conceptos incluye los conceptos generales (p. ej. `Multa`)
And no falla aunque el socio no tenga actividades.

---

## Scenario: cargo único se factura al crear

Given un `Socio` `Activo` con `Customer`
When la Secretaría crea un `Cargo Socio` con `modo_cobro = Unico`, ítem y monto
Then se crea automáticamente una `Sales Invoice` submitted con una línea
And el `Cargo Socio` queda `estado = Facturado` con `sales_invoice` poblado
And `Socio.saldo_deuda` se actualiza.

---

## Scenario: cargo recurrente NO se factura al crear

Given un `Socio` `Activo`
When la Secretaría crea un `Cargo Socio` con `modo_cobro = Recurrente` y
`fecha_hasta`
Then el cargo queda `estado = Pendiente` (sin factura inmediata)
And entra en la deuda mensual mientras esté vigente.

---

## Seguridad

- El endpoint que lista conceptos (`list_conceptos_cargo_extra`) exige rol
  `Secretaria` / `System Manager` (`ensure_secretaria_operacion_access`).
- La auto-facturación reusa `facturar_cargo_socio`, que ya valida permisos.

---

## Artefactos esperados

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio conceptos | `members/services/cargo_extra_conceptos.py` |
| API Desk | `members/api/cargo_extra_desk.py` |
| Controller (auto-factura) | `members/doctype/cargo_socio/cargo_socio.py` |
| Client script (filtro) | `members/doctype/cargo_socio/cargo_socio.js` |
| Ítems generales | `setup/icdpe_create_service_items.py` |
| Tests | `members/tests/test_cargo_extra_conceptos.py`, `members/doctype/cargo_socio/test_cargo_socio.py` |

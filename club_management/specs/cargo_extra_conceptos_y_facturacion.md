# Spec: Cargo extra por conceptos de la actividad + facturación inmediata

Al generar un **cargo extra** a un socio, la Secretaría debe poder elegir
únicamente entre:

1. **Conceptos asociados a las actividades en las que el socio está inscripto**
   (p. ej. *cuota federativa*, *campus* u otro cargo vinculado a ese deporte), y
2. **Conceptos generales** que no pertenecen a ninguna actividad (p. ej.
   *multa*, *cargo varios*, *colonias*, *eventos*, *indumentaria*).

El cargo extra debe quedar **cobrable** apenas se crea:

- **Único:** se factura al instante (sin un segundo paso «Facturar cargo»).
- **Recurrente:** queda `Pendiente` para meses futuros, pero desde Desk se
  ofrece **facturar el mes corriente ahora** para poder cobrarlo de inmediato.
  Si no se factura el mes, entra en «Generar cargo» / deuda mensual.

Tras facturar, Secretaría puede **Registrar cobro** de esa factura (mismo
flujo que el resto de la deuda del socio).

**Relacionado:** `cargo_extra_socio.md`, `cobranza_periodica_mensual.md`,
`deuda_socio_desk.md`, `cobro_multi_factura_medios_mixtos.md`

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
And la factura tiene `periodo_cobro` del mes de emisión y centro de costo del ítem
And el `Cargo Socio` queda `estado = Facturado` con `sales_invoice` poblado
  **en el documento devuelto al cliente** (no solo en base)
And la factura aparece en `list_facturas_pendientes` del socio
And `Socio.saldo_deuda` se actualiza.

---

## Scenario: cargo único no queda Pendiente si falla la factura

Given ERPNext no está disponible (o falta campo Socio en Sales Invoice)
When la Secretaría intenta crear un `Cargo Socio` `Unico`
Then el alta **falla** con error claro
And **no** queda un `Cargo Socio` `Pendiente` sin factura.

---

## Scenario: cargo recurrente factura el mes corriente a pedido

Given un `Socio` `Activo`
When la Secretaría crea un `Cargo Socio` `Recurrente` vigente con
`facturar_mes_corriente = 1` (default en el diálogo Desk)
Then se emite una `Sales Invoice` del período corriente (`periodo_cobro`)
And el cargo permanece `estado = Pendiente` (meses futuros siguen en deuda mensual)
And esa SI aparece en facturas pendientes y se puede cobrar
And «Generar cargo» del mismo mes **no** duplica el ítem.

---

## Scenario: cargo recurrente sin facturar mes (formulario / legado)

Given un `Socio` `Activo`
When la Secretaría crea un `Cargo Socio` `Recurrente` **sin** facturar el mes
Then el cargo queda `estado = Pendiente` (sin SI inmediata)
And entra en la deuda mensual mientras esté vigente
And en Desk hay acción **Facturar mes corriente** para volverlo cobrable.

---

## Scenario: diálogo Nuevo cargo extra en Socio

Given Secretaría está en el formulario `Socio`
When pulsa **Nuevo cargo extra**
Then se abre un **diálogo** (no navega a un formulario vacío de `Cargo Socio`)
And al confirmar un cargo `Unico` se factura y se ofrece **Registrar cobro**
  de esa factura
And al confirmar un cargo `Recurrente` se factura el mes corriente (checkbox
  marcado por defecto) y se ofrece **Registrar cobro**.

---

## Seguridad

- El endpoint que lista conceptos (`list_conceptos_cargo_extra`) exige rol
  `Secretaria` / `System Manager` (`ensure_secretaria_operacion_access`).
- `crear_cargo_extra` y la auto-facturación reusan las mismas validaciones
  de permiso.

---

## Artefactos esperados

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio conceptos | `members/services/cargo_extra_conceptos.py` |
| Servicio cargo | `members/services/cargo_socio.py` |
| API Desk | `members/api/cargo_extra_desk.py` |
| Controller (auto-factura) | `members/doctype/cargo_socio/cargo_socio.py` |
| Client script (filtro + cobro) | `members/doctype/cargo_socio/cargo_socio.js` |
| Diálogo Socio | `members/doctype/socio/socio.js` |
| Ítems generales | `setup/icdpe_create_service_items.py` |
| Tests | `members/tests/test_cargo_extra_conceptos.py`, `members/doctype/cargo_socio/test_cargo_socio.py` |

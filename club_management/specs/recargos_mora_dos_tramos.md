# Spec: Mora al cobro — tramos por vencimiento del período

Al cobrar, el recargo depende de la **fecha de pago** respecto de los
vencimientos del **período de la factura** (`periodo_cobro` = `MM/YYYY`):

| Momento de pago | Recargo | Base |
|-----------------|---------|------|
| Hasta el **1.er vencimiento** (día 10 del mes del período) inclusive | **0 %** | Saldo / valor facturado |
| Después del 1.er vencimiento y hasta el **2.º vencimiento** (**día 20** del mes del período) inclusive | **+10 %** | **Valor facturado** (rate de la SI) |
| **Después** del 2.º vencimiento | **+15 %** (= 10 % + 5 %) | **Valor facturado** (rate de la SI) |

```
si pago ≤ 1.er venc. del período     → sin mora
si 1.er < pago ≤ 2.º venc. del período → valor_facturado × (1 + 0,10)
si pago > 2.º venc. del período        → valor_facturado × (1 + 0,15)
```

**No** se multiplica ningún % por la cantidad de meses de atraso.
**No** se revaloriza al `Item.standard_rate` / precio del mes de pago: si la SI
de octubre tiene arancel 28.500 y en noviembre el ítem pasó a 32.000, al cobrar
octubre con mora la base sigue siendo **28.500**.

### Conceptos sujetos a mora

La mora al cobro aplica **solo** a:

- **Cuota social** — ítem de Club Settings y el ítem legado `CLUB-Cuota-Social-Base` (presente en
  facturas emitidas, p. ej. 08–09/2026), reconocido por código aunque cambie su grupo de ítem
- **Aranceles de actividad** (ítem enlazado a Actividad / Grupo / Equipo)

**No** aplican interés (ni post día 10 / 1.er vencimiento, ni post 2.º vencimiento / mes vencido):

- **Cuotas federativas** (`Cuotas federativas` / `ICDPE-CUOTA-FEDERATIVA-*`)
- **Cargos extra** en general (multas, viajes, colonias, eventos, `Cargo Socio`, etc.)

Al cobrar esas facturas el monto exigido = outstanding del grupo (sin SI de ajuste de mora).

**Relacionado:** `flujo_cobranzas.md`, `cobranza_config_club_settings.md`,
`cobranza_recargo_segundo_vencimiento.md` (job legado), `registrar_cobro_fecha.md`,
`cobro_multi_factura_medios_mixtos.md`, `cargo_extra_socio.md`

---

## Ejemplo canónico (período marzo)

- 1.er vencimiento = **10/03**; 2.º = **20/03**.
- SI de marzo facturada a **10** (aunque luego el ítem suba).

| Fecha de pago | Tramo | Monto |
|---------------|-------|-------|
| 08/03 | ninguno | outstanding / valor facturado (sin %) |
| 15/03 | post 1.er | `10 × 1,10` = **11,00** |
| 20/03 | post 1.er | `10 × 1,10` (aún dentro del 2.º vencimiento) |
| 21/03 | post 2.º | `10 × 1,15` = **11,50** |
| 08/04 | post 2.º | `10 × 1,15` = **11,50** (sigue la base facturada) |
| 15/07 | post 2.º | `10 × 1,15` = **11,50** |

---

## Decisiones (cerradas)

| ID | Decisión |
|----|----------|
| **D1** | El 10 % aplica si `posting_date` es **posterior** al 1.er vencimiento del **período adeudado** (día `dia_primer_vencimiento` de ese mes). |
| **D2** | El 5 % extra aplica solo si `posting_date` es **posterior** al 2.º vencimiento del período (default operativo: **día 20**). Junto con el 10 % suma **15 %**. |
| **D3** | Base de mora (post 1.er y post 2.º) = **valor facturado** de las líneas sujetas (rate/amount de la SI). **No** revalorizar al precio vigente del mes de pago. Ej.: SI octubre a 28.500, ítem ya en 32.000 en noviembre → mora `28.500 × 1,15`. |
| **D4** | El job legado `recargo_segundo_vencimiento_pct` **no** es la fuente de verdad; la mora se calcula **al cobrar**. |
| **D5** | Federativas y cargos extra **no** sufren mora (ni tramo post 1.er ni post 2.º vencimiento). |

---

## Configuración (`Club Settings`) — simplificada

| Campo | Label sugerido | Default | Rol |
|-------|----------------|---------|-----|
| `dia_primer_vencimiento` | Día primer vencimiento | 10 | 1.er vencimiento del mes del período |
| `dia_segundo_vencimiento` | Segundo vencimiento | **20** | 2.º vencimiento del período |
| `recargo_post_vencimiento_pct` | Recargo post 1.er vencimiento (%) | 10 | +10 % entre 1.er y 2.º venc. |
| `recargo_mes_vencido_pct` | Recargo extra post 2.º vencimiento (%) | 5 | +5 % adicional tras el 2.º (total 15 %) |
| `item_recargo_mora` | Ítem recargo mora | — | Obligatorio para crear SI de ajuste |
| `recargo_segundo_vencimiento_pct` | Recargo 2.º vencimiento (%) — legado | 10 | Solo job histórico; no usar en mora al cobro |

---

## Scenario: mismo mes, antes del día 10

Given deuda período `03/2026`
When paga el 2026-03-08
Then tramo = ninguno
And monto = outstanding del grupo (sin recargo).

---

## Scenario: mismo mes, entre día 11 y día 20 inclusive (+10 %)

Given deuda período `03/2026` facturada a 12
And `dia_segundo_vencimiento = 20`
And `recargo_post_vencimiento_pct = 10`
When paga el 2026-03-15
Then tramo = post_primer
And monto = `12 * 1.10` = 13,20.

Given deuda período `03/2026`
When paga el 2026-03-20
Then tramo = post_primer.

---

## Scenario: mismo mes, después del día 20 (+15 % sobre facturado)

Given deuda período `03/2026` facturada a 12
And `dia_segundo_vencimiento = 20`
When paga el 2026-03-21
Then tramo = post_segundo
And monto = `12 * 1.15` = 13,80.

---

## Scenario: mes siguiente (+15 % sobre valor facturado, sin revalorizar)

Given deuda período `03/2026` facturada a 10
And en abril el ítem vigente vale 12
And `recargo_post_vencimiento_pct = 10`, `recargo_mes_vencido_pct = 5`
When paga el 2026-04-08 (posterior al 20/03)
Then tramo = post_segundo
And monto = `10 * 1.15` = 11,50
And la composición muestra la base **facturada**, **sin** `×N meses`.

---

## Scenario: varios meses después sigue +15 % fijo sobre lo facturado

Given deuda de abril facturada a 11, paga en agosto cuando el ítem vale 13
When calcula mora
Then monto = `11 * 1.15` = 12,65
And **no** usa el 13 vigente ni escala el % con la cantidad de meses.

---

## Scenario: arancel de octubre cobrado en noviembre tras aumento

Given SI de arancel período `10/2026` con rate facturado 28.500
And el `Item.standard_rate` ya es 32.000 (aumento de noviembre)
When Secretaría registra el cobro en noviembre (tramo post 2.º)
Then `valor_actual` / base de mora = **28.500**
And monto exigido = `28.500 × 1,15`
And **no** aplica 15 % sobre 32.000.

---

## Scenario: preview Desk y cobro

Given facturas seleccionadas
When Secretaría abre Registrar cobro / llama `preview_mora_al_cobro`
Then ve total y composición por tramo
And al confirmar se crea SI de ajuste si hace falta (`item_recargo_mora` obligatorio)
And la suma de medios coincide con el total a cobrar.

---

## Scenario: factura con varias líneas (cuota + arancel)

Given una `Sales Invoice` del período con **más de una línea** (p. ej. cuota social + arancel)
And outstanding del grupo = suma de esas líneas (p. ej. 57.000)
When se calcula mora en tramo `post_primer` o `post_segundo`
Then `valor_actual` es la **suma** del valor **facturado** de **todas** las líneas
And `monto_exigido` = ese valor × factor del tramo
And si la base facturada fuera incompleta, el piso es `outstanding_factura × factor`
(sin recomponer sobre SI de mora ya creadas; no puede “achicar” la deuda al pasar del día 10 al 11).

---

## Scenario: diálogo Registrar cobro — fecha arriba

Given Secretaría abre **Registrar cobro**
Then el campo **Fecha de cobro** figura **arriba de todo** (antes de la lista de facturas)
And al cambiar la fecha se recalcula el total con mora.

---

## Scenario: cuota federativa no genera mora

Given factura de cuota federativa período `03/2026` con outstanding = 5000
When se calcula mora con posting_date posterior al 1.er o al 2.º vencimiento
Then tramo efectivo = ninguno (concepto exento)
And `aplica_mora` = false
And monto exigido = outstanding
And no se crea SI de ajuste.

---

## Scenario: cargo extra no genera mora

Given factura de cargo extra (p. ej. multa / viaje) período `03/2026`
When se calcula o prepara cobro con mora tras el día 10 o mes vencido
Then no aplica recargo
And monto exigido = outstanding del cargo.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Servicio | `members/services/mora_al_cobro.py` |
| Settings UI | `members/doctype/club_settings/club_settings.json` |
| Tests | `members/tests/test_mora_valor_actual.py`, `members/tests/test_mora_base_facturada.py` |

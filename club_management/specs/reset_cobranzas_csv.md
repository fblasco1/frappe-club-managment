# Spec: Reset limpio de cobranzas del CSV (agosto 2026)

Rehacer facturación e imputación del CSV consolidado **sin parches**.
Cancela Payment Entries y Sales Invoices del universo del CSV, refactura
con tarifas del período de cada fila, y vuelve a aplicar el importer
una sola vez (un PE por fila, mora al cobro sobre la línea del concepto).

**No** cancela la cuota/arancel de septiembre (`09/2026`) salvo SI de mora
colgadas de facturas del universo.

**Relacionado:** `carga_masiva_cobranzas.md`, `informe_concepto_cobranza.md`.

Ejecución:

```text
# Inventario (no cancela)
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.reset_cobranzas_csv.run \\
  --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv", "dry_run": true}'

# Apply cancelación (tras backup + OK)
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.reset_cobranzas_csv.run \\
  --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv", "dry_run": false, "confirm": "RESET_PROD", "fase": "cancelar"}'
```

---

## Universo a resetear

Given el CSV de cobranzas con `fecha_pago` en el rango de cobro
(`2026-08-01`–`2026-08-31`) y `periodo` por fila (p. ej. `06/2026`, `07/2026`, `08/2026`)
When se arma el inventario
Then entran:

1. **Todas** las SI submitted con `periodo_cobro = 08/2026` (cuota, arancel, federativa, CTO COMP, CARNET, FEBAMBA, etc.).
2. SI de períodos **anteriores** (`06/2026`, `07/2026`, …) cuyo par `(socio, periodo)` aparece en el CSV
   (julio/junio cobrados en agosto) **o** que tienen PE con `posting_date` en el rango de cobro.
3. SI de mora (`remarks` like `Mora al cobro {SI}` o ítem `RECARGO-MORA`) vinculadas a las SI de (1) y (2),
   aunque su `posting_date` sea septiembre.
4. Payment Entries submitted (o draft) imputados a esas SI **o** con `posting_date` en el rango de cobro
   y `reference_no` `INF-…`.

Then **no** entran:

- SI de `periodo_cobro` **posterior** a `08/2026` **sin** PE en el rango de cobro (p. ej. cuota mensual de septiembre aún no cobrada).
- SI de julio/junio **sin** fila CSV y **sin** PE en el rango de cobro (deuda de julio impaga se deja).
- Filas/SI **CARNET** (no se cancelan ni se reimputan; van al log de revisión).

---

## Scenario: cobro adelantado (10/11/12 y similares)

Given un PE de agosto (`INF-…`) imputado a una SI de período **posterior** al mes de cierre (`10/2026`, `11/2026`, `12/2026`, u `09/2026` pagada en agosto)
When se arma el inventario / se cancela
Then ese PE y esa SI **sí** entran al reset (se cancelan)
And **no** se vuelve a aplicar el cobro del CSV para ese período
And la fila queda en el log de revisión manual (`excluido_adelantado`) junto a CARNET y `error_socio_no_encontrado`.

Given una SI `09/2026` **sin** PE en agosto
When se cancela el universo
Then esa SI mensual permanece submitted.

---


## Scenario: dry-run no cancela

Given SI y PE del universo
When `run` con `dry_run=True`
Then no cambia `docstatus`
And el resultado lista `payment_entries` y `sales_invoices` a cancelar
And incluye conteos por período
And lista filas `CARNET` (cantidad, monto, nro_socio / socio) **sin** incluirlas en imputación ni como motivo extra de cancelación.

---

## Scenario: CARNET no se imputa

Given una fila del CSV con concepto `CARNET`
When corre el importer o el inventario del reset
Then el estado es `excluido_carnet`
And no se crea ni se busca PE para esa fila
And el log lista el socio (o `nro_socio` si no existe en ERP).

---

## Scenario: cancelar aplica parche PostgreSQL

Given un sitio PostgreSQL (`bench execute` no dispara `before_request`)
When `fase=cancelar`
Then se llama `payment_ledger_postgres.apply_patch` antes de cancelar
And `delinked` se escribe como `1` (smallint), no como boolean
And un error de un documento hace `rollback` y no aborta el resto de la corrida.

---

## Scenario: cancelar deja septiembre mensual

Given socio con SI `08/2026` pagada, SI mora de esa factura, y SI `09/2026` impaga
When `fase=cancelar` con confirmación
Then se cancelan PE de agosto, SI de agosto y SI de mora
And la SI `09/2026` **sin cobro en agosto** sigue submitted.

---

## Scenario: julio cobrado en agosto entra al reset

Given SI `07/2026` con PE `posting_date` en agosto (o fila CSV período `07/2026`)
When se cancela
Then esa SI de julio y sus PE de agosto quedan cancelados
And una SI `07/2026` de otro socio **sin** cobro en agosto ni fila CSV permanece.

---

## Scenario: cargo extra (CTO COMP) entra al reset

Given SI `08/2026` con línea `ICDPE-CARGO-VARIOS` descripción `CTO COMP …`
When se cancela el mes de cierre
Then esa SI se cancela igual que cuota/arancel.

---

## Scenario: gate apply

Given site de producción
When `dry_run=False` sin `confirm='RESET_PROD'`
Then ValidationError y no se cancela nada.

Given site local
When apply sin `confirm='local-dev'`
Then ValidationError.

---

## Etiquetas al refacturar / reimputar

Estas claves del informe **no** son un mismo “cargo extra genérico”:

| Concepto CSV | Clase | Destino |
|--------------|-------|---------|
| `CTO COMP …` | cargo extra (Cuota Complementaria) | `ICDPE-CARGO-VARIOS`, match por descripción, **sin mora** |
| `EXPEDIENTE FEBAMBA` | cargo extra / multa | `ICDPE-MULTA` (o alias), **sin mora** |
| `CARNET` | **excluido** de imputación | No se cobra por el importer. El inventario/reset deja log de filas y socios. |
| `CUOTA SOCIAL MENOR` | cuota | categoría **Menor** ($28.500 ago) |
| `CUOTA SOCIAL MENOR HIJO 2º` / `HIJO 2` | cuota | categoría **2° Hermano** ($27.500 ago), mismo ítem de cuota |
| `CUOTA SOCIAL MENOR HIJO 3` | cuota | categoría **3° Hermano** ($23.500 ago) |
| `ADICIONAL BASQUET ESCUELITA` | **arancel** (no cargo extra) | `ICDPE-BASQUET-ESCUELITA`. El PE truncado `ADICIONAL BASQUET ESCUEL` es el mismo concepto. |
| `INFA A U13`, `U15 FLEX`, … | arancel de equipo | alias en `informe_concepto_cobranza.py` |
| `C FED …` | federativa | ítem federativo, **sin mora** |

Al reaplicar, `referencia_informe` guarda el **concepto completo** (límite 140 chars del campo, sin recorte a 24).

---

## Tarifas patín al refacturar agosto

Item Price vigente en septiembre **no** se usa para SI `08/2026`:

| Ítem | Agosto 2026 |
|------|-------------|
| MINI / TEENS (`ICDPE-PATIN-MINI`, `ICDPE-PATIN-TEENS`) | 20.500 |
| INTERMEDIO | 36.000 |
| AVANZADO 3 | 42.000 |
| PATIN DANZA | 29.500 |
| PATIN ADULTO | 26.500 |

Septiembre conserva las tarifas nuevas del catálogo.

---

## Scenario: refacturar + aplicar (fase siguiente)

Given universo cancelado
When `cobranzas_bulk_importer.apply_prod_agosto` (`reconcile=False`, `auto_facturar=True`)
Then se emiten SI de una línea **sin mora embebida en el rate** (base = CSV÷(1+mora%),
  o tarifas patín agosto congeladas)
And se imputa cada fila del CSV (o error / exclusión explícita)
And Pagos por equipo en el rango de cobro coincide con el subtotal de aranceles del CSV
  (mora del arancel incluida en el cobro del concepto).

```text
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.cobranzas_bulk_importer.apply_prod_agosto
```
---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Script | `scripts/reset_cobranzas_csv.py` |
| Tests | `tests/test_reset_cobranzas_csv.py` |

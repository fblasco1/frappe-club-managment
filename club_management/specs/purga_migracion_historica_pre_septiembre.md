# Spec: Purga y migración histórica (cutoff 31/08/2026)

Rehacer la facturación/cobranza histórica **sin tocar septiembre 2026 en
producción**. Septiembre ya está vivo: facturas y cobros con
`posting_date >= 2026-09-01` deben permanecer intactos.

**Relacionado:** `reset_cobranzas_csv.md`, `carga_masiva_cobranzas.md`,
`informe_concepto_cobranza.md`, `recargos_mora_dos_tramos.md`

Ejecución:

```text
# Dry-run (inventario + plan; no persiste)
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.purge_historical_data_pre_september.run \\
  --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv", "dry_run": true}'

# Apply atómico (purga + facturas + cobros)
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.purge_historical_data_pre_september.run \\
  --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv", "dry_run": false, "confirm": "PURGE_MIGRATE_PROD"}'
```

---

## Constantes de control

| Constante | Valor |
|-----------|-------|
| `CUTOFF` | `2026-08-31` (inclusive: se purga) |
| `SEPT_START` | `2026-09-01` (nunca tocar) |
| Filas CSV agosto | **2.562** |
| Σ `monto_abonado` CSV | **$ 52.115.308,00** |

---

## Scenario: snapshot de integridad de septiembre

Given existen SI y PE con `posting_date >= 2026-09-01`
When arranca `run` (dry-run o apply)
Then se guarda `sept_si_count` y `sept_pe_count` **antes** de cualquier mutación
And al finalizar esos conteos son **idénticos**
And si difieren, la corrida falla (en apply: rollback).

---

## Scenario: safety guard aborta si el universo incluye septiembre

Given un candidato a cancelar (SI o PE) con `posting_date >= 2026-09-01`
When se valida el inventario de purga
Then se lanza `ValidationError` / excepción inmediata
And no se cancela ningún documento
And Socios, Disciplinas, Equipos, Item Prices y docs de septiembre quedan intactos.

---

## Scenario: dry-run no muta

Given SI/PE con `posting_date <= 2026-08-31` y el CSV de agosto
When `run` con `dry_run=True`
Then no cancela ni crea SI/PE
And el resultado lista candidatos a purga, combos a facturar y plan de cobros
And imprime el log de control esperado (totales del CSV).

---

## Scenario: purga quirúgica por posting_date

Given Payment Entries y Sales Invoices submitted (o draft) con
  `posting_date <= 2026-08-31`
When `fase` incluye purga y `dry_run=False` con confirmación
Then **no** entran SI con `periodo_cobro` posterior a `08/2026` (p. ej. cuota
`09/2026` emitida con `posting_date=2026-08-31`): se protegen por período, no
solo por fecha de asiento.

Orden: PE → SI. Las conciliaciones viven como referencias del PE; no se
requiere DocType aparte «Payment Allocation» salvo que exista submitted
vinculado (entonces se cancela solo si su fecha efectiva ≤ cutoff).

---

## Scenario: generación retroactiva de facturas

Given el CSV `cobranzas_bulk_erp_agosto_2026.csv`
When se arma el set de `(nro_socio, concepto, periodo)` con `periodo <= 08/2026`
  (excluye CARNET y filas sin socio / sin mapeo de ítem)
Then por cada combo se emite una SI de una línea:
  - `posting_date` = día 1 del mes del período (`set_posting_time=1`; **no**
    usar `resolve_fechas_factura_mensual`, que fuerza `today()` en deuda vieja)
  - `due_date` = día 10 del mes (o `dia_primer_vencimiento` de Club Settings)
  - `rate` = monto base sin mora (`monto_csv / (1+mora%)` o tarifa patín agosto);
    en **CTO COMP** el rate es el `monto_csv` completo (sin descontar mora)
  - `periodo_cobro` = período
  - estado abierto (`outstanding` = grand_total)
And **CTO COMP** también usa SI histórica (ítem `ICDPE-CARGO-VARIOS`); **no**
  `prepagar_cargo_socio` / `_facturar_cto_comp` (esas rutas fuerzan `today()`)
And no se facturan períodos `>= 09/2026` en este paso
And si una SI recién emitida quedara con `posting_date >= 2026-09-01`, aborta.

---

## Scenario: cobro de período histórico (≤ 08/2026)

Given una fila CSV con `periodo <= 08/2026` y SI abierta del combo
When `monto_abonado > monto_base`
Then se imputa la base a la SI (queda Paid / outstanding 0)
And la diferencia se registra como recargo por mora (`RECARGO-MORA` / SI de
  ajuste vía `preparar_facturas_cobro_con_mora`)
And la SI de mora y el/los PE usan **`fecha_pago` del cobro** (`set_posting_time=1`);
  nunca `today()` (evita asientos en septiembre durante migraciones)
And el PE usa `medio_pago` y referencia canónica INF.

When `monto_abonado <= monto_base`
Then se imputa el monto a la SI sin crear mora (o mora 0).

---

## Scenario: retry de filas sin PE (post-apply)

Given un apply parcial donde quedaron filas ≤08/2026 sin PE (p. ej. CTO COMP
  rechazadas por `posting_date` = hoy)
When `retry_sin_pe` / `run_local_retry_sin_pe`
Then inventaria solo filas imputables sin PE (excluye CARNET, sin socio, adelantados)
And emite las SI faltantes con posting día 1 del período
And imputa cobros (mora SI/PE = `fecha_pago`)
And los conteos de SI/PE con `posting_date >= 2026-09-01` no aumentan
And no ejecuta purga.
---

## Scenario: pagos adelantados (≥ 09/2026) como anticipo

Given una fila con `periodo >= 09/2026` cobrada en agosto
When se procesa la ingesta
Then **no** se cancela ni se modifica la SI de septiembre existente
And se crea un `Payment Entry` de **anticipo no aplicado** (sin references /
  unallocated) a favor del socio con `posting_date = fecha_pago` de agosto
And el monto cuenta en el total de control de agosto.

---

## Scenario: CARNET

Given concepto CARNET
When se procesa
Then no se factura ni se crea PE de imputación
And la fila queda `excluido_carnet` en el log
And su `monto_csv` entra en el total de control (no-pérdida).

---

## Scenario: validaciones finales obligatorias

Given apply completado (o dry-run del plan)
When termina
Then imprime:
  1. Total dinero del CSV / contabilizado en agosto = **52.115.308,00**
  2. Registros procesados = **2.562**
  3. Integridad septiembre: `sept_si_count` / `sept_pe_count` sin cambio
And si (1) o (2) no cuadran en apply sobre el CSV completo, falla con rollback.

---

## Scenario: gate apply

Given site de producción
When `dry_run=False` sin `confirm='PURGE_MIGRATE_PROD'`
Then ValidationError y no muta.

Given site local
When apply sin `confirm='local-dev'`
Then ValidationError.

---

## Scenario: atomicidad

Given apply
When cualquier paso (purga, facturación o cobro) falla
Then se hace `ROLLBACK` de toda la corrida
And los conteos de septiembre siguen iguales al snapshot
And no quedan lotes a medias (sin `commit` intermedio fuera de test).

---

## Scenario: limpieza de mora huérfana (site-wide)

Given SI de ajuste `*-MORA` / remarks `Mora al cobro …` con `outstanding > 0`
And la SI origen está **Paid** o **Cancelled**
And no hay Payment Entry **submitted** contra esa mora
When `cancelar_mora_huerfanas` (dry-run o apply con confirm)
Then lista / cancela esas SI
And **no** cancela mora con origen aún impago ni con PE submitted
And opcionalmente filtra por `socio`.

---

## Scenario: revisión post-corridas fallidas (producción)

Given producción tuvo apply parciales previos (SI/PE duplicados, mora con
  `posting_date` en septiembre, filas CSV sin PE)
When se corre inventario readonly antes del apply limpio
Then se registran: snapshot septiembre, universo purga ≤31/08, mora huérfana,
  mora posteada en sept, filas sin PE, duplicados históricos y PE INF en sept
And la purga principal **no** cancela docs con `posting_date >= 2026-09-01`
And la basura de mora en septiembre se limpia después con
  `run_prod_cancelar_mora_huerfanas` (tras dry-run)
And `retry_sin_pe` / FLEX se aplican solo si el inventario lo justifica
And los conteos de septiembre productivos no cambian.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Script | `scripts/purge_historical_data_pre_september.py` |
| Tests | `tests/test_purge_historical_data_pre_september.py` |
| Wrappers prod | `run_prod_dry`, `run_prod_apply`, `run_prod_retry_sin_pe`, `run_prod_recrear_flex`, `run_prod_cancelar_mora_huerfanas` |

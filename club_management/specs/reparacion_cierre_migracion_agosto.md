# Spec: Reparación cierre migración agosto 2026

Cierre operativo tras la conciliación CSV↔PE: limpiar **mora residual
huérfana**, reimputar filas con **alias de padrón** y **facturar+aplicar**
los adelantos `09/2026` que quedaron en `sin_pe_inf`.

**Relacionado:** `conciliacion_migracion_agosto.md`,
`purga_migracion_historica_pre_septiembre.md`, `recargos_mora_dos_tramos.md`

```text
bench --site SITE execute \
  club_management.scripts.reparar_cierre_migracion_agosto.run \
  --kwargs '{"csv_path":"/tmp/cobranzas_bulk_erp_agosto_2026.csv","dry_run":true}'

bench --site SITE execute \
  club_management.scripts.reparar_cierre_migracion_agosto.run_prod \
  --kwargs '{"dry_run":false}'
```

---

## Scenario: mora residual huérfana (origen cerrado)

Given una SI de mora (`periodo *-MORA` o remarks `Mora al cobro …`)
  con `outstanding > 0`
And la SI origen está Paid / Cancelled / inexistente
And el socio figura entre los del CSV de agosto (imputados)
When corre la reparación de mora
Then si la mora **no** tiene PE submitted → se **cancela** la SI de mora
And si la mora tiene PE parcial submitted → se emite **Credit Note** por el
  outstanding residual (no se toca el PE ya aplicado)
And tras apply, esa mora queda con `outstanding ≈ 0` (o `docstatus=2`)
And no se tocan moras cuyo origen sigue impago.

---

## Scenario: alias de padrón CSV → Socio

Given el CSV trae `nro_socio=12009` y el padrón real es Socio `9484`
And el CSV trae `nro_socio=11755` y el padrón real es Socio `3838`
When se resuelven filas para reimputación
Then `find_socio` usa el alias y la fila deja de ser `socio_no_encontrado`
And se factura (si falta) e imputa el cobro con `fecha_pago` del CSV
  contra el Socio canónico.

---

## Scenario: facturar y aplicar `sin_pe_inf` de período 09/2026

Given filas CSV con `periodo=09/2026` cobradas en agosto sin PE `INF-*`
And el socio existe
When corre la reparación de adelantados
Then si ya hay SI del concepto/período → solo se aplica el cobro
And si no hay SI → se emite SI del período (`rate` = monto CSV, sin mora)
  y se aplica el Payment Entry con `posting_date = fecha_pago`
And la fila **no** queda como anticipo unallocated ni como `excluido_adelantado`
And CARNET sigue excluido
And `nro_socio=12062` sin alias conocido queda en error (no inventar socio).

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Script | `scripts/reparar_cierre_migracion_agosto.py` |
| Tests | `tests/test_reparar_cierre_migracion_agosto.py` |
| Mora helpers | `scripts/purge_historical_data_pre_september.py` (`inventariar` / `limpiar`) |

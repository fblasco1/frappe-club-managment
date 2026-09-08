---
name: carga-masiva-meses
description: >-
  Carga masiva de cobranzas de un mes (informe Excel o CSV) vía pipeline
  cobranza_informe / bulk_payments, con prep CTO COMP, mora, dry-run y apply
  local/prod. Usar al pedir cargar mes, apply cobranzas, pipeline informe,
  migración histórica de un período, o conciliación CSV↔PE.
---

# Carga masiva de cobranzas por mes

Specs canónicas:

- `club_management/specs/carga_masiva_cobranzas.md`
- `club_management/specs/plantilla_carga_cobranzas.md`
- `club_management/specs/informe_concepto_cobranza.md`

## Regla de oro

**Una fila = un concepto cobrado = un Payment Entry.**  
Cuota + arancel del mismo socio/mes → **dos filas**.

## Formato de entrada (preferido)

Excel **INFORME DE COBRANZAS** (Secretaría):

1. Celda A1: `INFORME DE COBRANZAS`
2. Bloques `CONCEPTO: <nombre exacto>`
3. Columnas: Fecha | Nro socio | … | Período | Importe | … | Nota (`tra` → Transferencia)

Nombres de concepto: ver `informe_concepto_cobranza.md` (cuotas, tiras, C FED, CTO COMP, adicionales).

CSV plano alternativo: `nro_socio,monto_abonado,fecha_pago,medio_pago,periodo,concepto,referencia_comprobante`.

## Pipeline operativo (mes en curso / informe)

Orden fijo — `club_management.scripts.cobranza_informe_prod_pipeline.run`:

1. Parche tarifas cuota impagas  
2. Sync PLE cuota social  
3. Refacturas puntuales del informe  
4. Alta cargo CTO COMP  
5. Facturar CTO COMP  
6. Facturar cuota complementaria pendiente  
7. Dry-run apply → detectar `sin_factura`  
8. Facturar sin_factura  
9. Dry-run control  
10. Apply cobranzas (si `dry_run=False`)

### Local

```bash
bench --site dev.localhost execute \
  club_management.scripts.cobranza_informe_prod_pipeline.run \
  --kwargs '{
    "csv_path": "/ruta/Cobranza MM.xlsx",
    "dry_run": true,
    "log_dir": "/tmp/cobranza_pipeline",
    "periodos_cto_comp": ["MM/YYYY"]
  }'
```

Apply local: `"dry_run": false, "confirm": "local-dev"`.

### Producción

Confirm token: **`APPLY_PROD`** (gate en `bulk_io.ensure_bulk_apply_allowed`).

```bash
bench --site gestion.icdpedroechague.com.ar execute \
  club_management.scripts.cobranza_informe_prod_pipeline.run \
  --kwargs '{
    "csv_path": "/tmp/Cobranza.xlsx",
    "dry_run": false,
    "confirm": "APPLY_PROD",
    "log_dir": "/tmp/cobranza_pipeline",
    "periodos_cto_comp": ["MM/YYYY"]
  }'
```

Siempre: **dry-run primero**, revisar `*.inconsistencias.csv`, recién después apply.

## Migración histórica (cutoff mes cerrado)

Solo cuando hay que **purgar y reimputar** un mes ya migrado mal:

- Script: `purge_historical_data_pre_september.py` (adaptar cutoff/CSV del mes)
- Confirm prod: **`PURGE_MIGRATE_PROD`**
- Post: `conciliacion_migracion_agosto.py` (patrón CSV↔PE `INF-*`)
- Reparos: `reparar_cierre_migracion_agosto.py`, `alinear_pe_monto_distinto.py`

Reglas aprendidas:

- C FED / CTO COMP **no** aplican mora
- Gap CSV (base+mora) vs PE INF (solo base) se cierra con PE mora del mismo origen → `ok_con_mora`
- Idempotencia por `referencia_comprobante` / `INF-*`
- No tocar SI/PE del mes vivo (septiembre+) sin gate explícito

## Checklist por mes nuevo

1. Spec/periodo: actualizar `periodos_cto_comp` y paths del archivo  
2. Dry-run pipeline → inconsistencias  
3. Resolver `socio_no_encontrado` / `monto_discordante` / `sin_factura`  
4. Apply con token correcto  
5. Conciliación opcional (totales CSV vs PE por concepto)  
6. Actualizar bitácora DevLog  

## Deploy

Código a prod: commit + push `mvp/secretaria-2026-06` + `scripts/prod/deploy-club-management.sh`  
(no dejar solo `docker cp` salvo hotfix urgente).

## No hacer

- Inventar endpoints Cobrand/Supervielle sin doc API  
- Apply en prod sin dry-run ni backup reciente  
- Mezclar cuota+arancel en una sola fila del informe  
- Commitear artefactos `tmp_*` / CSV de conciliación local  

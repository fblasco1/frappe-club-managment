# Spec: Carga masiva de cobranzas del mes

Secretaría carga un CSV/Excel de cobros del período (mes en curso o indicado)
y el sistema genera `Payment Entry` imputados a las `Sales Invoice` impagas,
con mora al cobro y sin duplicar comprobantes.

**Relacionado:** `recargos_mora_dos_tramos.md`, `registrar_cobro_fecha.md`,
`cobro_multi_factura_medios_mixtos.md`, `flujo_cobranzas.md`

Ejecución (solo local / con `pause_scheduler` y `mute_emails`):

```text
bench --site dev.localhost execute club_management.scripts.bulk_payments.run \
  --kwargs '{"csv_path": "/ruta/cobranzas.csv", "dry_run": true}'
```

---

## Input

Columnas mínimas (alias aceptados entre paréntesis):

| Columna | Descripción |
|---------|-------------|
| `nro_socio` (`numero_socio`) **o** `dni` | Identificación del socio |
| `monto_abonado` (`monto`) | Importe cobrado |
| `fecha_pago` | Fecha real del cobro (`YYYY-MM-DD` o `DD/MM/YYYY`) |
| `medio_pago` | Efectivo, Transferencia, Tarjeta crédito/débito, Cheque |
| `referencia_comprobante` (`referencia`) | N° de recibo/comprobante (idempotencia) |

Opcional: `periodo` (`MM/YYYY`) por fila; si falta, se usa el período de la corrida.

---

## Scenario: dry-run no persiste

Given un CSV con un socio Activo y factura impaga del período
When se ejecuta `run` con `dry_run=True`
Then no se crea `Payment Entry`
And el reporte incluye la fila como `ok` (simulada) con monto exigido y facturas.

---

## Scenario: socio no encontrado

Given una fila con `nro_socio` / `dni` inexistente
When se procesa
Then la fila queda en inconsistencias `socio_no_encontrado`
And no se crea documento.

---

## Scenario: imputación al período con mora

Given factura(s) impaga(s) del período emitidas el día 1
And `fecha_pago` posterior al 1.er vencimiento (día 10) y hasta el día 20
When el `monto_abonado` coincide con el total exigido (cuota/arancel × 1,10, tolerancia configurable)
Then se crea `Payment Entry` submitted imputado a esas SI
And se aplica mora al cobro (`preparar_facturas_cobro_con_mora`)
And el centro de costo queda el de cada factura (Cuotas Sociales vs. Actividad).

---

## Scenario: cruce por concepto del informe (línea)

Given una SI multi-línea (cuota + arancel) impaga del período
And una fila con `concepto` del informe (p. ej. «Adicional Basquet Escuelita»)
When el monto abonado coincide con el exigido de **esa línea** (con mora si aplica)
Then se imputa un cobro **parcial** contra la SI por ese importe
And no exige el total cuota+arancel.

Ver spec detallada: `informe_concepto_cobranza.md`.

---

## Scenario: monto discordante

Given el `monto_abonado` no coincide (fuera de tolerancia) ni con el total exigido del período ni con una SI individual
When se procesa
Then inconsistencia `monto_discordante`
And no se crea `Payment Entry`.

---

## Scenario: idempotencia por comprobante

Given ya existe un `Payment Entry` submitted con el mismo `referencia_comprobante` para el socio
When se vuelve a procesar la fila
Then se omite como `ya_procesado`
And no se duplica el cobro.

---

## Scenario: facturas ya saldadas

Given el socio no tiene SI impagas del período
When se procesa un cobro
Then inconsistencia `sin_factura_impaga` (o `ya_saldada` si hay SI del período en cero **con la línea de ese concepto**)
And no se crea PE.

`ya_saldada` **no** se usa solo porque exista otra factura del período (p. ej. cuota ya cobrada): si el concepto del informe no está en ninguna SI, el código es `sin_factura_impaga`.

---

## Scenario: mora al cruce por concepto

Given una SI impaga de cuota/arancel
And una fila del informe con monto que incluye mora (+10 % o +15 % según tramo)
When `bulk_payments` cruza por concepto con `fecha_pago` posterior al 2.º vencimiento
Then acepta el match vía `calcular_exigido_linea_factura`, monto de línea facturado
  o total de `previsualizar_cobro_con_mora`
And al aplicar usa `registrar_cobro_compuesto` (ajuste de mora + cobro).

---

## Scenario: auto-submit configurable

Given `auto_submit=False`
When el cobro es válido
Then el `Payment Entry` queda en Draft (`docstatus=0`).

Given `auto_submit=True` (default)
Then el PE queda Submitted.

---

## Scenario: error de cobranza menor −$500 (pre-agosto)

Given una fila «Cuota Social Menor» con período anterior a 08/2026
And el `monto_abonado` es exactamente $500 menor que el exigido con mora 15 %
When se cruza por concepto
Then se acepta el cobro parcial por el monto informado
And la SI puede quedar con saldo residual de $500.

---

## Scenario: fallo de cobrador mora 10 % vs 15 %

Given una línea de arancel con mora 15 % exigible al cobro
And el informe trae el importe con mora 10 % sobre la misma base
When se cruza por concepto
Then se tolera el fallo del cobrador e imputa el monto informado.

---

## Scenario: saldo a favor por excedente ≤ $500

Given el `monto_abonado` supera el exigido de la línea en hasta $500
When se aplica el cobro
Then se imputa el exigible a la factura
And el excedente se registra como saldo a favor del socio.

---

## Scenario: dos conceptos contra la misma SI multi-línea

Given una SI del período con cuota social + arancel (p. ej. $28.500 + $28.500)
And el informe trae primero «Cuota Social Menor» $28.500 y después «PRE-MINI A U9» $29.000
When se aplica la carga masiva
Then ambos cobros se imputan a la **misma** SI (parcial + parcial)
And la SI queda saldada (o con excedente ≤ $500 como saldo a favor)
And **no** se reserva la factura completa tras el primer renglón: solo se reserva cuando `outstanding` llega a 0.

---

## Scenario: boxeo informe 3 veces

Given el informe dice «BOXEO 3 VECES»
When se resuelve el ítem
Then el candidato es `ICDPE-BOXEO-3-CLASES`
And si la factura tenía otro ítem de boxeo se refactura antes del cobro.

---

## Scenario: fecha futura rechazada

Given `fecha_pago` posterior a hoy
When se procesa
Then inconsistencia `fecha_invalida`.

---

## Scenario: reporte de auditoría

Given una corrida (dry-run o apply)
When termina
Then el resultado incluye: filas procesadas, monto total cobrado, facturas saldadas, lista de inconsistencias
And se puede persistir un JSON de log en `log_path`.

---

## Importer consolidado con invariante de no-pérdida (`cobranzas_bulk_importer`)

Reemplaza el pipeline multi-script para el CSV consolidado del mes
(`nro_socio, monto_abonado, fecha_pago, medio_pago, periodo, concepto, referencia_comprobante`).
Resuelve facturación e imputación **fila por fila, inline** (sin pasos previos de
facturación por script separado) y garantiza que ninguna fila se descarte sin registro.

### Scenario: CARNET excluido

Given una fila con concepto `CARNET`
When se procesa
Then el estado es `excluido_carnet`
And no se crea Payment Entry
And el log incluye `nro_socio`, `socio` y `monto_csv`.

### Scenario: invariante de no-pérdida

Given un CSV de N filas con suma total T
When se ejecuta `cobranzas_bulk_importer.run` (dry-run o apply)
Then el log de auditoría tiene exactamente N registros
And la suma de `monto_csv` del log es exactamente T
And cada registro tiene un estado terminal explícito.

### Estados terminales

| Estado | Significado |
|--------|-------------|
| `imputado` | PE creado y aplicado a la línea del concepto |
| `imputado_con_facturacion` | Se emitió SI de una línea para el concepto faltante y se cobró |
| `imputado_con_saldo_favor` | Se imputó hasta el outstanding y el excedente quedó a favor (`-SF`) |
| `ya_imputado` | Idempotencia: PE existente con la referencia INF de la fila |
| `error_socio_no_encontrado` | `nro_socio`/`dni` sin match en `Socio` |
| `excluido_carnet` | Fila CARNET: no se imputa; queda en log de revisión manual |
| `excluido_adelantado` | Período posterior al mes de cobro: se resetea el PE/SI si existían; no se reimputa |
| `error_concepto_sin_mapeo` | `resolver_item_codes_concepto` vacío (no CTO COMP) |
| `error_facturacion` | Falló la emisión de la SI del concepto |
| `error_cobro` | ValidationError al registrar el PE |

No existe skip silencioso: `ya_procesado` del importer legado se registra como `ya_imputado`.

### Scenario: el CSV manda el monto

Given una fila con `monto_abonado` M y línea de factura del concepto con outstanding O < M
When se aplica el cobro
Then se imputa O a la SI (más la SI de mora vinculada del concepto si existe)
And el resto (M − imputado) queda como saldo a favor con referencia `…-SF`
And `monto_imputado + saldo_favor = M` en el log.

### Scenario: auto-facturación inline por concepto

Given una fila cuyo concepto no tiene línea en ninguna SI del período
And el concepto resuelve a un `item_code` (arancel de inscripción, cuota por categoría,
  federativa o cargo)
When se aplica
Then se emite una SI de una línea (`item_code`) con `periodo_cobro` de la fila
And el **rate es la base sin mora** (`monto_csv / (1 + mora_pct/100)`, o tarifa
  congelada de patín agosto si aplica)
And la mora se genera al cobro (SI de mora vinculada), no embebida en el rate
And se cobra contra esa SI en la misma corrida
And el estado es `imputado_con_facturacion`.

Para CTO COMP se factura vía cargo socio (`prepagar_cargo_socio`), creando el
cargo si no existe.

### Scenario: apply post-reset sin reconciliar

Given el universo del CSV fue cancelado (`reset_cobranzas_csv`)
When `apply_prod_agosto` (o `run` con `reconcile=False`, `auto_facturar=True`)
Then no busca PE previos para “corregir”
And factura e imputa cada fila elegible una sola vez.

### Scenario: mora sobre valor facturado

Given una línea de arancel facturada a $28.500 con tarifa vigente distinta
And `fecha_pago` en tramo `post_primer` (día 11–20 del mes del período)
When el importer calcula la mora esperada
Then usa base **facturada** ($28.500 × 1,10 = $31.350), no el valor vigente
And si el `monto_abonado` difiere de la mora esperada se registra `diferencia_mora`
  en el log pero **se imputa igual** el monto del CSV.

Tramos (`mora_al_cobro.resolver_tramo_mora`, sobre el mes del `periodo`):
día 1–10 sin mora; 11–20 +10 %; 21+ (incluye período vencido pagado en mes
posterior) +15 %. Período adelantado (mes futuro) sin mora.

### Scenario: idempotencia determinista por fila

Given la referencia `INF-{fila}-{socio}-{periodo}-{monto}-{concepto}` de una fila ya aplicada
When se re-ejecuta el importer sobre el mismo CSV
Then la fila queda `ya_imputado` sin crear PE nuevo
And los totales del log no cambian.

### Scenario: modo reconciliador

Given un PE existente imputado a la SI del concepto con referencia INF **incorrecta**
  (fila/concepto mal etiquetados) pero mismo socio, período, monto y fecha
When se ejecuta con `reconcile=True`
Then se corrige `reference_no` del PE a la referencia canónica de la fila
And la fila queda `ya_imputado` (con nota `referencia_corregida`)
And no se duplica el cobro.

### Scenario: log de auditoría fila a fila

Given una corrida
When termina
Then existe `<csv>.auditoria.csv` con columnas
  `fila, nro_socio, socio, fecha_pago, periodo, concepto, monto_csv, estado,
  item_code, sales_invoice, sales_invoice_emitida, payment_entry, monto_imputado,
  mora_pct_esperado, mora_monto, sales_invoice_mora, saldo_favor, mensaje`
And un `<csv>.resumen.json` con conteos por estado y totales de control
  (total CSV, total imputado, total saldo a favor, total en error).

### Scenario: cuadratura contable

Given el CSV consolidado de agosto 2026 (2.562 filas, $52.115.308,00)
When corre `verificar_cuadratura_cobranzas.run` sobre el log de auditoría
Then valida filas = 2.562 y `Σ monto_csv` = $52.115.308,00
And `Σ monto_imputado + Σ saldo_favor + Σ monto en error + Σ excluido_carnet` = `Σ monto_csv`
And reporta el detalle de filas en estado de error (si las hay).

---

## Reset limpio (agosto 2026)

Cuando los PE/SI quedaron partidos por parches, no se repara socio a socio:
ver spec `reset_cobranzas_csv.md` (cancela universo del CSV, incluye julio
cobrado en agosto y cargos extra; no toca SI `09/2026` mensual).

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Script legado | `scripts/bulk_payments.py` |
| Importer consolidado | `scripts/cobranzas_bulk_importer.py` |
| Diagnóstico read-only | `scripts/diagnostico_cobranzas_csv.py` |
| Verificador de cuadratura | `scripts/verificar_cuadratura_cobranzas.py` |
| Reimputación arancel omitido | `scripts/reapply_informe_arancel_omitido.py` |
| Pipeline prod (legado) | `scripts/cobranza_informe_prod_pipeline.py` |
| Tests | `tests/test_bulk_payments.py`, `tests/test_cobranzas_bulk_importer.py` |

---

## Scenario: gate apply producción

Given el site es `gestion.icdpedroechague.com.ar`
When se ejecuta apply (`dry_run=False`) sin confirmación
Then falla con ValidationError
And exige `confirm='APPLY_PROD'`.

---

## Scenario: gate apply local

Given el site es `dev.localhost`
When se ejecuta apply sin confirmación
Then falla con ValidationError
And exige `confirm='local-dev'`.

---

## Pipeline producción (informe Excel)

Given el informe `Cobranza 01 a 28-08.xlsx` en el servidor
And backup reciente de la base de producción
When se ejecuta `cobranza_informe_prod_pipeline.run` con `dry_run=True`
Then corre en simulación: parche tarifas, sync PLE, refacturas, altas/facturas CTO COMP, dos dry-run apply
And no crea Payment Entry.

When el dry-run final muestra ≤10 `monto_discordante` (casos manuales acordados)
And Francisco confirma apply
Then `dry_run=False`, `confirm='APPLY_PROD'` imputa cobranzas
And persiste log en `log_dir/pipeline_summary.json`.

Pasos manuales post-apply: **28 filas** no imputables — ver `docs/club/cobranza-informe-manual-prod.md`:

- **10** `monto_discordante` (Cuota Social Menor)
- **17** `socio_no_encontrado`
- **1** `fecha_invalida`

Comando prod (dry-run):

```text
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.cobranza_informe_prod_pipeline.run \\
  --kwargs '{"csv_path": "/tmp/Cobranza 01 a 28-08.xlsx", "dry_run": true, "log_dir": "/tmp/cobranza_pipeline"}'
```

Apply (solo tras OK dry-run + backup):

```text
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.cobranza_informe_prod_pipeline.run \\
  --kwargs '{"csv_path": "/tmp/Cobranza 01 a 28-08.xlsx", "dry_run": false, "confirm": "APPLY_PROD", "log_dir": "/tmp/cobranza_pipeline"}'
```

Prep datos sin apply: `skip_apply=True` con el mismo `confirm`.

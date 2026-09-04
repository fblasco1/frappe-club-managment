# Plantilla: carga masiva de cobranzas (bulk exacto)

Guía para armar un archivo que `bulk_payments.run` / `cobranza_informe_prod_pipeline.run`
pueda aplicar **sin prorrateos ni conceptos ambiguos**.

**Relacionado:** `carga_masiva_cobranzas.md`, `informe_concepto_cobranza.md`

---

## Regla de oro

**Una fila = un concepto cobrado = un Payment Entry.**

Si el socio pagó cuota **y** arancel en el mismo mes, van **dos filas** (aunque compartan
la misma Sales Invoice en el sistema):

| Fila | concepto (ejemplo) | monto típico agosto 2026 |
|------|-------------------|--------------------------|
| 1 | Cuota Social Menor | $28.500 (+ mora si aplica) |
| 2 | PRE-MINI A U9 | $28.500 o $29.000 según informe |

---

## Formato A — Excel «INFORME DE COBRANZAS» (recomendado)

Es el que ya usa Secretaría. El parser está en `scripts/informe_cobranzas.py`.

### Estructura

1. Celda A1: **`INFORME DE COBRANZAS`**
2. Bloques por concepto:

```text
CONCEPTO: Cuota Social Menor
Fecha     | Nro socio | … | Período   | Importe | … | Nota
2026-08-05| 10800     | … | AGOSTO 26 | 28500   | … | tra
2026-08-12| 10849     | … | AGOSTO 26 | 32775   | … |
Subtotales …

CONCEPTO: PRE-MINI A U9
Fecha     | Nro socio | … | Período   | Importe | … | Nota
…
```

### Columnas usadas (índice 0-based del Excel)

| Col | Campo | Obligatorio |
|-----|-------|-------------|
| 0 | Fecha de pago | Sí |
| 1 | Número de socio | Sí |
| 3 | Período (`AGOSTO 26`, `AGOSTO 2026`, `08/2026`) | Recomendado |
| 4 | Importe cobrado | Sí |
| 8 | Nota (`tra` → Transferencia; resto → Efectivo) | Opcional |

El sistema genera solo:

- `referencia_comprobante`: `INF-{fila}-{socio}-{MM/YYYY}-{monto}-{concepto[:24]}`
- `concepto`: texto exacto del bloque `CONCEPTO: …`
- `periodo`: derivado de col. 3 o de la fecha

### Nombres de concepto válidos (agosto)

Usar **exactamente** estos textos (ver tabla completa en `informe_concepto_cobranza.md`):

- Cuota: `Cuota Social Activo`, `Cuota Social Menor`, `Cuota Social Adherente`, …
- Básquet tira: `PRE-MINI A U9`, `MINI A U11`, `INFA A U13`, `CADETES A U15`, `JUVENILES A U17`, `LIGA APROX A U21`, …
- Adicionales: `Adicional Basquet Escuelita`, `Adicional Voley Menor`, …
- Federativas: `C FED U9/U11 MASC/FEM`, `C FED U15/U17 MASC`, `CUOTA FEDER VOLEY`, …
- Complementarias: `CTO COMP BASQ TIRA A/B/FLEX`, `CTO COMP VOLEY ESC`, …

**No mezclar** cuota + arancel en una sola fila.

---

## Formato B — CSV plano (alternativa)

Primera fila = encabezados. Una fila por cobro.

```csv
nro_socio,monto_abonado,fecha_pago,medio_pago,periodo,concepto,referencia_comprobante
10800,28500,2026-08-03,Efectivo,08/2026,Cuota Social Menor,
10800,29000,2026-08-03,Efectivo,08/2026,PRE-MINI A U9,
10849,28500,2026-08-05,Transferencia,08/2026,Cuota Social Menor,
10849,28500,2026-08-05,Transferencia,08/2026,INFA A U13,
```

| Columna | Obligatorio | Notas |
|---------|-------------|-------|
| `nro_socio` o `dni` | Sí | Debe existir en `Socio` |
| `monto_abonado` | Sí | Coincide con línea + mora (tolerancia $1) |
| `fecha_pago` | Sí | `YYYY-MM-DD` o `DD/MM/YYYY`; no futura |
| `medio_pago` | Sí | Efectivo, Transferencia, Tarjeta crédito/débito, Cheque |
| `periodo` | Recomendado | `08/2026` para agosto |
| `concepto` | **Sí** | Texto del informe (ver spec concepto) |
| `referencia_comprobante` | Opcional | Si vacío, se autogenera en Excel informe; en CSV conviene `INF-…` único |

---

## Checklist antes de apply (agosto completo)

1. **Facturación previa:** cada socio/concepto con deuda debe tener SI del `08/2026`
   (pipeline: `facturar_sin_factura`, `facturar_cto_comp`, etc.).
2. **Dry-run:** `dry_run=True` → revisar inconsistencias:
   - `sin_factura_impaga` → falta SI o concepto mal escrito
   - `monto_discordante` → monto no coincide con línea + mora
   - `ya_procesado` → comprobante duplicado (OK, idempotente)
3. **Apply:** `confirm='APPLY_PROD'` en prod o `local-dev` en dev.
4. **Repetir** dry-run post-apply: inconsistencias solo casos manuales (C FED sin SI, etc.).

### Comando pipeline (agosto)

```text
bench --site gestion.icdpedroechague.com.ar execute \\
  club_management.scripts.cobranza_informe_prod_pipeline.run \\
  --kwargs '{
    "csv_path": "/tmp/Cobranza-agosto.xlsx",
    "dry_run": true,
    "log_dir": "/tmp/cobranza_pipeline"
  }'
```

---

## Scenario: etiqueta informe no confunde arancel con cuota

Given una SI multi-línea cuota + arancel
And el reporte prorratea un PE sin `INF-…`
When se etiqueta la línea de arancel `ICDPE-BASQUET-…`
Then la etiqueta **no** es «Cuota Social Menor» por categoría del socio
And el subtotal por concepto en rendición refleja aranceles aparte.

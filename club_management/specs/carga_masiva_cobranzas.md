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
Then inconsistencia `sin_factura_impaga` (o `ya_saldada` si hay SI del período en cero)
And no se crea PE.

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

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Script | `scripts/bulk_payments.py` |
| Tests | `tests/test_bulk_payments.py` |

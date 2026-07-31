# Spec índice: Flujo de cobranzas

Mapa del ciclo completo de facturación y cobro en Desk. Cada capacidad apunta a su spec
detallada (Given/When/Then).

**Última revisión:** 2026-07-29

---

## Capacidades

| # | Capacidad | Spec | Estado |
|---|-----------|------|--------|
| 1 | Generar facturación del mes (job día 1 + Generar cargo Desk) | `cobranza_periodica_mensual.md`, `mvp_operacion_secretaria_sin_pagos.md` | Hecho |
| 2 | Generar facturación de **meses anteriores** (alta de deuda histórica) | `facturacion_meses_anteriores.md` | **Hecho** (2026-07-30) |
| 3–4 | Mora al cobrar: hasta día 10 sin %; hasta fin de mes +10 %; después cuota mes pago +15 % | `recargos_mora_dos_tramos.md` | **Hecho** (2026-07-30) |
| 5 | Cargos extras (único / recurrente: federativa, campus, viaje, etc.) | `cargo_extra_socio.md`, `cargo_extra_conceptos_y_facturacion.md` | Hecho |
| 6 | Registrar cobro eligiendo conceptos + medios mixtos (Efectivo, Transferencia, TC, TD) | `cobro_multi_factura_medios_mixtos.md` | Hecho |
| 7 | Cobrar **meses hacia adelante** en cargos extras (cancelación total / prepago) | `cargo_extra_prepago_adelantado.md` | **Hecho** (2026-07-30) |

**Relacionado:** `deuda_socio_desk.md`, `registrar_cobro_fecha.md`, `recibo_pago_escpos.md`,
`moroso_automatico.md`, `centro_costo_arancel_actividad.md`

---

## Modelo operativo (actual)

```
Día 1 (configurable)     →  emitir SI por concepto (cuota, arancel, cargo recurrente)
Día 10 (1.er venc.)      →  due_date; umbral del +10 % al cobrar
Al registrar cobro       →  según vencimientos del período adeudado:
                             ≤ día 10: sin mora
                             ≤ fin de mes: +10 %
                             después: valor mes de pago × 1,15
Secretaría               →  Generar cargo / Registrar cobro / Cargo Socio
```

Medios Desk: Efectivo (`Cash`), Transferencia (`Wire Transfer`), Tarjeta crédito
(`Credit Card`), Tarjeta débito (`Bank Draft`), Cheque.

---

## Decisiones de mora (cerradas)

Fórmula: tramos sobre el **período de la factura**

| Momento de pago | Recargo | Base |
|-----------------|---------|------|
| Hasta 1.er venc. (`dia_primer_vencimiento`, default 10) | 0 % | Saldo |
| Tras 1.er y hasta 2.º (`dia_segundo_vencimiento`, default fin de mes) | +10 % (`recargo_post_vencimiento_pct`) | Valor vigente |
| Tras 2.º vencimiento | +15 % (= 10 %+5 %) | **Cuota del mes de pago** |

Ejemplo: debe marzo, paga en abril (cuota abril 12) → `12×1,15`. Mismo mes el 15 → +10 % solamente.

Detalle: `recargos_mora_dos_tramos.md`.

---

## Orden de implementación sugerido (SDD → TDD)

1. ~~Mora al cobro (`recargos_mora_dos_tramos.md`) + config Club Settings.~~ **Hecho**
2. ~~`facturacion_meses_anteriores.md` (UI período en Generar cargo + batch ops).~~ **Hecho**
3. ~~`cargo_extra_prepago_adelantado.md`.~~ **Hecho**

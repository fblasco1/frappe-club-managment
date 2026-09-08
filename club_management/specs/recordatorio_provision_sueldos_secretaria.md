# Spec: Recordatorio provisión de sueldos (Secretaría)

El último día hábil de cada mes, Secretaría debe ver en el panel del workspace un aviso para generar las **Purchase Invoice** de provisión de sueldos y cargas (sin HRMS).

**Relacionado:** `carga_rapida_ingreso_egreso.md`, `secretaria_workspace_panel_kpis.md`

---

## Scenario: último día hábil del mes

Given la fecha de referencia es el **último día hábil** del mes (lun–vie y **sin feriados**)
When Secretaría abre el workspace **Secretaría**
Then el panel muestra un banner de provisión de sueldos.

---

## Scenario: el último día del mes lun–vie es feriado (GF-6)

Given el último día lun–vie del mes está marcado como feriado en la **Holiday List** de la empresa
When se calcula el último día hábil
Then se devuelve el día hábil **anterior** (salteando feriados y fines de semana)
And el banner se muestra ese día hábil anterior, no el feriado.

---

## Scenario: sin Holiday List configurada (GF-6)

Given la empresa no tiene `default_holiday_list` ni se pasan feriados
When se calcula el último día hábil
Then se consideran solo fines de semana (comportamiento previo, sin romper).

---

## Scenario: no es último día hábil

Given la fecha no es el último día hábil del mes
When Secretaría consulta el panel
Then el banner **no** se muestra (`mostrar = false`).

---

## Scenario: lista conceptos pendientes

Given es último día hábil y no existe PI del mes para «Sueldos del personal»
When se arma el recordatorio
Then `conceptos_pendientes` incluye ese concepto con proveedor, ítem y etiqueta
And no incluye conceptos que ya tienen PI submitted del mes (por ítem).

---

## Scenario: todos los conceptos cargados

Given es último día hábil y todas las PI de provisión del mes ya existen
When se arma el recordatorio
Then `mostrar = true` y `conceptos_pendientes` está vacío
And el mensaje indica que la provisión del mes está completa.

---

## Conceptos de provisión (catálogo fijo)

| Etiqueta | Proveedor | Ítem |
|----------|-----------|------|
| Sueldo Personal Administrativo | ICDPE-Sueldos Personal | ICDPE-FIN-SUELDO-ADMIN |
| Formulario 931 ARCA | ICDPE-AFIP 931 | ICDPE-FIN-CARGAS-931 |
| ART (Aseguradora de Riesgos del Trabajo) | ICDPE-ART | ICDPE-FIN-ART |
| Cuota Sindical UTEDYC y CCT | ICDPE-UTEDYC | ICDPE-FIN-UTEDYC |
| Honorario Entrenador / Director Técnico | ICDPE-Sueldos Personal | ICDPE-FIN-HON-ENTRENADOR |

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `finance/services/recordatorio_sueldos.py` |
| Panel payload | `members/services/secretaria_workspace_panel.py` |
| UI | `public/js/secretaria_workspace_panel.js` |
| Tests | `tests/test_recordatorio_sueldos.py` |

---

## GF-6: feriados AR y copy

- El cálculo del último día hábil considera **feriados** además de fines de semana.
- Fuente de feriados: **Holiday List** de la empresa (`default_holiday_list` de la Company, mantenible en Desk por Secretaría). Si no hay lista, se cae al comportamiento previo (solo fines de semana).
- El core `get_ultimo_dia_habil_mes(reference_date, holidays=...)` acepta feriados inyectables para tests puros.
- Copy: el mensaje del banner usa **«factura de compra»** (no «Purchase Invoice»).

### Holiday List de Argentina (seeding)

- `finance/setup/feriados_argentina.py` define los feriados nacionales (Ley 27.399) y días no laborables con fines turísticos (Resolución 164/2025) por año.
- **No** incluye días no laborables de colectividades (judía, islámica, armenia): no son feriados nacionales.
- El patch `seed_holiday_list_ar_2026` crea la `Holiday List` «Feriados Argentina 2026» (idempotente) y la asigna como `default_holiday_list` de las empresas de Argentina que no tengan una elección manual.
- **Fuente:** https://www.argentina.gob.ar/feriados.
- **Mantenimiento anual:** agregar el año siguiente en `FERIADOS_POR_ANIO` (con puentes ya resueltos por decreto) y un patch análogo.

### Pendiente de validación con Secretaría

- Revisar copy, lista de conceptos y CTA con un usuario real de Secretaría.

## GF-7 (hecho)

- Reemplazar todo texto visible en inglés por español argentino (ej. «Nueva factura de compra» en lugar de «Nueva Purchase Invoice»).

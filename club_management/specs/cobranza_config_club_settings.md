# Spec: Configuración de cobranza periódica en Club Settings

Parámetros del calendario mensual de deuda, vencimientos y recargo.

**Relacionado:** `cobranza_periodica_mensual.md`, `cobranza_recargo_segundo_vencimiento.md`, `moroso_automatico.md`

---

## Campos nuevos en `Club Settings` (Single)

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `dia_generacion_deuda` | Int | 1 | Día del mes en que se genera la deuda (1–28) |
| `dia_primer_vencimiento` | Int | 10 | Día del mes del 1er vencimiento |
| `dia_segundo_vencimiento` | Select | `Ultimo dia del mes` | `Ultimo dia del mes` o día fijo 15–28 |
| `recargo_segundo_vencimiento_pct` | Percent | 10 | Recargo sobre saldo impago al 2do vencimiento |
| `item_recargo_mora` | Link → Item | — | Ítem ERPNext para línea de recargo (servicio) |
| `incluir_aranceles_en_deuda_mensual` | Check | 1 | Facturar aranceles de inscripciones activas |
| `incluir_cargos_extra_en_deuda_mensual` | Check | 1 | Facturar cargos extra recurrentes vigentes |

---

## Scenario: defaults al migrar

Given sitio con `Club Settings` existente sin los campos nuevos
When `bench migrate`
Then los defaults anteriores se aplican sin romper cobranza manual existente.

---

## Scenario: validación de días

Given `dia_generacion_deuda = 15` y `dia_primer_vencimiento = 10` en el mismo mes calendario
When Secretaría guarda `Club Settings`
Then error: el 1er vencimiento debe ser **posterior** al día de generación
  (o ajustar regla: vencimiento del mes de facturación ≥ día generación + margen mínimo).

Given `dia_primer_vencimiento = 31` (inválido)
Then error o normalización al último día hábil del mes.

---

## Scenario: solo Secretaría edita configuración

Given usuario sin rol `Secretaria` / `System Manager`
When intenta guardar `Club Settings`
Then sin permiso de escritura (DocPerm actual).

---

## Artefactos esperados

| Artefacto | Ubicación |
|-----------|-----------|
| JSON | `members/doctype/club_settings/club_settings.json` |
| Validación | `club_settings.py` |
| Tests | `members/tests/test_cobranza_config_club_settings.py` |

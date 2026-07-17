# Spec: Recordatorio provisión de sueldos (Secretaría)

El último día hábil de cada mes, Secretaría debe ver en el panel del workspace un aviso para generar las **Purchase Invoice** de provisión de sueldos y cargas (sin HRMS).

**Relacionado:** `carga_rapida_ingreso_egreso.md`, `secretaria_workspace_panel_kpis.md`

---

## Scenario: último día hábil del mes

Given la fecha de referencia es el **último día hábil** del mes (lun–vie; sin feriados en MVP)
When Secretaría abre el workspace **Secretaría**
Then el panel muestra un banner de provisión de sueldos.

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
| Sueldos del personal | ICDPE-Sueldos Personal | ICDPE-FIN-SUELDOS |
| Formulario 931 / cargas sociales | ICDPE-AFIP 931 | ICDPE-FIN-CARGAS-931 |
| ART | ICDPE-ART | ICDPE-FIN-ART |
| Aportes UTEDYC | ICDPE-UTEDYC | ICDPE-FIN-UTEDYC |
| Honorarios entrenadores | ICDPE-Sueldos Personal | ICDPE-FIN-ENTRENADORES |

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `finance/services/recordatorio_sueldos.py` |
| Panel payload | `members/services/secretaria_workspace_panel.py` |
| UI | `public/js/secretaria_workspace_panel.js` |
| Tests | `tests/test_recordatorio_sueldos.py` |

---

## Backlog (post-MVP)

- **GF-6:** Revisar con Secretaría qué debe verse el último día hábil (copy, conceptos, CTA hacia factura de compra).
- **GF-7:** Reemplazar todo texto visible en inglés por español argentino (ej. «Nueva factura de compra» en lugar de «Nueva Purchase Invoice»).

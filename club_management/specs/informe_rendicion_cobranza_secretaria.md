# Spec: Informes de rendición de cobranza — Secretaría / cobradora

**Épica:** 5.1 Caja diaria y rendición actividades (Club Echagüe)  
**Objetivo:** que Secretaría y la cobradora vean en Desk la recaudación **imputada** por concepto/actividad y los saldos pendientes, sin depender del Excel intermedio del informe manual.

**Relacionado:** `carga_masiva_cobranzas.md`, `informe_concepto_cobranza.md`, `informe_pagos_del_dia.md`, `secretaria_workspace_panel_kpis.md`, `pagos_por_equipo.md`, `liquidacion_equipo_deuda_rango.md`

---

## 1. Relevamiento — formato manual (informe de la cobradora)

El archivo que entrega la cobradora (p. ej. `Cobranza 01 a 28-08.xlsx`) es un Excel **agrupado por concepto**, no un CSV tabular.

### Estructura detectada (`informe_cobranzas.py`)

| Elemento | Contenido |
|----------|-----------|
| Encabezado | Celda A1: texto `INFORME DE COBRANZAS` |
| Bloques | Una fila `CONCEPTO: <nombre>` seguida de filas de detalle |
| Columnas detalle | A: **Fecha** · B: **Nº socio** · D: **Período** (`JULIO 2026`, `AGOSTO 26`, …) · E: **Importe** · I: **Nota** (medio: efectivo / transferencia) |
| Pie de bloque | `Subtotales` por concepto |
| Pie global | `Totales` |

### Semántica operativa

- Un mismo archivo cubre **varios períodos de deuda** (p. ej. cuota agosto + arancel julio pendiente).
- El **concepto** del informe es la clave de negocio para Secretaría (no el `item_code` ERPNext).
- La nota en columna I distingue **Efectivo** vs **Transferencia** (regex `tra` → Transferencia).
- El informe es **input** del apply masivo y **rendición** hacia Tesorería/Secretaría.

### Lo que Secretaría necesita ver (sin Excel)

1. **Recaudado imputado** en el sistema, desglosado por **concepto del informe** (o agrupación equivalente).
2. **Subtotales por concepto** y **total del rango** (fechas del informe).
3. **Medios de pago** (efectivo / transferencia / tarjeta).
4. **Saldos pendientes** por actividad / concepto (deuda emitida no cobrada).
5. **Excepciones** tras apply masivo (`monto_discordante`, `socio_no_encontrado`, …) — hoy en CSV/Excel auxiliar.

---

## 2. Inventario — capacidades actuales

### 2.1 Scripts (motor de importación, no informes Desk)

| Script | Rol | Salida | ¿Sirve como rendición? |
|--------|-----|--------|-------------------------|
| `scripts/informe_cobranzas.py` | Parsea Excel agrupado → filas normalizadas (`nro_socio`, `concepto`, `periodo`, `monto_abonado`, `medio_pago`, `referencia_comprobante`) | `list[dict]` para `bulk_payments` | **No** — solo lectura de entrada |
| `scripts/informe_concepto_cobranza.py` | Cruce concepto ↔ línea SI / ítem; CTO COMP fuzzy; reglas FEBAMBA | Match interno | **No** — lógica de imputación |
| `scripts/bulk_payments.run` | Crea `Payment Entry`, mora al cobro, tolerancias | JSON log + `.inconsistencias.csv` | **Parcial** — auditoría técnica, no formato Secretaría |
| `backups/.../_build_discordantes_xlsx.py` | Enriquece filas `monto_discordante` del apply | `cobranzas_discordantes_vN.xlsx` | **No** — herramienta de reconciliación dev/ops |
| `scripts/cobranza_informe_prod_pipeline.py` | Orquesta parches + facturación CTO COMP + apply prod | `pipeline_summary.json` | **No** — pipeline ops |

### 2.2 Desk — informes existentes

| Informe | Fuente de datos | Agrupación | Filtros | Gap vs informe manual |
|---------|-----------------|------------|---------|------------------------|
| **Pagos del dia** | `Payment Entry` del día | Detalle socio + concepto normalizado; totales por concepto al pie; summary por medio | Fecha (día) | Rango **un solo día**; conceptos **normalizados** («Cuota Social», no «Cuota Social Menor»); no replica bloques `CONCEPTO:` |
| **Deuda por actividad** | SI impagas + inscripciones | Por actividad deportiva | Actividad, fechas | Muestra **pendiente**, no recaudado |
| **Deuda por equipo** | Idem, por equipo | Por equipo / socio | Actividad, grupo, equipo, rango | Pendiente + acción liquidar |
| **Pagos por equipo** | Cobros en rango | Por socio / equipo; liquidación entrenador | Actividad, equipo, rango fechas | Solo **aranceles de equipo**; no cuota social ni CTO COMP |

### 2.3 Desk — panel KPI (custom, no workspace JSON estático)

Implementado en `members/services/secretaria_panel_kpis.py` + panel custom (`secretaria_workspace_panel.py`):

| Métrica | Qué muestra | Gap |
|---------|-------------|-----|
| % cuotas sociales mes | Emitido / recaudado / saldo por cobrar del **período MM/YYYY** | No desglosa por categoría (Activo/Menor/…) ni por concepto informe |
| % aranceles mes + por actividad | Recaudación aranceles agrupada por `Inscripcion Actividad.actividad` | No incluye CTO COMP, federativas, cargos extra con etiqueta informe |
| Tendencia diaria cuotas | Acumulado emitido vs recaudado por día del mes | Útil para monitoreo; no es rendición de cobradora |
| Medios de pago mes | Efectivo / tarjeta / transferencia / otro | **Mes calendario**, no rango del informe |
| Socios morosos | Cantidad + suma `saldo_deuda` | Complementa saldos pendientes globales |

### 2.4 Workspace `Secretaría` (JSON exportado)

- Atajos: socios pendientes de pago, morosos.
- **Sin** number cards ni enlaces a informes de cobranza en el fixture `secretaria.json` (el panel rico vive en página custom «Gestión de Socios»).

---

## 3. Matriz de brechas

| Necesidad cobradora / Secretaría | Excel manual | Sistema hoy | Brecha |
|----------------------------------|--------------|-------------|--------|
| Listado por concepto informe con subtotales | Sí | No | **Alta** |
| Rango de fechas de cobro (01–28) | Sí | Solo día o mes calendario | **Alta** |
| Medios de pago en rendición | Sí (nota) | Pagos del día (summary); panel mes | Media — falta en reporte por rango/concepto |
| Recaudado **después de imputar** en ERP | Implícito post-apply | Pagos del día / pagos por equipo | Media — falta vista consolidada por concepto informe |
| Saldos pendientes por actividad | No (otra planilla) | Deuda por actividad | **Cubierto** (enlace desde workspace) |
| Filas no imputables del apply | `_build_discordantes_xlsx` | CSV inconsistencias | Media — no visible en Desk |
| Cuota social por categoría (Activo/Menor/…) | Sí (concepto explícito) | KPI % global cuotas | Media |
| CTO COMP / federativas / FEBAMBA | Conceptos propios | Mapeo en import; sin reporte | **Alta** |

---

## 4. Diseño propuesto

### 4.1 Principio

> **Fuente de verdad post-go-live:** `Payment Entry` + líneas `Sales Invoice Item` ya imputadas.  
> El Excel del informe deja de ser la rendición oficial una vez aplicado el cobro en Desk.

Los informes nuevos **reconstruyen la etiqueta de concepto del informe** a partir de la línea facturada, reutilizando `resolver_item_codes_concepto` / descripción SI (inverso documentado en §4.2).

### 4.2 Nuevo Script Report: **Recaudación por concepto**

**Nombre Desk:** `Recaudacion por concepto`  
**Ubicación:** `members/report/recaudacion_por_concepto/`  
**Rol:** `Secretaria`, `System Manager`

#### Filtros

| Filtro | Tipo | Default |
|--------|------|---------|
| `fecha_desde` | Date | Primer día mes corriente |
| `fecha_hasta` | Date | Hoy |
| `periodo_cobro` | Data (MM/YYYY) | Opcional — restringe SI referenciadas |
| `agrupacion` | Select | `Concepto informe` · `Actividad` · `Tipo (Cuota / Arancel / CTO COMP / Otro)` |
| `solo_cuotas_sociales` | Check | Off |
| `medio_pago` | Link Mode of Payment | Opcional |

#### Columnas (modo detalle)

| Columna | Origen |
|---------|--------|
| Concepto informe | Etiqueta reconstruida (ver tabla §4.2.1) |
| Fecha cobro | `Payment Entry.posting_date` |
| Nº socio / Apellido, nombre | `Socio` vía SI |
| Período | `periodo_cobro` de la SI |
| Medio | `Payment Entry.mode_of_payment` |
| Monto imputado | `Payment Entry Reference.allocated_amount` prorrateado por línea |
| Payment Entry | Link |
| Sales Invoice | Link |

#### Pie del reporte

- **Subtotales por concepto informe** (réplica funcional de `Subtotales` del Excel).
- **Total recaudado** del rango.
- **Totales por medio de pago** (réplica del summary de Pagos del día, pero para el rango).

#### §4.2.1 Mapeo inverso concepto informe

Reutilizar tablas de `informe_concepto_cobranza.py`:

- Cuota social: `Cuota Social {Categoría}` según ítem / categoría socio.
- Aranceles: nombre del ítem o alias (`Adicional Basquet Escuelita`, …).
- CTO COMP: descripción de línea `ICDPE-CARGO-VARIOS` normalizada.
- Federativas: `CUOTA FEDER VOLEY`, `C FED …` según ítem.
- Fallback: `description` de la línea SI truncada.

Servicio compartido propuesto: `members/services/concepto_informe_label.py` (función `etiqueta_concepto_informe_desde_linea_si`).

---

### 4.3 Excepciones de importación (fuera de alcance producto)

Los códigos `monto_discordante` / `socio_no_encontrado` y el Excel `_build_discordantes_xlsx.py` fueron **herramientas de migración** del sistema anterior. El producto **no** prevé CSV/Excel auxiliar ni DocType de inconsistencias: la cobranza operativa es Desk (`Registrar cobro` / carga masiva puntual) y la rendición sale de `Payment Entry` imputados.

---

### 4.4 Panel Secretaría — card «Tasa de cobrabilidad del mes»

En el panel custom (`secretaria_workspace_panel.js`), **una sola card** con **dropdown de vista** y **subfiltro** según el tipo elegido:

| Vista (dropdown 1) | Subfiltro (dropdown 2) | Métrica mostrada |
|--------------------|------------------------|------------------|
| **Total** | — | % recaudado global del mes (todas las líneas emitidas del período) |
| **Cuotas sociales** | Categoría (Activo, Menor, Adherente, …) | % / cobrado / saldo de la categoría |
| **Aranceles** | Actividad deportiva | % / cobrado del arancel de esa actividad |
| **CTO COMP** | Concepto (si hay varios) | % / cobrado del concepto |
| **Federativas** | Concepto federativo | Idem |
| **Otros conceptos** | Etiqueta informe | Idem |

«Ver informe» abre **Recaudación por concepto** con filtros alineados a la vista (`agrupacion`, `solo_cuotas_sociales`, período del mes).

Los datos de desglose salen de `get_recaudacion_mes_payload()`; los enlaces en `get_cobranza_panel_links()` → `ver_mas.cobranza`.

### 4.5 Enlaces en workspace — sección «Cobranza»

Un solo informe **Recaudación por concepto** con filtro **Vista** (`Rendición por concepto` / `Pagos del día`) reemplaza el menú separado de Pagos del día.

Un solo informe **Deuda por equipo** con filtro **Agrupar por** (`Equipo` / `Actividad`) reemplaza Deuda por actividad en el menú.

| Enlace menú | Tipo |
|-------------|------|
| Recaudación por concepto | Report unificado |
| Deuda por equipo | Report unificado |
| Pagos del dia | Report (legado; delega al unificado) |
| Pagos por equipo | Report |

---

## 5. Escenarios Given / When / Then

### Scenario: rendición por rango sin Excel

Given cobros imputados entre el 01/08/2026 y el 28/08/2026
When Secretaría abre **Recaudación por concepto** con ese rango
Then ve bloques equivalentes al informe manual: detalle por fila y subtotales por concepto
And el total del reporte coincide con la suma de `Payment Entry` Receive en el rango (± tolerancia redondeo).

---

### Scenario: subtotales cuota social por categoría

Given cobros del mes con líneas «Cuota Social Activo» y «Cuota Social Menor»
When agrupación = `Concepto informe`
Then aparecen subtotales separados por cada categoría
And no se mezclan en un único «Cuota Social» genérico.

---

### Scenario: aranceles y CTO COMP en la misma rendición

Given PE imputados a aranceles y a líneas CTO COMP en el rango
When se genera el reporte
Then cada concepto informe aparece con su subtotal
And CTO COMP no lleva mora en el monto mostrado (monto cobrado = monto imputado).

---

### Scenario: saldos pendientes por actividad

Given actividades con socios inscriptos y SI impagas del período
When Secretaría abre **Deuda por actividad**
Then ve el saldo pendiente por actividad
And puede contrastar con la columna «Saldo por cobrar» del panel KPI.

---

### Scenario: number card recaudado cuotas

Given facturas de cuota social emitidas en 09/2026
And el 60 % ya cobrado
When Secretaría abre el workspace
Then la card muestra el monto recaudado y al hacer clic abre el reporte filtrado al mes.

---

### Scenario: permisos

Given usuario sin rol `Secretaria` ni `System Manager`
When intenta abrir **Recaudación por concepto** o las APIs de KPI
Then recibe error de permisos.

---

### Scenario: exportar Excel alineado al modelo de rendición

Given cobros imputados en un día o rango (`fecha_desde` / `fecha_hasta`)
When Secretaría pulsa **Exportar Excel** en **Recaudación por concepto**
Then descarga un `.xlsx` con dos hojas:
- **Resumen Ejecutivo CD**: título del club, rango de cobro, KPIs (total / operaciones / cuotas / aranceles), tabla por concepto (ops, total, % participación), arqueo por medio de cobro, bloque de firmas
- **Detalle_Cobranzas**: `#`, Concepto, Fecha Cobro, N° Socio, Apellido y Nombre, Período Imputado, Medio de Pago, Monto Cobrado, N° Comprobante (Payment Entry)
And los totales del Excel coinciden con `get_informe_recaudacion_por_concepto` para los mismos filtros
And un usuario sin rol Secretaría / System Manager no puede exportar.

---

### Scenario: exportar PDF de la misma rendición

Given el mismo informe filtrado
When Secretaría pulsa **Exportar PDF**
Then descarga un PDF con resumen ejecutivo (KPIs + por concepto + por medio) y el detalle de cobranzas
And el total del PDF coincide con el total del informe
And aplica el mismo control de permisos que el Excel.

---

### Scenario: export desde vista Pagos del día

Given vista = `Pagos del día` con una `fecha`
When se exporta Excel o PDF
Then el archivo usa `fecha_desde = fecha_hasta = fecha` (un solo día de cobro).

---

## 6. Roadmap de implementación (TDD)

| Fase | Entregable | Tests |
|------|------------|-------|
| **1** | `concepto_informe_label.py` + tests unitarios de etiquetas | `test_concepto_informe_label.py` |
| **2** | Script Report `recaudacion_por_concepto` | `test_recaudacion_por_concepto.py` ✅ |
| **3** | Card unificada «Tasa de cobrabilidad» + links filtrados en panel Secretaría | `test_secretaria_panel_cobranza_cards.py` ✅ |
| **4** | Export Excel/PDF alineado al modelo (2 hojas / PDF resumen+detalle) | `test_recaudacion_por_concepto_export.py` |

Orden SDD: spec (este archivo) → test rojo → implementación mínima → refactor.

---

## 7. Qué sigue siendo Excel / bench (fuera de Desk)

| Proceso | Herramienta | Motivo |
|---------|-------------|--------|
| Primera carga masiva del mes | `bulk_payments.run` / pipeline prod | Volumen + reglas mora/tolerancia |
| Reconciliación pre-apply | `_build_discordantes_xlsx.py` | Análisis fila a fila antes de imputar |
| Cierre manual casos excepción | Desk + `cobranza-informe-manual-prod.md` | `monto_discordante`, socios nuevos, fechas inválidas |

Una vez imputado, **la rendición oficial es Desk** (reporte + cards), no una nueva exportación del Excel de la cobradora.

---

## 8. Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | `specs/informe_rendicion_cobranza_secretaria.md` |
| Parser informe (input) | `scripts/informe_cobranzas.py` |
| Cruce concepto (import) | `scripts/informe_concepto_cobranza.py` |
| Apply masivo | `scripts/bulk_payments.py` |
| Pagos diarios (parcial) | `members/services/informe_pagos_del_dia.py` |
| KPI panel | `members/services/secretaria_panel_kpis.py` |
| Etiquetas concepto (fase 1) | `members/services/concepto_informe_label.py` |
| Tests fase 1 | `members/tests/test_concepto_informe_label.py` |
| Report recaudación (fase 2) | `members/report/recaudacion_por_concepto/` |
| Servicio reporte | `members/services/recaudacion_por_concepto.py` |
| Tests fase 2 | `members/tests/test_recaudacion_por_concepto.py` |
| Workspace (fase 3) | `members/workspace/secretaria/secretaria.json` |
| Export Excel/PDF (fase 4) | `members/services/recaudacion_por_concepto_export.py` |
| API export | `members/api/cobranza_desk.py` (`export_recaudacion_por_concepto`) |
| Template PDF | `templates/recaudacion_por_concepto_pdf.html` |
| Tests fase 4 | `members/tests/test_recaudacion_por_concepto_export.py` |

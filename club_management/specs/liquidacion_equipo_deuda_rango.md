# Spec: Liquidación por equipo y deuda por socio en rango de fechas

Secretaría debe poder **consultar** y **liquidar manualmente** la deuda de socios
filtrados por **actividad / grupo / equipo** y por **rango de fechas** de facturación.

**Relacionado:** `mvp_operacion_secretaria_sin_pagos.md`, `activities_jerarquia.md`,
`inscripcion_gestion_desk.md`, `cobranza_periodica_mensual.md`, `secretaria_operacion_interna_mvp.md`

**Prerequisito:** ERPNext (`Sales Invoice`, `Payment Entry`) y campo `socio` en factura
(patch `add_cobranza_custom_fields`).

**Módulo:** `members/` (reporte) + reutiliza `members/services/cobranza_manual.py`

---

## Objetivo

1. **Consulta:** listar socios con inscripción activa en el equipo (o grupo/actividad)
   elegido y el **saldo impago** de facturas emitidas en un rango de fechas.
2. **Liquidación manual:** desde esa consulta, registrar cobro de una o más facturas
   pendientes del socio en el rango (reutiliza `registrar_cobro_manual`).

**Fuera de alcance (iteración siguiente):**

- Cobro online / SIRO por lote.
- Liquidación automática sin intervención de Secretaría.
- Descuentos por hermanos o grupo familiar.
- Export PDF con firma del entrenador (solo export CSV/Excel estándar del reporte Frappe en v1).

---

## Modelo y definiciones

### Población de socios (filtro equipo)

Un socio entra en el reporte si existe al menos una `Inscripcion Actividad` con:

| Filtro del reporte | Condición sobre la inscripción |
|--------------------|--------------------------------|
| `equipo_actividad` informado | `equipo_actividad` = valor y `estado = Activa` |
| Solo `grupo_actividad` | `grupo_actividad` = valor, `estado = Activa` (cualquier equipo del grupo) |
| Solo `actividad` | `actividad` = valor, `estado = Activa` |

**Jerarquía en UI:** filtros en cascada Actividad → Grupo → Equipo (mismo patrón que inscripción Desk).
Al menos **uno** de los tres debe estar informado.

Un mismo socio aparece **una sola vez** por ejecución del reporte (aunque tenga varias
inscripciones que matcheen; mostrar resumen de actividad/grupo/equipo de la inscripción
que coincide con el filtro más específico).

### Deuda en rango de fechas

**Regla v1:** suma de `Sales Invoice.outstanding_amount` donde:

- `docstatus = 1`
- `outstanding_amount > 0`
- vínculo `socio` (o `custom_socio`) = socio del reporte
- `posting_date` ∈ [`fecha_desde`, `fecha_hasta`] (inclusive)

`posting_date` es la **fecha de emisión** de la deuda (cuota mensual, cargo manual, etc.).

**Columnas adicionales por fila (detalle opcional en expand / drill-down):**

- Lista de facturas pendientes en el rango: `name`, `posting_date`, `due_date`, `periodo_cobro` (si existe), `outstanding_amount`, `grand_total`.

**Saldo total del socio** (todas las facturas pendientes, sin filtro de fecha): columna
informativa `saldo_total`; no sustituye a `deuda_en_rango`.

### Estados de socio

Incluir socios en cualquier `estado` excepto `Baja` (configurable; default excluir solo `Baja`).
No filtrar solo `Moroso`: la liquidación sirve también para cobrar antes del cambio de estado.

---

## Reporte Desk: «Deuda por equipo»

| Propiedad | Valor |
|-----------|--------|
| Tipo | Script Report |
| Nombre | `Deuda por equipo` |
| Módulo | Members |
| Roles | `Secretaria`, `System Manager` |

### Filtros del reporte

| Filtro | Tipo | Reqd | Notas |
|--------|------|------|-------|
| `actividad` | Link → Actividad | no | Cascada |
| `grupo_actividad` | Link → Grupo Actividad | no | Filtrado por actividad si está seteada |
| `equipo_actividad` | Link → Equipo Actividad | no | Filtrado por grupo si está seteado |
| `fecha_desde` | Date | sí | Default: primer día del mes corriente |
| `fecha_hasta` | Date | sí | Default: hoy; debe ser ≥ `fecha_desde` |
| `incluir_saldo_cero` | Check | no | Default 0; si 0, oculta socios con `deuda_en_rango = 0` |

### Columnas del reporte

| Columna | Descripción |
|---------|-------------|
| `socio` | Link / ID (`SOC-YYYY-####`) |
| `nombre_apellido` | Texto |
| `estado` | Estado del socio |
| `actividad` | De la inscripción matcheada |
| `grupo_actividad` | Idem |
| `equipo_actividad` | Idem |
| `deuda_en_rango` | Currency; suma outstanding en rango |
| `deuda_cuota_social` | Currency; saldo pendiente de líneas de cuota social |
| `deuda_arancel` | Currency; saldo pendiente del arancel de la inscripción |
| `deuda_cuota_federativa` | Currency; saldo pendiente de cuota federativa vinculada a la actividad |
| `cantidad_meses_deuda` | Int; períodos distintos (`periodo_cobro`) o facturas pendientes en rango |
| `saldo_total` | Currency; saldo impago total ERPNext |
| `cantidad_facturas` | Int; facturas pendientes en rango |

**Resumen en cabecera del reporte:** totales agregados del filtro jerárquico
(actividad / grupo / equipo) para `deuda_cuota_social`, `deuda_arancel`,
`deuda_cuota_federativa` y `deuda_en_rango`.

**Informe complementario:** `Deuda por actividad` (ver `deuda_por_actividad.md`).

Orden default: `deuda_en_rango` descendente, luego `nombre_apellido` ascendente.

**Fila de totales:** el reporte muestra una fila **Total** al pie con la suma de
`deuda_en_rango`, `saldo_total` y `cantidad_facturas` de las filas visibles.

---

## Scenario: Secretaría consulta deuda del equipo en un mes

Given inscripciones activas en `Equipo Actividad` «U15 Masculino»
And socios A y B del equipo con facturas pendientes emitidas en marzo 2026
And socio C del mismo equipo sin facturas en ese rango
When Secretaría ejecuta el reporte con `equipo_actividad` = «U15 Masculino»,
  `fecha_desde` = 2026-03-01, `fecha_hasta` = 2026-03-31
Then aparecen A y B con `deuda_en_rango` > 0
And C no aparece si `incluir_saldo_cero` = 0
And cada fila muestra actividad, grupo y equipo de la inscripción.

---

## Scenario: filtro por grupo sin equipo específico

Given varias inscripciones activas bajo `Grupo Actividad` «Tira Azul»
  en distintos equipos (U13, U15)
When el reporte filtra solo por `grupo_actividad` = «Tira Azul»
Then incluye todos los socios con inscripción activa en ese grupo
And la deuda en rango se calcula igual por socio.

---

## Scenario: factura pagada dentro del rango no suma deuda

Given socio D con factura de marzo 2026 totalmente cobrada (`outstanding_amount = 0`)
And otra factura de abril 2026 pendiente
When el reporte usa rango marzo 2026
Then `deuda_en_rango` de D = 0 para marzo
When el rango es abril 2026
Then `deuda_en_rango` de D > 0.

---

## Scenario: recargo de segundo vencimiento en el rango

Given factura mensual marzo pendiente y factura de recargo `-REC` del mismo período
  emitida en marzo con saldo pendiente
When el reporte filtra marzo 2026
Then `deuda_en_rango` incluye ambas facturas (cuota + recargo).

---

## Scenario: validación de fechas

Given `fecha_desde` = 2026-05-15 y `fecha_hasta` = 2026-05-01
When Secretaría ejecuta el reporte
Then recibe error de validación (hasta ≥ desde).

---

## Scenario: al menos un filtro jerárquico obligatorio

Given `actividad`, `grupo_actividad` y `equipo_actividad` vacíos
When Secretaría ejecuta el reporte
Then recibe error: debe elegir actividad, grupo o equipo.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When invoca el reporte o las APIs de liquidación
Then recibe `PermissionError`.

---

## Scenario: sin ERPNext

Given el sitio no tiene `Sales Invoice`
When Secretaría abre el reporte
Then ve mensaje claro de que la consulta de deuda requiere ERPNext
And no expone datos de socios de otro módulo sin control (fail closed en API).

---

## Liquidación manual desde el reporte

### Scenario: listar facturas pendientes de un socio en el rango

Given una fila del reporte con `deuda_en_rango` > 0
When Secretaría abre el detalle del socio (drill-down o botón «Ver facturas»)
Then ve las `Sales Invoice` pendientes con `posting_date` en el rango
And cada una muestra saldo pendiente y fechas.

---

### Scenario: registrar cobro de una factura desde liquidación

Given factura pendiente F de socio S en el rango del reporte
When Secretaría ejecuta **Registrar cobro** sobre F vía API `registrar_cobro_liquidacion`
Then se llama a `registrar_cobro_manual(S, F)` (mismo comportamiento que formulario Socio)
And se crea `Payment Entry` submitted
And `Socio.saldo_deuda` y `deuda_en_rango` se actualizan al refrescar
And si el socio estaba `Moroso` y saldo total = 0, pasa a `Activo`.

---

### Scenario: registrar cobro de todas las facturas del rango para un socio

Given socio S con 2 facturas pendientes en el rango
When Secretaría ejecuta **Liquidar deuda en rango** para S
Then se registra cobro secuencial de cada factura pendiente en el rango (más antigua primero)
And si una falla, se detiene y se reporta cuáles se liquidaron
And la respuesta lista `payment_entries` creados.

---

### Scenario: no cobrar factura fuera del rango desde liquidación por equipo

Given factura pendiente G de socio S con `posting_date` fuera del rango del reporte
When Secretaría intenta `registrar_cobro_liquidacion` con filtros del reporte y factura G
Then recibe error de validación (factura no pertenece al rango activo).

---

### Scenario: aislamiento entre socios

Given cobro iniciado para socio A
When el usuario intenta registrar cobro con `sales_invoice` de socio B
Then recibe error (factura no pertenece al socio).

---

## UI Desk

Given workspace **Secretaría** o **Gestión de Actividades**
When Secretaría abre el enlace **Deuda por equipo**
Then navega al Script Report con filtros en cascada
And puede exportar CSV/Excel (estándar Frappe)
And en cada fila con deuda > 0 hay acción **Liquidar en rango** o enlace al formulario `Socio`.

**Ubicación sugerida del enlace:** workspace **Secretaría** (sección cobranza) y
barra de administración de **Gestión de Actividades**.

---

## Artefactos esperados (implementación)

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio consulta | `members/services/liquidacion_equipo.py` |
| Script Report | `members/report/deuda_por_equipo/deuda_por_equipo.py` + `.json` |
| Client report (opcional) | `members/report/deuda_por_equipo/deuda_por_equipo.js` |
| API whitelist | `members/api/liquidacion_equipo_desk.py` |
| Tests servicio | `members/tests/test_liquidacion_equipo.py` |
| Tests API | `members/tests/test_liquidacion_equipo_desk.py` |
| Enlace workspace | `members/workspace/secretaria/secretaria.json` (+ patch sync) |

### API propuesta

```python
@frappe.whitelist()
def get_facturas_pendientes_rango(
    socio: str,
    fecha_desde: str,
    fecha_hasta: str,
) -> list[dict]: ...

@frappe.whitelist()
def registrar_cobro_liquidacion(
    socio: str,
    sales_invoice: str,
    fecha_desde: str,
    fecha_hasta: str,
) -> dict: ...

@frappe.whitelist()
def liquidar_deuda_socio_en_rango(
    socio: str,
    fecha_desde: str,
    fecha_hasta: str,
) -> dict: ...
```

Todas las APIs llaman `ensure_secretaria_operacion_access()` y validan que la factura
pertenece al socio y cae en el rango antes de cobrar.

---

## SQL / PostgreSQL

Si hay consulta cruda, usar sintaxis **PostgreSQL v14**.
Preferir `frappe.get_all` / `frappe.qb` sobre SQL manual.

---

## Orden de implementación (TDD)

1. Tests de `liquidacion_equipo.py` (población por equipo + suma deuda en rango).
2. Servicio mínimo.
3. Script Report que delega en el servicio.
4. Tests API de cobro en rango.
5. API + botones en client report.
6. Enlace en workspace + patch.

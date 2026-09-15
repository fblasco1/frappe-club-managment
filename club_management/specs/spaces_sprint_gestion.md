# Spec / Sprint: Gestión de Espacios (próximo tramo)

**Objetivo de negocio:** pasar de catálogo + grilla Desk a operación diaria
(reservas con comprobante y aprobación, disponibilidad en vivo, datos reales
cargados, reporte formal para Comisión Directiva).

**Base ya entregada (MVP Spaces — actualizado 2026-08-27):**
- DocTypes `Espacio`, `Horario Entrenamiento`, `Reserva Espacio`, `Excepcion Horario Dia`, `Suspension Reserva Dia`
- Motor de solapes / ocupación (`availability.py`)
- Alquiler externo Temporal / Recurrente (sin factura automática ni cobro online)
- Evento club recurrente (eventos sociales CSV: cenas, jubilados)
- Dashboard Desk `/desk/ocupacion-espacios` (planilla 08:00–04:00, 6 tipos de evento, orden fijo de columnas)
- Import CSV grilla L–V / sábado + fixtures FeBAMBA GES (JSON, ventanas partido, superposiciones)
- Reubicar / suspender entrenamiento del día; suspender reserva del día; selector superposición al clic
- Rol `Coordinacion`, workspace Espacios
- Resumen módulo: `spaces_modulo_resumen.md`

**Pendiente inmediato (antes de épicas online):**
- **SP-1:** sync **FMV (Vóley)** — adaptador federativo (ver `spaces_fixtures_partidos.md`)
- **SP-2:** import **fixtures de ligas en Excel** (Desk, idempotente)

**Relacionado:** `spaces_catalogo_ocupacion.md`, `spaces_alquiler_externo.md`,
`spaces_ocupacion_dashboard.md`, `spaces_fases_futuras.md`

**Fuera de este sprint (salvo spike acotado):** inventar endpoints Cobrand;
SIRO; facturación automática completa; bot no oficial a grupo WhatsApp.

---

## Decisiones de producto (cerradas 2026-08-24)

| Tema | Decisión |
|------|----------|
| Ocupación | Al **generar la solicitud** el slot queda **bloqueado** (ocupa calendario). Queda **firme** solo cuando Coordinación **confirma**. Rechazo / vencimiento del flujo **libera** el bloqueo. |
| Quién reserva | **Ambos:** socio portal **y** externo (token/flujo público). Tarifas y reglas **configurables y distintas** por canal (Club Settings / maestros Spaces). |
| Comprobante | **Fase 1:** transferencia + PDF adjunto. **Fase 2:** Cobrand. Retención: ver sección más abajo. |
| Datos E3 | Coordinación de espacios entrega **Excel esta semana** con la información completa. |
| Destinatarios E4 | Email a **coordinador/es** (lista en Club Settings). Ellos **replican manualmente** al grupo WhatsApp de Comisión Directiva. Sin integración WhatsApp en el sistema. |

---

## Épica 1 — Reservas online + comprobante + confirmación Coordinación

### Scenario: solicitud online bloquea el slot

Given un espacio `alquilable = 1` y `habilitado = 1` con franja libre
When un solicitante (socio portal **o** externo con token) genera la solicitud
Then se crea `Reserva Espacio` en estado **Pendiente confirmación** (o
**Pendiente pago** si aún falta comprobante, según subflujo)
And el slot **ocupa** el calendario (bloqueo) frente a otras solicitudes y
reservas Confirmada
And el solicitante solo ve **sus** reservas (aislamiento).

### Scenario: tarifas distintas por canal

Given tarifas configuradas para canal `socio` y canal `externo`
When cada uno solicita el mismo espacio/franja
Then el monto / ítem sugerido corresponde a la tarifa de **su** canal
And los valores son editables en configuración (no hardcode).

### Scenario: envío de comprobante (fase 1 transferencia + PDF)

Given una reserva bloqueada pendiente de pago/comprobante
When el solicitante adjunta PDF de transferencia
Then el sistema notifica a Coordinación (Email Queue / Desk)
And el File queda vinculado a la reserva
And se registra fecha de carga para política de retención.

### Scenario: Coordinación confirma (firme) o rechaza

Given reservas en cola **Pendiente confirmación** con bloqueo activo
When Coordinación confirma
Then el estado pasa a **Confirmada** (ocupación **firme**)
When rechaza o el flujo vence sin completar
Then el estado pasa a **Cancelada** / **Rechazada**, se **libera** el bloqueo
And se notifica al solicitante
And no queda ocupación fantasma.

### Scenario: Coordinación ve conflicto al confirmar

Given otra ocupación Confirmada o grilla que solapa (edge: datos corruptos)
When Coordinación intenta confirmar
Then el sistema bloquea con mensaje claro de conflicto
And lista los conflictos.

---

## Épica 2 — Disponibilidad en tiempo real

### Scenario: consulta de disponibilidad

Given fecha + espacio (opcionalmente rango horario)
When un usuario autorizado (Desk o portal) consulta disponibilidad
Then recibe ocupación expandida: grilla + reservas **Confirmada** + reservas
en estados que **bloquean** (pendientes de la solicitud)
And el resultado refleja el estado actual de BD (polling / invalidación).

### Scenario: dashboard Desk se actualiza

Given Coordinación tiene abierta la planilla de ocupación
When otra sesión genera o confirma una reserva
Then al refrescar (manual o auto) ve el bloque (bloqueo o firme).

---

## Épica 3 — Carga de horarios y alquileres ya programados

### Scenario: importación desde Excel de Coordinación

Given el Excel oficial entregado esta semana por Coordinación de espacios
When se importa (herramienta Desk o patch supervisado)
Then se crean/actualizan `Horario Entrenamiento` y/o `Reserva Espacio`
(alquileres Temporal/Recurrente) de forma **idempotente**
And un reporte lista filas omitidas/errores
And el dashboard de un día de referencia coincide con la planilla.

---

## Épica 4 — Reporte diario grilla para Comisión Directiva

### Scenario: exportar ocupación del día

Given un usuario Coordinación / Secretaría / Tesorería
When elige una fecha y exporta el reporte
Then obtiene PDF y/o Excel (ventana **08:00–04:00**, columnas = espacios)
And distingue visualmente bloqueo vs Confirmada si aplica.

### Scenario: envío a coordinador/es (replica manual a Comisión)

Given lista `emails_coordinacion_espacios` (o equivalente) en Club Settings
When se dispara “Enviar reporte del día”
Then se encola email a **coordinador/es** con adjunto PDF/Excel del día
And queda registro (Communication / Email Queue)
And el cuerpo del mail indica que deben **replicar al grupo WhatsApp de Comisión Directiva**
And **no** se envía mensaje automático a WhatsApp desde el sistema.

### Scenario: sin XSS / fuga de datos

Given títulos o datos de arrendatario con caracteres especiales
When se renderiza el reporte
Then el contenido está escapado
And roles sin permiso Spaces no generan ni descargan el reporte.

---

## Análisis: retención de comprobantes (PDF)

**Contexto:** fase 1 = File adjunto a la reserva (no es factura electrónica AFIP
por sí solo). Sí puede ser **documentación respaldatoria** de un ingreso si
Tesorería lo usa para conciliar.

| Etapa | Recomendación |
|-------|----------------|
| Reserva pendiente / rechazada sin pago útil | Conservar **30–90 días** tras cierre del flujo, luego borrar File (libera storage; el doc puede quedar con nota “comprobante depurado”). |
| Reserva **Confirmada** (ingreso operativo) | Conservar **mínimo 24 meses** (operación + reclamos). |
| Si Tesorería/contabilidad lo archiva como respaldo de cobro | Alinear a práctica documental AR: **hasta 10 años** (configurable); default conservador **60 meses** si el club lo marca “respaldo contable”. |

**Diseño propuesto (configurable en Club Settings):**

- `espacios_comprobante_retencion_pendiente_dias` — default **90**
- `espacios_comprobante_retencion_confirmada_meses` — default **24** (o 60 si CD lo pide)
- Job diario: elimina Files vencidos; **no** borra el DocType Reserva; log de depuración
- Cobrand (fase 2): el ID en Payment Log es permanente; el PDF adjunto sigue la misma política de File

**Decisión pendiente de CD/Tesorería:** confirmar default 24 vs 60 meses para
Confirmada antes de implementar el job de purge.

---

## Entrega del reporte a Comisión Directiva (decisión cerrada)

**Flujo acordado:** el sistema envía **email** al/los **coordinador/es** (lista en
Club Settings) con el reporte del día adjunto. Coordinación **replica manualmente**
al grupo WhatsApp de Comisión Directiva.

| Aspecto | Decisión |
|---------|----------|
| Destino automático | Solo email a coordinador/es |
| WhatsApp grupo CD | **Fuera de alcance** — replicación humana |
| Configuración | Campo en Club Settings con uno o más emails de Coordinación |
| Auditoría | Email Queue / Communication |

No se implementa bot, API WhatsApp ni post al grupo en este sprint ni fases
posteriores salvo cambio explícito de producto.

---

## Orden de entrega sugerido

1. **Épica 3** — Excel/CSV grilla fija (L–V, sábado; hecho parcialmente vía `import_horarios`).
2. **Fixtures partidos** — carga manual CSV + contrato para FeBAMBA (`spaces_fixtures_partidos.md`).
3. **Épica 2** — disponibilidad incluyendo estados que bloquean.
4. **Épica 1** — flujo online (ambos canales) + PDF + cola Coordinación.
5. **Épica 4** — export + email a coordinador/es (replican al grupo CD por WhatsApp).

## Definición de terminado (DoD)

- Spec Given/When/Then + tests TDD por épica.
- Bloqueo desde solicitud; firme solo con Confirmada; rechazo libera.
- Tarifas socio ≠ externo configurables.
- Permisos Spaces y aislamiento portal/token.
- Retención de Files documentada + job o issue explícito si se difiere.
- Checklist security-auditor (whitelist, XSS, IDs pago idempotentes).

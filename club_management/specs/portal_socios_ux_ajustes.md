# Spec: Ajustes UX portal Gestión de Socios

Ajustes de etiqueta, acciones rápidas, alta Desk, navegación desde
Solicitud de Asociación y detalle de mora en el KPI del panel.

**Relacionado:** `secretaria_workspace_panel_kpis.md`, `gestion_socios_dashboard.md`,
`socio_alta_edicion_secretaria.md`

---

## Scenario: workspace visible como Socios

Given el Workspace Desk operativo de socios
When Secretaría (o System Manager) abre el panel
Then el `name`, **label** y **title** son **Socios**
And la URL Desk es `/desk/socios` (Frappe v16 enruta por name/title coincidentes).
And la URL legacy `/desk/secretaría` puede redirigir o dejar de resolver tras el rename.

---

## Scenario: acciones rápidas del panel

Given Secretaria abre el panel de Socios
When carga las acciones rápidas
Then ve el botón **+ Nuevo Socio** (alta guiada)
And **no** ve los botones «Emitir cupón / Registrar cobro» ni
  «Registrar Nuevo Gasto / Comprobante» (lógica backend intacta si se usa en otro lado)
And el recordatorio masivo sigue deshabilitado (próximamente).

---

## Scenario: alta Desk — título, layout y sin post-alta

Given Secretaria abre el asistente de alta desde el panel o el Form `Socio` nuevo
When ve el diálogo
Then el título es **Alta de Socio** (no «Alta guiada de socio»)
And en desktop los campos usan columnas densas (Column Breaks) para reducir scroll
And **no** hay sección «Después del alta» ni selector de destino de flujo
And al crear, el backend usa destino por defecto **Activar ahora** (`activar_al_guardar = 1`)
And el botón **Crear socio** está al final del formulario (después de todos los campos)
And la inscripción opcional a actividad sigue disponible en el mismo diálogo.

---

## Scenario: volver a Socios desde Solicitud de Asociación

Given Secretaria abre una `Solicitud Asociacion` desde el panel (o Form Desk)
When ve el formulario
Then tiene una acción clara **Volver a Socios**
And al usarla navega al workspace `Socios` (panel de gestión de socios).

---

## Scenario: KPI mora con clasificación por antigüedad

Given socios con `saldo_deuda > 0` y distintos períodos mensuales impagos
When Secretaria consulta el panel
Then la card **Socios en mora** sigue mostrando cantidad `estado = Moroso` y deuda total de morosos
And debajo muestra el desglose de deuda por **clasificación de mora**:
  - **1–3 meses** (1 a 3 períodos mensuales impagos)
  - **4+ meses** (4 o más períodos mensuales impagos)
And cada tramo incluye cantidad de socios y monto (`saldo_deuda` sumado).

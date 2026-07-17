# Spec: UI siempre en español argentino (GF-7)

El sistema es para clubes de Argentina. **Ninguna etiqueta visible para el usuario puede estar en inglés.** Esta fase cubre las superficies de Gestión Financiera (workspace Tesorería y banner de provisión de sueldos en Secretaría) y establece el mecanismo reutilizable de traducciones de la app.

**Relacionado:** `proyeccion_flujo_fondos.md`, `carga_rapida_ingreso_egreso.md`, `recordatorio_provision_sueldos_secretaria.md`

**Regla de producto:** los nombres técnicos de DocType de ERPNext (`Purchase Invoice`, `Payment Entry`, etc.) se usan solo como **identificadores** en `link_to`, rutas (`frappe.set_route`) y SQL; **nunca** como texto en pantalla.

---

## Scenario: workspace Tesorería sin inglés

Given el usuario abre el workspace **Tesorería**
When se listan las etiquetas de los links y accesos directos
Then ninguna etiqueta está en inglés (`Purchase Invoice`, `Sales Invoice`, `Payment Entry`, `Account`, `Cost Center`, `Invoice`, `Payment`)
And cada link muestra su etiqueta en español (p. ej. «Facturas de compra», «Pagos y cobros», «Centros de costo»)
And `link_to` conserva el nombre técnico del DocType (identificador, no visible).

---

## Scenario: banner provisión de sueldos en español

Given es el último día hábil y hay conceptos pendientes de provisión
When Secretaría ve el banner en el panel
Then el botón de acción dice **«Nueva factura de compra»** (no «Nueva Purchase Invoice»)
And la ruta interna sigue apuntando al DocType `Purchase Invoice`.

---

## Scenario: títulos y navegación de DocTypes financieros en español

Given el idioma del sitio es **es**
And la app provee `translations/es.csv`
When se abre la lista o el formulario de un DocType financiero
Then el título/breadcrumb se muestra en español según el catálogo de traducción de la app.

### Catálogo de traducción (mínimo GF-7)

| Nombre técnico (identificador) | Texto en pantalla (es-AR) |
|--------------------------------|---------------------------|
| Purchase Invoice | Factura de compra |
| Sales Invoice | Factura de venta |
| Payment Entry | Pago / cobro |
| Account | Cuenta contable |
| Cost Center | Centro de costo |

---

## Scenario: branding del sistema en español/producto (GF-7b)

Given el usuario ve el encabezado del workspace o la pantalla de apps
When se muestra el nombre del sistema
Then dice **«SICLUB»** (nombre del producto), nunca «Club Management».

---

## Scenario: nombres de módulo en español (GF-7b)

Given el idioma del sitio es **es**
When se muestra el módulo de un workspace en el breadcrumb/encabezado
Then aparece traducido: `Finance`→«Finanzas», `Members`→«Socios», `Activities`→«Actividades», `Club Management`→«SICLUB»
And el nombre técnico del módulo se conserva como identificador.

---

## Scenario: panel de Actividades sin inglés (GF-7b)

Given Secretaría abre el panel de Gestión de Actividades
When ve las acciones sobre actividades/grupos/equipos
Then el botón para abrir el registro dice **«Abrir ficha»** (no «Abrir en Desk»)
And la acción de alta de ítem de arancel dice **«Crear ítem de arancel»** (no «Crear ítem ERP»).

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Workspace Tesorería | `finance/workspace/tesoreria/tesoreria.json` |
| Traducciones app | `translations/es.csv` |
| Banner Secretaría | `public/js/secretaria_workspace_panel.js` |
| Patch re-sync workspace | `patches/v1_0/sync_tesoreria_workspace_es.py` |
| Tests | `tests/test_ui_espanol.py` |

---

## Backlog (fuera de GF-7)

- Términos en inglés remanentes en otras superficies: branding «Club Management» en sidebar (`app_title`), «Abrir en Desk», «Crear ítem ERP» en panel de Actividades. Revisar en una pasada global de i18n.

# Spec: Informes Tesorería — Ganancias vs Pérdidas y Cash Flow

El Tesorero, el día 1 (o cualquier cierre de período), abre desde el workspace **Tesorería** dos informes contables básicos, sin pasar por el módulo Accounts en inglés:

1. **Ganancias y pérdidas** (P&L) — resultado del período (ingresos vs gastos).
2. **Flujo de efectivo** — estado de cash flow contable (operativo / inversión / financiación).

La **proyección operativa a 5 días** ya existe (`proyeccion_flujo_fondos.md`); este spec no la reemplaza. El tesorero usa las dos capas: «¿llegamos la semana?» vs «¿el mes cerró positivo?».

**Relacionado:** `rol_tesoreria_permisos.md`, `tesoreria_panel_operaciones.md`, `proyeccion_flujo_fondos.md`

**No se modifica** `apps/erpnext`. Los Script Reports de `club_management` llaman a `erpnext.accounts.report.*`.

---

## Scenario: Tesorería ejecuta Ganancias y pérdidas

Given un usuario con rol `Tesoreria` y ERPNext instalado
When ejecuta el Script Report `Ganancias y Perdidas` del mes en curso (rango de fechas, company ICDPE)
Then obtiene columnas y filas de ingresos/gastos (puede estar vacío si no hay GL)
And el acceso pasó por `ensure_tesoreria_access`.

---

## Scenario: Tesorería ejecuta Flujo de efectivo

Given un usuario con rol `Tesoreria`
When ejecuta el Script Report `Flujo de Efectivo` del mismo período
Then obtiene el estado de flujo de efectivo de ERPNext (secciones operativo/inversión/financiación)
And el acceso pasó por `ensure_tesoreria_access`.

---

## Scenario: Secretaría no ve ni ejecuta P&L ni Cash Flow

Given un usuario con rol `Secretaria` (sin `Tesoreria`)
When llama a `execute` de `Ganancias y Perdidas` o `Flujo de Efectivo`
Then recibe `PermissionError`.

Given el mismo usuario abre el panel Tesorería
When se arma `get_panel_data`
Then `informes_contables.visible` es False
And el panel no muestra botones a esos reportes (sí puede ver liquidez operativa y listas).

---

## Scenario: panel Tesorería enlaza los informes (solo Tesorería)

Given un usuario `Tesoreria`
When se arma el panel
Then `informes_contables.visible` es True
And incluye los nombres `Ganancias y Perdidas`, `Flujo de Efectivo` y `Proyeccion Flujo de Fondos`
And el workspace muestra botones que abren esos Query Reports
And se puede filtrar P&L / Cash Flow por **centro de costo** (opcional) y por fechas del período.

---

## Scenario: P&L y Cash Flow corren en PostgreSQL

Given un sitio PostgreSQL (ERPNext usa `FORCE INDEX` MariaDB en el mayor)
When Tesorería ejecuta `Ganancias y Perdidas` o `Flujo de Efectivo`
Then el parche runtime omite `FORCE INDEX` y la consulta GL es SQL válido
And no se modifica `apps/erpnext`.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `finance/services/informes_contables.py` |
| Compat PG | `integrations/payment_ledger_postgres.py` (`force_index` no-op) |
| Reportes | `finance/report/ganancias_y_perdidas/`, `finance/report/flujo_de_efectivo/` |
| Panel | `finance/services/tesoreria_panel.py`, `public/js/tesoreria_workspace_panel.js` |
| Tests | `tests/test_informes_tesoreria.py`, `tests/test_tesoreria_panel.py` |

---

## Fuera de alcance

- Reescribir el motor contable de ERPNext.
- Trial Balance, conciliación bancaria, checklist de cierre de mes.
- Mostrar P&L a Secretaría.

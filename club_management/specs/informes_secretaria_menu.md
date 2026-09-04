# Spec: Menú de informes Secretaría / Actividades

Informes operativos visibles en Desk (Secretaría y Gestión de Actividades).

---

## Scenario: tres informes canónicos

Given rol Secretaría o System Manager
When abre el menú de informes
Then ve exactamente estos Script Reports (labels):
- **Cobranza por fechas**
- **Pagos por equipo**
- **Deuda por actividad**
And **no** ve como ítems de menú: «Pagos del dia», «Recaudacion por concepto», «Deuda por equipo».

---

## Scenario: Cobranza por fechas absorbe rendición y pagos del día

Given cobros imputados en un rango (o un solo día con Desde = Hasta)
When Secretaría abre **Cobranza por fechas**
Then ve el detalle por concepto/socio/medio con subtotales (misma lógica que la ex-Recaudación por concepto)
And puede exportar Excel/PDF
And el report legado **Pagos del dia** / **Recaudacion por concepto** redirige o ejecuta la misma grilla.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | `specs/informes_secretaria_menu.md` |
| Report | `members/report/cobranza_por_fechas/` |
| Servicio | `members/services/recaudacion_por_concepto.py` |
| Menú | `inicio_workspace.CLUB_DESK_REPORTS`, sidebars, `club_desk_navigation.js` |
| Patch rename | `patches/v1_0/sync_informes_secretaria_menu.py` |

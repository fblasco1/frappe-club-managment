# Spec: Cuota complementaria editable en panel Gestión de Actividades

La tarifa de **cuota complementaria** (CTO COMP) se asocia al deporte / categoría en el mismo panel donde se edita el arancel mensual.

**Relacionado:** `gestion_actividades_panel.md`, `gestion_actividades_edicion_panel.md`, `cargo_extra_socio.md`

---

## Scenario: campo en Actividad, Grupo y Equipo

Given los DocTypes `Actividad`, `Grupo Actividad` y `Equipo Actividad`
Then cada uno tiene el campo Currency `monto_cuota_complementaria` (opcional, ≥ 0).

---

## Scenario: set desde panel

Given un usuario con rol `Secretaria` o `System Manager`
When llama `set_cuota_complementaria(doctype, name, monto)`
Then persiste `monto_cuota_complementaria` en ese nodo
And la respuesta incluye `monto` resuelto.

---

## Scenario: cascada efectiva equipo → grupo → actividad

Given un equipo sin monto propio, grupo con `6000` y actividad con `7000`
When se resuelve la cuota complementaria efectiva del equipo
Then el monto es `6000` y el origen es `Grupo`.

Given el mismo equipo con monto propio `5000`
Then el efectivo es `5000` y origen `Equipo`.

Given equipo y grupo sin monto, actividad con `7000`
Then el efectivo es `7000` y origen `Actividad`.

---

## Scenario: catálogo expone monto y efectivo

Given Secretaría abre el panel (`get_catalog`)
Then cada actividad/grupo incluye `monto_cuota_complementaria`
And cada equipo incluye `monto_cuota_complementaria` propio y `cuota_complementaria` efectiva (`monto`, `origen`).

---

## Scenario: UI inline junto al arancel

Given el panel Gestión de Actividades expandido
When Secretaría ve actividad / grupo / equipo
Then junto al arancel mensual hay un input **Cuota complementaria**
When cambia el monto y guarda
Then llama `set_cuota_complementaria` y refresca el catálogo.

---

## Scenario: seed Básquet noviembre 2026

Given la estructura Basquet sincronizada
When corre el seed de tarifas CTO COMP
Then nodos Escuelita / Femenino quedan en `6000`
And nodos Masculino (Azul / Amarillo / Flex) quedan en `7000`.

---

## Notas

- La facturación sigue usando ítem `ICDPE-CARGO-VARIOS` + descripción `CTO COMP …`; este campo es **catálogo de tarifa**, no crea ítems ERP.
- Auto-alta de cargos desde el catálogo queda fuera de este sprint.

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/cuota_complementaria_panel_actividades.md` |
| Servicio | `activities/services/gestion_actividades_panel.py` |
| API | `activities/api/gestion_actividades_workspace.py` |
| UI | `public/js/gestion_actividades_workspace_panel.js` |
| Seed | `activities/services/estructura_actividades_seed.py` / sync CTO COMP |
| Tests | `activities/tests/test_gestion_actividades_panel.py` |

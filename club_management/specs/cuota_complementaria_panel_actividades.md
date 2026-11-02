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
Then nodos Escuelita / Femenino quedan en `6000` con título `CTO COMP BASQ ESC/FEM`
And nodos Masculino (Azul / Amarillo / Flex) quedan en `7000` con título `CTO COMP BASQ TIRA A/B/FLEX`.

---

## Scenario: seed enlaza CTO COMP de todos los deportes con cuota

Given la estructura de actividades sincronizada
When corre `seed_cuota_complementaria_tarifas`
Then cada grupo con concepto CTO COMP conocido queda con `monto_cuota_complementaria` y `titulo_cuota_complementaria`:

| Actividad | Grupo | Título CTO COMP | Monto |
|-----------|-------|-----------------|------:|
| Basquet | Masculino / Azul\|Amarillo\|Flex | CTO COMP BASQ TIRA A/B/FLEX | 7000 |
| Basquet | Femenino / Formativa\|Superior, Mixto / Escuela | CTO COMP BASQ ESC/FEM | 6000 |
| Futbol | FAFI, TABI A | CTO COMP FUTBOL FAFI/TABI | 8400 |
| Futbol | TABI B | CTO COMP FUTBOL ESC | 7400 |
| Voley Femenino | Tira | CTO COMP VOLEY | 6100 |
| Voley Femenino | Escuela Adolescente, Escuelita* | CTO COMP VOLEY ESC | 4300 |
| Patin Artistico | Patin Avanzado | CTO COMP PATIN AVANZADO | 2520 |
| Patin Artistico | Patin Intermedio | CTO COMP PATIN INTERMEDIO | 2160 |
| Patin Artistico | Patin Mini\|Teens\|Danza | CTO COMP PATIN INICIAL | 1230 |
| Patin Artistico | Adulto | CTO COMP PATIN ADULTOS | 1590 |

---

## Scenario: título CTO COMP editable en panel

Given un grupo con cuota complementaria
When Secretaría ve el panel
Then junto al monto aparece el campo **Concepto CTO COMP** (`titulo_cuota_complementaria`)
When guarda monto y/o título vía `set_cuota_complementaria`
Then ambos persisten en el nodo.

---

## Notas

- La facturación sigue usando ítem `ICDPE-CARGO-VARIOS` + descripción `CTO COMP …`; este campo es **catálogo de tarifa**, no crea ítems ERP.
- Auto-alta de cargos desde el catálogo queda fuera de este sprint.
- Deportes sin CTO COMP histórico (Boxeo, Yoga, etc.) quedan en 0 / vacío.

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/cuota_complementaria_panel_actividades.md` |
| Servicio | `activities/services/gestion_actividades_panel.py` |
| API | `activities/api/gestion_actividades_workspace.py` |
| UI | `public/js/gestion_actividades_workspace_panel.js` |
| Seed | `activities/services/estructura_actividades_seed.py` / sync CTO COMP |
| Tests | `activities/tests/test_gestion_actividades_panel.py` |

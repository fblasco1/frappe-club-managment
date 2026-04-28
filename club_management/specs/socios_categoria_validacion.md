# Spec: Socios categoría, validación y panel Secretaría

Given/When/Then scenarios for the next sprint. Implementation must follow TDD after this spec.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`

**Ruta en este workspace:** `club_manager_infra/development/frappe-bench/apps/club_management/club_management/specs/`

---

## Scenario: estado is read-only; only validar_socio changes it

Given a Socio document exists with `estado` = "Pendiente de Validación"
And a Secretaria user with permission to call `validar_socio`
When the user attempts to change `estado` via the form Save (direct field edit)
Then the save is rejected or `estado` remains unchanged except through whitelisted flow
And only the `validar_socio` method (or the Vitalicio system rule) may assign a new `estado`

---

## Scenario: Selecting Vitalicio manually is blocked

Given a Socio in "Pendiente de Validación" or "Requiere Corrección"
And Secretaria opens "Validar Socio" (prompt/dialog)
When Secretaria submits validation
Then "Vitalicio" is not offered as a selectable category in that dialog
And `validar_socio` rejects an explicit attempt to set `estado` to "Vitalicio" if passed as argument

---

## Scenario: fecha_alta set on first definitive estado assignment

Given a Socio with empty `fecha_alta`
When `validar_socio` assigns the first definitive category (Activo, Menor, Adherente, or Jubilado)
Then `fecha_alta` is set to today's date (server date)
And subsequent calls to `validar_socio` that change category do not overwrite `fecha_alta`

---

## Scenario: After 25 years from fecha_alta scheduled job promotes to Vitalicio

Given a Socio with `fecha_alta` set and `estado` in Activo, Adherente, or Jubilado
And elapsed years from `fecha_alta` to the job run date is >= 25
When the scheduled job (or equivalent batch process) runs
Then `estado` becomes "Vitalicio"
And the transition does not require manual validation in the Validar dialog

---

## Scenario: Vitalicio members have cuota_social = 0

Given Club Settings defines non-zero `cuota_social` for other categories
And a Socio with `estado` = "Vitalicio"
When the system resolves `cuota_social` for billing or for `cuota_social_actual` (if implemented)
Then the effective monthly/period cuota for that Socio is 0
And no category row in Club Settings is required to store Vitalicio with amount > 0

---

## Scenario: cuota_social determined by category table in Club Settings

Given Club Settings has a child table mapping categories (Activo, Adherente, Jubilado, Menor) to `cuota_social` amounts
And a Socio with `estado` = "Activo"
When resolving cuota from configuration (or displaying `cuota_social_actual`)
Then the amount matches the row for "Activo" in Club Settings
And unknown estado falls back to a defined behavior (e.g. 0 or ValidationError) as specified in tests

---

## Scenario: Grupo Familiar exists; a Socio can belong to one family

Given DocType "Grupo Familiar" (or domain-aligned "Family") exists with member child rows
And a Socio document has optional link `grupo_familiar` (or equivalent)
When Secretaria links a Socio to a Grupo Familiar
Then the link persists and the Socio can be listed among that group's members
And a Socio may belong to at most one grupo in this iteration (unless spec extended)

---

## Scenario: Sibling discount uses Family link not name matching

Given two Socios in the same Grupo Familiar with rol "Hijo" (or equivalent)
When discount logic counts siblings for pricing
Then eligibility is determined by membership in the same `grupo_familiar` / Family link
And discounts do not apply based solely on matching surnames or addresses

---

## Scenario: Report "Socios pendientes de validación" default filter

Given multiple Socios with mixed `estado` values
When a user opens the Report "Socios pendientes de validación"
Then the default filter restricts rows to `estado` = "Pendiente de Validación"
And the Report references DocType Socio with appropriate filter metadata

---

## Scenario: Workspace Secretaría with Report shortcut and no "Todos los Módulos"

Given Workspace "Secretaría" is installed
When Secretaria opens that workspace in Desk
Then a shortcut or primary link opens the Report "Socios pendientes de validación"
And the workspace layout does not include a "Todos los Módulos" block matching Club Management's module cards

---

## Scenario: Secretaria default_workspace via after_install hook

Given a fresh site after `bench install-app club_management` (or migrate running after_install)
When a User has role "Secretaria" and `default_workspace` was empty
Then `default_workspace` is set to "Secretaría"
And existing users who already chose another default are not overwritten (if that is the intended idempotent rule; align with tests)

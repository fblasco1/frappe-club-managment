# Spec: Carga rápida de ingreso y egreso

Secretaría registra ingresos eventuales y egresos operativos sin navegar el ERP completo. Los documentos subyacentes son **Sales Invoice**, **Purchase Invoice** y **Payment Entry**.

**Relacionado:** `rol_tesoreria_permisos.md`, `items_finance_cost_center.md`

**Modelo de egresos:** Purchase Invoice a Suppliers sembrados (sueldos, 931, ART, UTEDYC, servicios). **No** usa HRMS en esta fase.

---

## Scenario: registrar egreso crea Purchase Invoice

Given Secretaría autenticada y un Supplier + Item de gasto válidos
When registra egreso con monto, `due_date`, Cost Center y categoría `Personal`
Then se crea una `Purchase Invoice` submitted
And `club_concepto` = `Personal`
And la línea lleva el Cost Center indicado
And `outstanding_amount` = monto (si no se marcó pagado ahora).

---

## Scenario: egreso pagado ahora crea Payment Entry

Given el mismo egreso con `pagado_ahora = True` y modo de pago válido
When se confirma
Then la PI queda con outstanding 0
And existe un `Payment Entry` (Pay) submitted vinculado.

---

## Scenario: registrar ingreso crea Sales Invoice

Given Secretaría y un Item de ingreso con defaults contables
When registra ingreso con monto y Cost Center
Then se crea `Sales Invoice` submitted con ese Item y CC
And si `cobrado_ahora = True`, un `Payment Entry` (Receive) cancela el saldo.

---

## Scenario: Cost Center obligatorio

Given Secretaría omite Cost Center y el Item no tiene default resoluble
When intenta registrar ingreso o egreso
Then error de validación.

---

## Scenario: solo Secretaría / System Manager cargan

Given un usuario con solo rol `Tesoreria`
When llama a la API de carga rápida
Then `PermissionError`.

---

## Scenario: categoría club_concepto válida

Given un egreso con `club_concepto` fuera de `{Personal, Deportiva, Infraestructura, Estructura}`
When se intenta guardar
Then error de validación.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `finance/services/carga_rapida.py` |
| API | `finance/api/carga_rapida_desk.py` |
| Custom field | patch `add_finance_custom_fields` |
| Seed suppliers/items | `finance/setup/seed_finance_masters.py` |
| Tests | `tests/test_carga_rapida.py` |

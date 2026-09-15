# Spec: Integración Banco Supervielle (Cobros Plus) — API Wrapper

Given/When/Then scenarios for the Python service module `supervielle_api.py`.
Implementation must follow TDD after this spec.

**Ruta en Bench (relativa a `frappe-bench/`):** `apps/club_management/club_management/specs/`

---

## Scenario: Generación de hash SHA-256 para request payload (excluye `hash`)

Given un payload JSON a enviar a la API de Cobros Plus con campos escalares y (opcionalmente) un campo `"hash"`
And una `secret_key` configurada en `Cobros Plus Settings`
When el cliente genera el hash para ese payload
Then el cliente concatena **todos los valores** del JSON en el **orden exacto** en que aparecen
And el cliente **excluye** el valor del campo `"hash"` de la concatenación
And el cliente agrega al final de la cadena concatenada la `secret_key`
And el cliente calcula `SHA-256` de la cadena final y devuelve el hexadecimal en minúsculas

---

## Scenario: El hash se inyecta en el payload final antes de enviar

Given un payload base que aún no contiene `"hash"` o lo contiene vacío
When el cliente prepara la request para un endpoint de Cobros Plus
Then el payload final incluye el campo `"hash"` con el valor SHA-256 calculado

---

## Scenario: Errores HTTP o de negocio se loguean en Frappe y elevan excepción tipada

Given un endpoint de Cobros Plus que responde con HTTP distinto de 200
Or responde HTTP 200 pero el cuerpo JSON indica error de negocio (código/estado de error)
When el cliente ejecuta la request
Then se registra el detalle completo de respuesta en `frappe.log_error` con el título "Supervielle API Error"
And el cliente lanza `SupervielleIntegrationError` para que los controladores manejen el fallo sin romper el sistema


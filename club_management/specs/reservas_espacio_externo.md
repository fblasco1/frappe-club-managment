# Spec: Reservas externas online (token / SP-3)

**Relacionado:** `spaces_sprint_gestion.md` (Épica 1), `reservas_espacio_portal.md`,
`reservas_espacio_confirmacion.md`, `spaces_alquiler_externo.md`

Canal **público** (guest) para alquiler externo: sesión firmada de corta vida +
`token_acceso` por reserva. Confirmación Coordinación reutiliza el flujo Desk ya
entregado (`confirmar_reserva_espacio` / `rechazar_reserva_espacio`).

---

## Modelo

| Artefacto | Notas |
|-----------|--------|
| Club Settings `espacios_reserva_externa_habilitada` | Check; si 0, todo el canal guest falla cerrado |
| `Espacio.tarifa_externo` | Currency; si vacío/0 → `standard_rate` del ítem `ICDPE-ALQ-ARS-TEMP` |
| `Reserva Espacio.token_acceso` | Data unique; solo reservas `Alquiler externo` online; no enumerable |

Estados / ocupación: igual que portal socio (`Pendiente` y `Confirmada` ocupan).

Tipo / modalidad online externo: `Alquiler externo` + `modalidad_alquiler = Temporal`
(fecha + hora puntuales). Recurrente Desk queda fuera de este slice.

---

## Scenario: canal deshabilitado

Given `espacios_reserva_externa_habilitada = 0` (o ausente)
When un guest llama `abrir_sesion_reserva_externa` u otra API externa
Then `PermissionError`
And no se crea reserva.

---

## Scenario: abrir sesión externa

Given canal habilitado
When guest llama `abrir_sesion_reserva_externa()`
Then recibe `sesion_token` firmado (HMAC) con expiración (~2 h)
And un token manipulado o vencido no pasa `verify` en las APIs siguientes.

---

## Scenario: disponibilidad con sesión válida

Given sesión válida y espacios `alquilable=1` `habilitado=1`
When `get_espacios_disponibles_externo(sesion_token, fecha)`
Then lista slots libres/ocupados (misma ventana 08–22 que portal socio)
And `monto_arancel` usa tarifa **externo** (no la de socio si difieren)
And sin sesión / sesión inválida → PermissionError.

---

## Scenario: solicitar reserva externa

Given sesión válida, franja libre, `arrendatario_nombre` y contacto no vacíos
When `solicitar_reserva_externa(sesion_token, espacio, fecha, hora_inicio, hora_fin, arrendatario_nombre, arrendatario_contacto)`
Then crea `Reserva Espacio` `Alquiler externo` / `Temporal` / `Pendiente`
And persiste `monto_arancel`, `token_acceso` único y datos de arrendatario
And el slot ocupa el calendario
And la respuesta expone `reserva` + `token_acceso` (no IDs internos ajenos)
And solape → ValidationError sin crear doc.

---

## Scenario: gestión por token_acceso

Given una reserva externa Pendiente con `token_acceso = T`
When `get_reserva_externa(T)`
Then devuelve detalle acotado (espacio, fecha, horas, estado, monto, comprobante si hay)
When `adjuntar_comprobante_externo(T, file_url)` con PDF
Then setea `comprobante` + `fecha_comprobante` y sigue `Pendiente`
When se usa token inexistente / de otra reserva
Then PermissionError (fail closed; sin filtrar existencia con mensajes distintos útiles a enumeración — mensaje genérico).

---

## Scenario: no cruza con portal socio

Given guest con sesión externa
When intenta endpoints de portal socio autenticados
Then siguen exigiendo sesión Socio (sin bypass).
Given token_acceso de reserva externa
When un socio autenticado no es dueño (no aplica)
Then no usa ese token en APIs socio; las APIs socio solo miran `get_current_socio()`.

---

## Seguridad

- `@frappe.whitelist(allow_guest=True)` **solo** con gate: canal habilitado +
  `sesion_token` HMAC vigente **o** `token_acceso` de la reserva.
- Tests obligatorios: canal off, token malo, token vencido, cross-reserva.
- XSS/files: solo PDF vía File URL ya validada (reutilizar reglas de confirmación).
- Sin `allow_guest` en confirmación Desk.

## Fuera de alcance (este slice)

- Email automático a Coordinación.
- Recurrente online / Cobrand.
- Rate limit redis avanzado (seguir con fail-closed + tokens).

**UI Next:** ruta pública `/alquiler` (BFF + upload PDF vía `upload_y_adjuntar_comprobante_externo`).

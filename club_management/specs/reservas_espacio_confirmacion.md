# Spec: Confirmación Coordinación + comprobante PDF (Épica 1 / SP-3·SP-7)

**Relacionado:** `spaces_sprint_gestion.md` (Épica 1), `reservas_espacio_portal.md`,
`spaces_fases_futuras.md`, `portal_socio_alcance.md`

Cierra el flujo operativo de una reserva online **Pendiente** (bloqueo):
adjunta comprobante de transferencia (fase 1) y Coordinación confirma o rechaza.

---

## Modelo (campos)

Sobre `Reserva Espacio`:

| Campo | Tipo | Notas |
|-------|------|--------|
| `comprobante` | Attach | PDF de transferencia; opcional hasta confirmar en MVP socio |
| `fecha_comprobante` | Datetime | set al adjuntar; read_only |
| `motivo_rechazo` | Small Text | obligatorio al rechazar |

Estados que ocupan (sin cambio): `Pendiente`, `Confirmada`.
`Cancelada` libera el slot (`slot_key` vacío).

---

## Scenario: socio adjunta comprobante PDF

Given una `Reserva Espacio` tipo `Alquiler socio` en `Pendiente` del socio de sesión
When llama `adjuntar_comprobante_reserva(reserva, file_url)` (o upload File + enlace)
Then `comprobante` y `fecha_comprobante` quedan persistidos
And el estado sigue `Pendiente` (sigue bloqueando el slot)
And otro socio no puede adjuntar a esa reserva (PermissionError).

---

## Scenario: Coordinación lista cola pendiente

Given rol `Coordinacion` (o `Secretaria` / System Manager)
When llama `list_reservas_pendientes_confirmacion()`
Then recibe reservas en `Pendiente` (alquiler socio/externo online) ordenadas por fecha
And Guest / Socio sin Desk no pueden listar.

---

## Scenario: Coordinación confirma

Given reserva `Pendiente` con bloqueo activo
And no hay conflicto nuevo de ocupación Confirmada/grilla
When `confirmar_reserva_espacio(reserva)`
Then estado = `Confirmada`
And el slot sigue ocupado (firme)
When hay conflicto al confirmar
Then ValidationError con mensaje claro y **no** cambia el estado.

---

## Scenario: Coordinación rechaza

Given reserva `Pendiente`
When `rechazar_reserva_espacio(reserva, motivo)`
Then estado = `Cancelada`, `motivo_rechazo` seteado
And `slot_key` vacío (libera ocupación)
And Guest no puede rechazar.

---

## Seguridad

- Portal: identidad solo de sesión (`get_current_socio`); sin `socio` del cliente.
- Desk: `ensure_spaces_write_access()` (Coordinacion / Secretaria / System Manager).
- Adjuntos: solo PDF; File vinculado a la reserva.

## Fuera de alcance (este tramo)

- UI Next pública `/alquiler` (API guest token entregada en `reservas_espacio_externo.md`).
- Cobrand / pago online.
- Job de retención/purge de PDFs (defaults documentados en sprint).
- Notificación email automática (cola Desk basta en MVP; email Coordinación en slice siguiente).

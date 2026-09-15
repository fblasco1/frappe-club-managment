# Spec: Reservas de espacios — núcleo transaccional + portal (SP-3 / SP-7)

**Relacionado:** `spaces_catalogo_ocupacion.md`, `spaces_sprint_gestion.md`,
`spaces_fases_futuras.md`, `spaces_fixtures_partidos.md`, `portal_socio_alcance.md`,
`cargo_extra_socio.md`

Prerrequisito del gate de release del Portal del Socio: núcleo transaccional de
`Reserva Espacio` y API autenticada para solicitar franjas alquilables.

## Modelo

DocType existente **`Reserva Espacio`** (módulo Spaces). Campos relevantes al
portal (además de los ya usados por Desk/fixtures):

| Campo | Tipo | Notas |
|-------|------|--------|
| `espacio` | Link → Espacio | obligatorio |
| `socio` | Link → Socio | obligatorio en `Alquiler socio` portal |
| `fecha` | Date | franja puntual |
| `hora_desde` / `hora_hasta` | Time | API portal acepta alias `hora_inicio` / `hora_fin` |
| `monto_arancel` | Currency | tarifa del canal socio al solicitar |
| `estado` | Select | `Borrador` (Desk, no ocupa) · **`Pendiente`** (bloqueo) · `Confirmada` · `Cancelada` |
| `tipo` | Select | portal usa **`Alquiler socio`** |
| `slot_key` | Data unique | índice lógico `(espacio, fecha, slot)` solo en estados que ocupan |
| `cargo_socio` | Link → Cargo Socio | borrador de cargo generado al solicitar |

**Estados que ocupan el calendario:** `Pendiente`, `Confirmada`.
`Borrador` y `Cancelada` **no** ocupan.

**Índice único compuesto:** `slot_key = "{espacio}|{fecha}|{hora_desde}|{hora_hasta}"`
cuando el estado ocupa; `NULL`/vacío al cancelar o en borrador Desk. Evita dos
reservas activas con el mismo slot exacto. Solapes parciales los rechaza
`availability.assert_no_overlap_with_occupancy` (grilla, excepciones, fixtures
FMV/ligas y otras reservas ocupantes).

---

## Scenario: socio activo solicita franja libre

Given un `Espacio` con `alquilable = 1` y `habilitado = 1`
And un Website User con rol `Socio` vinculado a un único `Socio` en estado `Activo`
And la franja no solapa grilla, excepciones, fixtures ni otras reservas ocupantes
When llama `solicitar_reserva_espacio(espacio, fecha, hora_inicio, hora_fin)`
Then se crea `Reserva Espacio` tipo `Alquiler socio`, estado `Pendiente`, `socio` = el de sesión
And el slot queda bloqueado (ocupa calendario)
And se genera un `Cargo Socio` borrador (`Pendiente`, sin auto-facturar) enlazado en `cargo_socio`
And `monto_arancel` queda persistido en la reserva.

---

## Scenario: rechazo por solape con fixture de torneo

Given un fixture FMV/liga (u otra `Reserva Espacio` Confirmada con `origen_fixture`)
que ocupa el mismo espacio/fecha/horario
When el socio activo solicita esa franja
Then se lanza `ValidationError`
And no se crea reserva ni cargo.

---

## Scenario: rechazo por socio no activo

Given el socio de sesión no está en estado `Activo` (p. ej. `Pendiente de Inscripción` o `Moroso`)
When solicita una reserva
Then se lanza `ValidationError` (o `PermissionError` documentado)
And no se crea reserva.

---

## Scenario: aislamiento entre socios

Given dos socios activos A y B con usuarios distintos
When A solicita una reserva
Then la reserva queda vinculada solo a A
And B no puede leer ni mutar esa reserva vía API portal (fail closed; sin parámetro `socio` del cliente).

---

## Scenario: grilla de disponibilidad portal

Given una fecha y opcionalmente `tipo_espacio`
When un socio autenticado llama `get_espacios_disponibles(fecha, tipo_espacio=None)`
Then recibe espacios `alquilable=1` + `habilitado=1` (filtrados por tipo si aplica)
And cada espacio incluye slots horarios con estado `libre` u `ocupado`
And los ocupados reflejan grilla + excepciones + reservas en estados que bloquean
(incluyendo fixtures Confirmada y solicitudes `Pendiente`).

---

## Seguridad

- Endpoints `@frappe.whitelist()` autenticados (sin `allow_guest`).
- Identidad solo de `frappe.session.user` → `get_current_socio()`; el cliente **no**
  envía `socio`.
- Gate: rol `Socio` + Socio único vinculado; Guest / staff sin vínculo → error genérico.
- Permisos Desk Spaces no se reutilizan para el portal: insert vía servicio con
  `ignore_permissions` tras el gate de sesión.

## Fuera de alcance (este tramo)

- Confirmación / rechazo por Coordinación (cola Desk).
- Comprobante PDF / Cobrand.
- Canal externo con token.
- Tarifas configurables distintas socio vs externo en Club Settings (MVP: ítem
  `ICDPE-ALQ-ARS-TEMP` / rate estándar; override opcional en spec futura).

# Spec: Espacios — fases futuras (fuera de implementación actual)

Documento de alcance **no implementado** en el tramo de catálogo + grilla +
ocupación interna. Ver `spaces_catalogo_ocupacion.md` para lo entregado.

**Sprint activo propuesto:** `spaces_sprint_gestion.md` (reservas online,
disponibilidad en vivo, carga de planillas, reporte Comisión Directiva).

---

## Fase: portal socio / equipo

### Scenario (futuro): socio reserva espacio alquilable

Given un `Espacio` con `alquilable = 1` y `habilitado = 1`
And el socio está autenticado en el portal
When solicita una reserva para cumpleaños o evento familiar
Then se crea un pedido de reserva acotado a **su** `Socio`
And no puede ver ni modificar reservas de otros socios.

### Scenario (futuro): equipo reserva para asado

Given un `Equipo Actividad` y un espacio alquilable
When un operador autorizado (o flujo futuro de equipo) reserva el espacio
Then la reserva referencia `equipo_actividad` y el slot queda ocupado al confirmarse.

### Scenario (futuro): espacio no alquilable no aparece en portal

Given `Espacio` con `alquilable = 0`
When el socio lista espacios reservables
Then ese espacio **no** aparece.

---

## Fase: alquiler a externos con costo

> **Ocupación Desk Temporal/Recurrente:** implementada en `spaces_alquiler_externo.md`.
> Lo siguiente sigue pendiente.

### Scenario (futuro): cobro con ítems ICDPE-ALQ

Given un alquiler externo Confirmado
When Tesorería/Secretaría factura el alquiler
Then usa ítems `ICDPE-ALQ-*-TEMP` o `ICDPE-ALQ-*-REC` según modalidad
And el Cost Center es `Temporal - ICDPE` o `Recurrente - ICDPE`.

### Scenario (futuro): cobro online Cobrand / Supervielle

Given un alquiler externo pendiente de pago
When el externo paga online
Then el ID de transacción del gateway se persiste en Payment Log (o equivalente)
And el webhook es idempotente (no se reutiliza el ID en otro pago).

### Scenario (futuro): SIRO no aplica

Given cualquier diseño de cobro de alquiler
Then **no** se documenta ni implementa flujo SIRO.

---

## Notas de diseño

- `alquilable` ya existe en `Espacio` como metadato; las reglas de este archivo
  lo activan.
- Reutilizar Cost Centers e ítems ya sembrados; no inventar endpoints de cobro.

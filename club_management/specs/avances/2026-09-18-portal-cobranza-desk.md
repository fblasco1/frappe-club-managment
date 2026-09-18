# Avance 2026-09-18 — Portal finance, renditions scheduler y Desk cobranza

**Fecha:** 2026-09-18  
**Proyecto:** ICDPE / `club_management`  
**Autores de sesión:** Cursor + Francisco  
**Integración a producción:** planificada para el lunes siguiente (no deploy hoy)

---

## Resumen ejecutivo

En `develop` quedó unificado el hardening de portal socio, el polling horario de
rendiciones Supervielle (con flag Desk), el estado de cuenta BL-6d para el portal,
y mejoras de cobranza Desk: nombre del socio en el ticket, reimpresión desde
historial y corrección de medio de pago (cancel + recreate).

---

## 1. Portal socio — hardening en develop

| Acción | Detalle |
|--------|---------|
| Origen | `feat/bl6-portal-socio` @ `3604918` |
| En develop | cherry-pick → `2a2772e` |
| Contenido | `update_foto_perfil`, validación de URL imagen, specs de perfil |

### Suite dirigida

```bash
bench --site dev.localhost run-tests --module club_management.members.test_portal_socio
```

- Loader: `members/test_portal_socio.py` (perfil + inscripción + URL/sesión)
- **50/50 OK**, exit 0 (incluye 2 tests de foto del hardening)

---

## 2. Scheduler rendiciones Supervielle

| Pieza | Detalle |
|-------|---------|
| Hook | `scheduler_events["hourly"]` → `process_renditions_scheduler_tick` |
| Flag Desk | `Supervielle Settings.enable_automated_polling` (default off) |
| Errores API | timeout / HTTP ≠ 200 → `Payment Gateway Event` con `severity = High` sin tumbar la cola |
| Schema | `payment_log` deja de ser `reqd` en PGE (auditoría de poll sin log) |

Tests: `test_supervielle_renditions` **7/7**. Conciliación existente **9/9**.

---

## 3. Portal BL-6d — estado de cuenta

| Artefacto | Path |
|-----------|------|
| Spec | `specs/portal_socio_estado_cuenta.md` |
| API | `members/api/portal_finance.py` → `get_estado_cuenta_socio()` |
| Tests | `tests/test_portal_finance.py` **5/5** |

- Guest / sin socio → `PermissionError`
- Solo SI `docstatus=1` y `outstanding_amount > 0` del socio de sesión
- Últimos 5 PE con `recibo_url`

---

## 4. Cobranza Desk — ticket y medio de pago

| Función | Detalle |
|---------|---------|
| Nombre en ticket | `Socio: Apellido, Nombre` + `Nº socio` en ESC/POS / texto |
| Reimpresión | Botón **Imprimir ticket** en historial (y en detalle) |
| Corregir medio | Cancela PE + recrea con mismo monto/fecha/facturas; motivo obligatorio; bloquea PE con Payment Log gateway |

Specs: `recibo_pago_escpos.md`, `historial_pagos_socio.md`, `corregir_medio_pago_cobro.md`.

Tests: `test_recibo_pago` **10/10**; `test_corregir_medio_pago_cobro` **5/5**.

### Uso Secretaría (post-migrate / hard refresh Desk)

1. Historial de pagos en Socio → **Imprimir ticket** (transferencias sin ticket).
2. **Corregir medio** → medio nuevo + motivo → opcional reimprimir ticket.

---

## 5. Pendiente lunes (prod)

- [ ] Merge/deploy de este `develop` a Hetzner (migrate + clear-cache / build assets si hace falta)
- [ ] Activar `enable_automated_polling` solo cuando Cobrand/sandbox esté listo
- [ ] UAT Secretaría: reimpresión ticket + corregir Cash → Wire Transfer
- [ ] Cablear UI Vercel de deudas al endpoint `get_estado_cuenta_socio` (si aún no está)

---

## Semáforo

| Ítem | Estado |
|------|--------|
| Código en `develop` local | Listo (push en esta sesión) |
| Prod Hetzner | **No** — lunes |
| Polling rendiciones prod | Off hasta flag Desk |

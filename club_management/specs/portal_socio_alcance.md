# Portal del Socio — alcance, funcionalidades básicas y plan

**Relacionado:** `portal_socio_inscripcion.md` (BL-6), `login_dual.md`,
`portal_alta_grupo_familiar.md`, `alta_sin_pago_online.md`, `spaces_fases_futuras.md`

Este documento delimita el **área autenticada del socio** en el sitio del club
(Vercel) frente al wizard público de alta y al Desk de Secretaría. No sustituye
el contrato de BL-6; lo ubica en el producto.

---

## Qué es (y qué no es)

| Superficie | Audiencia | Identidad | Rol |
|------------|-----------|-----------|-----|
| Campaña `/asociate` | Visitante | Guest | Explicar el proceso de asociación. |
| Wizard `/asociate/inscripcion` | Pre-asociado | Guest + token | Alta pública (BL-10, ya en prod). |
| **Portal del socio** | Socio habilitado | `frappe.session.user` + rol `Socio` | Autogestión acotada post-alta. |
| `/inscripcion-actividades` (Frappe) | QA | `pago_token` | Cliente legacy; no es el portal productivo. |
| Desk Secretaría | Staff | Usuario Desk | Operación interna; no es portal. |

El portal **no** es el formulario de asociación. El wizard deja al interesado
pre-asociado; Secretaría valida, cobra (manual o, más adelante, gateway) y deja
al `Socio` en `Pendiente de Inscripción` con Website User. Recién ahí entra al
portal.

---

## Principios

1. Identidad solo de sesión. Ningún endpoint de portal acepta `socio`, email o
   DNI del cliente para decidir qué leer o mutar.
2. Fail closed: Guest, rol incorrecto o vínculo `User`↔`Socio` no único → error
   genérico.
3. El frontend vive en Vercel; Frappe expone APIs autenticadas, CORS acotado y
   CSRF. Desk no se reusa como UI del socio.
4. Cobranza online (Cobrand / Supervielle) es épica aparte. El portal consume
   estados ya persistidos (`Pendiente de Inscripción`, `Activo`, deuda), no
   inventa el cobro.
5. El socio no elige tira deportiva ni equipo; eso sigue en Secretaría.

---

## Funcionalidades básicas (MVP del portal)

Orden de entrega. Solo el ítem 1–4 entra en el primer corte usable.

| # | Función | Estado | Spec / notas |
|---|---------|--------|----------------|
| 1 | Login email o DNI | Hecho | `login_dual.md` |
| 2 | Contexto del socio (estado, elegibilidad) | Backend BL-6 | `get_contexto_socio` |
| 3 | Catálogo de inscripción (plana / deporte / variante) | Backend BL-6 | `get_catalogo_inscripcion` |
| 4 | Confirmar actividades e inscripciones propias | Backend BL-6 | `confirmar_inscripcion_actividades`, `list_inscripciones_propias` |
| 5 | Home autenticado (saludo, estado, CTA de inscripción o “ya activo”) | Pendiente UI Vercel | Reusa 2–4 |
| 6 | Ver inscripciones actuales (solo lectura) | API lista lista; falta UI | Sin baja ni cambio post-alta |
| 7 | Enlace al área de pago cuando exista gateway | Fuera de BL-6 | Supervielle / Cobrand |
| 8 | Carnet digital | Fuera de MVP portal | XSS: no renderizar HTML crudo |
| 9 | Historial de pagos del socio | Fuera de MVP portal | Hoy es Desk (`historial_pagos_socio.md`) |
| 10 | Autogestión de datos personales / documentación | Fuera de MVP portal | Secretaría edita; portal como mucho “ver y solicitar corrección” |
| 11 | Reserva de espacios alquilables | Futuro | SP-7, `spaces_fases_futuras.md` |

### Scenario: socio pendiente ve solo lo suyo

Given un Website User con rol `Socio` y un único `Socio` vinculado
And el socio está `Pendiente de Inscripción`
When abre el portal autenticado
Then ve su estado y el catálogo permitido
And puede confirmar selecciones válidas
And no ve datos de otro socio ni tiras/equipos internos.

### Scenario: socio activo no reabre el alta de actividades

Given un socio `Activo` con inscripciones
When entra al portal
Then puede ver el resumen de inscripciones propias
And una confirmación idéntica es idempotente
And no puede inscribir a otra persona ni alterar el `socio` del documento.

### Scenario: visitante y staff no usan esta superficie

Given Guest, un usuario sin rol `Socio`, o Secretaría en Desk
When llama a las APIs del portal o abre el área Vercel del socio
Then Guest/rol incorrecto fallan cerrados
And Secretaría opera por Desk, no por el portal.

---

## Fuera de alcance del portal (hasta nueva spec)

- Checkout y conciliación online.
- Cambio, baja o transferencia de inscripciones desde el sitio.
- Asignación de grupo/tira o equipo deportivo por el socio.
- Edición libre de categoría, estado, número de socio o cuota.
- Uso de `pago_token` como sesión.
- Reutilizar páginas Frappe `www/` como UI productiva.

---

## Plan de implementación

### Fase A — Backend Frappe (esta branch `feat/bl6-portal-socio`)

1. Metadata `tipo_inscripcion_portal` / `portal_socio_elige`.
2. API autenticada + permisos PostgreSQL + `validate` atado a sesión.
3. Suite de aislamiento (dos socios) y reglas plana / deporte / variante.
4. `bench migrate` en el sitio de desarrollo.

**Hecho en esta branch.** Siguiente: suite dirigida verde en Docker.

### Fase B — Contrato Vercel ↔ Frappe

1. CORS solo orígenes del sitio; cookies + CSRF en mutaciones.
2. `inscripcion_url` por ambiente apuntando al área autenticada Vercel.
3. Cliente Vercel: login existente → contexto → catálogo → confirmar.
4. UAT local: cobro manual Secretaría → socio pendiente → login → inscripción.

### Fase C — Cutover

1. Dejar `/inscripcion-actividades` + `pago_token` como QA hasta UAT verde.
2. No autorizar el portal productivo con token de pago.
3. Documentar el disparador: cobro manual ahora; callback Supervielle después.

### Fase D — Home mínimo

1. Pantalla autenticada con estado, CTA de inscripción o listado propio.
2. Errores genéricos; sin IDs internos de `Socio` en la respuesta salvo
   necesidad documentada.

### Fase E — Extensiones (specs nuevas, TDD)

1. Historial de pagos en portal (reusar servicio Desk con alcance de sesión).
2. Carnet (plantilla escapada).
3. Solicitud de corrección de datos.
4. Reservas de espacios (SP-7).

Cada extensión: spec Given/When/Then → test con dos usuarios → API con sesión
→ UI Vercel. No se agregan campos “por las dudas”.

---

## Decisiones de corte MVP

- **Sí ahora:** login + inscripción post-alta + listado propio + aislamiento.
- **Después:** pagos, carnet, perfil, espacios.
- **Nunca en el portal:** operar como Secretaría, elegir equipo competitivo,
  confiar en el body para la identidad.

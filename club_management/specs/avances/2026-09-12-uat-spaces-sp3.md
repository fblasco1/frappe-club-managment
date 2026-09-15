# UAT smoke — Spaces SP-3 (local)

**Fecha:** 2026-09-12  
**Sitio:** `dev.localhost`  
**Runner:** `bench --site dev.localhost execute club_management.spaces.qa.uat_spaces_smoke.run`

## Resultado

| Flujo | Evidencia | Estado |
|-------|-----------|--------|
| Externo: sesión → slot → Pendiente → PDF → confirmar Coordinación → Confirmada | `RES-2026-00342` | PASS |
| Socio portal: solicitar → PDF → confirmar Coordinación → Confirmada | `RES-2026-00343` | PASS |
| UI `/alquiler` | HTTP 200 (`localhost:3000`) | PASS |
| BFF `/api/alquiler?fecha=` | HTTP 200 | PASS |
| Canal Club Settings | `espacios_reserva_externa_habilitada=1` | ON |

## Gate release (código local)

- Reservas externas (token + UI) — listo para merge/UAT humano opcional
- Reservas portal socio (API + UI + confirmación) — listo
- Siguiente: merge/push `develop` + dual-deploy Hetzner + Vercel; luego Supervielle sandbox

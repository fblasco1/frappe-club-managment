---
name: qa-solicitud-supervisada
description: Ejecuta el flujo E2E de Solicitud de Asociación en modo supervisado (terminal bench execute, tests CI, browser MCP Playwright). Usar cuando el usuario pida QA manual automatizado, recorrido feliz solicitud, o validación visual Desk/pago-stub.
---

# QA supervisado — Solicitud de Asociación

## Cuándo usar

- Validar el flujo manual (alta → validar → pago → Activo) sin repetir pasos a mano.
- Demos o regresión antes de release con **supervisión humana** entre fases.
- Complementar `bench run-tests` (CI headless) con UI opcional.

## Tres niveles (en orden)

| Nivel | Herramienta | Supervisión |
|-------|-------------|-------------|
| 1 CI | `bench run-tests --module ...test_flujo_solicitud_completo` | No (automático) |
| 2 Terminal | `bench execute club_management.members.qa.run_supervised.run` | Sí (Enter entre pasos) |
| 3 Browser | Playwright `npm run qa:e2e:headed` o **browser MCP** en Cursor | Sí (ventana visible) |

Spec: `club_management/specs/solicitud_asociacion_publica.md` — sección «Flujo E2E».

## Nivel 1 — CI (siempre primero)

Dentro del contenedor `frappe` / bench:

```bash
cd /workspace/development/frappe-bench
bench --site dev.localhost run-tests --app club_management \
  --module club_management.members.tests.test_flujo_solicitud_completo
```

Si falla, **no** abrir browser hasta corregir.

## Nivel 2 — Q&A en terminal (supervisado)

```bash
bench --site dev.localhost execute club_management.members.qa.run_supervised.run
```

Sin pausas (smoke):

```bash
bench --site dev.localhost execute club_management.members.qa.run_supervised.run \
  --kwargs '{"auto": True}'
```

(`bench execute` evalúa Python: usar `True`, no JSON `true`.)

Con corrección intermedia:

```bash
bench --site dev.localhost execute club_management.members.qa.run_supervised.run \
  --kwargs '{"con_correccion": true}'
```

Cada paso imprime JSON de evidencia; el operador pulsa Enter o `n` para abortar.

## Nivel 3 — Browser supervisado (Agent)

### Pre-requisitos

- Stack Docker arriba (`dev.localhost:8000`).
- Usuario Secretaría: `secretaria@dev.local` / `Secretaria123!` (o el del sitio).
- Workflow migrado.

### Guion Q&A (usar `AskQuestion` entre fases si el usuario pidió supervisión)

1. **Alta pública** — Navegar a `http://dev.localhost:8000/solicitud-asociacion`, completar formulario adulto, enviar.  
   - Pregunta: ¿Apareció el `token_seguimiento` en pantalla?  
   - Verificar API: `consultar_solicitud?token=...` → `Pendiente`.

2. **Desk Secretaría** — Login → buscar «Solicitud Asociacion» → abrir la última `Pendiente`.  
   - Pregunta: ¿Datos correctos?  
   - Acción workflow **Validar**.  
   - Pregunta: ¿`socio_generado` poblado y Socio en **Pendiente de Pago**?

3. **Pago stub** — Abrir link del email o URL  
   `http://dev.localhost:8000/pago-stub?token=<pago_token>`  
   (el token firmado sale del email de validación o del resumen de `run_supervised`).  
   - Clic **Marcar como pagado**.  
   - Pregunta: ¿Socio en **Activo** en Desk?

4. **Opcional corrección** — Solicitar Corrección → actualizar vía token → Reenviar → Validar de nuevo.

### Herramientas MCP

- `browser_navigate`, `browser_snapshot`, `browser_click` (refs del snapshot).
- Tras cada acción que cambie la página: nuevo `browser_snapshot`.
- Si login/captcha bloquea: pedir al usuario que tome el control y avisar cuando continuar.

### Playwright local (alternativa al MCP)

**Ejecutar en el host (WSL), no dentro del contenedor `frappe`.**

```bash
cd development/frappe-bench/apps/club_management
npm install
npx playwright install chromium
export PLAYWRIGHT_BASE_URL=http://localhost:8000
export QA_SECRETARIA_EMAIL=secretaria@dev.local
export QA_SECRETARIA_PASSWORD=Secretaria123!
QA_SUPERVISED=1 npm run qa:e2e:headed
```

Si aparece `playwright: not found` → falta `npm install` (los scripts usan `npx playwright`).

## Evidencia a reportar al usuario

- `token_seguimiento`, `solicitud` name, `socio` name, estados workflow y Socio.
- Captura o snapshot en pasos 2 y 3 si hubo UI.
- Si Nivel 1 verde y Nivel 3 falla → bug de UI, no de negocio.

## No hacer

- No saltar Nivel 1 en CI/PR.
- No commitear contraseñas reales; usar env vars en Playwright.
- No usar `innerHTML` con datos del solicitante en scripts de QA.

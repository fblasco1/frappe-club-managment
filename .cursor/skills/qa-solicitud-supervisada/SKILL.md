---
name: qa-solicitud-supervisada
description: QA del flujo Solicitud de Asociación. En WSL usar browser MCP de Cursor para UI supervisada; bench/Playwright headless para lógica. Usar cuando pidan testeo manual automatizado o Q&A del flujo solicitud.
---

# QA supervisado — Solicitud de Asociación

## Entorno WSL (regla principal)

WSL **no tiene ventana gráfica** para `playwright --headed` salvo que configures WSLg/X11.

| Objetivo | Herramienta correcta |
|----------|----------------------|
| Lógica / CI (sin UI) | `bench run-tests` + `bench execute …run_supervised` |
| UI supervisada (ver pantalla) | **Browser MCP de Cursor** (`cursor-ide-browser`) |
| Smoke HTTP + formulario sin ver ventana | `npm run qa:e2e` (Playwright **headless**) |

**No** pedir `npm run qa:e2e:headed` en WSL sin WSLg; usar **Cursor Browser**.

Spec: `club_management/specs/solicitud_asociacion_publica.md` — «Flujo E2E».

URLs desde Cursor (Windows) hacia Docker en WSL: **`http://localhost:8000`** (puerto mapeado por Docker Desktop).

---

## Nivel 1 — CI (siempre primero)

En el contenedor `frappe`:

```bash
cd /workspace/development/frappe-bench
bench --site dev.localhost run-tests --app club_management \
  --module club_management.members.tests.test_flujo_solicitud_completo
```

Si falla, corregir antes de abrir browser.

---

## Nivel 2 — Q&A terminal (API, supervisado con Enter)

```bash
bench --site dev.localhost execute club_management.members.qa.run_supervised.run
```

Sin pausas: `--kwargs '{"auto": True}'` (Python `True`, no JSON `true`).

Equivalente al flujo manual de negocio sin abrir Desk.

---

## Nivel 3 — UI supervisada con **Cursor Browser** (WSL)

El agente debe usar el MCP **`cursor-ide-browser`** (no Playwright headed).

### Pre-requisitos

- Docker / devcontainer con sitio en **puerto 8000** publicado al host.
- Usuario Secretaría: `secretaria@dev.local` / `Secretaria123!`
- MCP browser habilitado en Cursor.

### Orden de herramientas MCP

1. `browser_navigate` → URL
2. `browser_lock` (si ya hay pestaña)
3. `browser_snapshot` → leer refs
4. Interacción (`browser_click`, `browser_fill`, …) con **refs del snapshot**
5. Tras cada acción que cambie la página → **nuevo** `browser_snapshot`
6. Al terminar → `browser_unlock`

### Guion Q&A (pausar con `AskQuestion` si el usuario pidió supervisión)

**Base URL:** `http://localhost:8000`

#### Fase A — Alta pública

1. `browser_navigate` → `http://localhost:8000/solicitud-asociacion`
2. `browser_snapshot` → completar formulario adulto (DNI/email únicos, adjuntos si el formulario los exige).
3. Enviar formulario.
4. Confirmar en pantalla: mensaje con **`token_seguimiento`** (sin exponer `name` del doc).
5. *(Opcional)* Verificar API en terminal WSL:
   `curl "http://localhost:8000/api/method/club_management.members.api.solicitud_publica.consultar_solicitud?token=TOKEN"`

#### Fase B — Desk Secretaría

1. `browser_navigate` → `http://localhost:8000/login`
2. Login: `secretaria@dev.local` / `Secretaria123!`
3. Ir a lista **Solicitud Asociacion** (Awesome Bar o ruta `/app/solicitud-asociacion`).
4. Abrir la solicitud recién creada (`Pendiente`).
5. Menú **Acciones** → **Validar**.
6. Confirmar en formulario: `socio_generado`, `workflow_state` = Validada.
7. Abrir **Socio** vinculado → estado **Pendiente de Pago**.

#### Fase C — Pago stub

Obtener token de pago desde WSL (no adivinar):

```bash
bench --site dev.localhost execute club_management.members.qa.run_supervised.run \
  --kwargs '{"auto": True, "dni": "DNI_USADO", "email": "EMAIL_USADO"}'
```

Copiar `pago_token` del JSON, o firmar tras validar desde Desk con consola Frappe.

1. `browser_navigate` → `http://localhost:8000/pago-stub?token=PAGO_TOKEN`
2. Clic **Marcar como pagado**.
3. Verificar en Desk: **Socio** → estado **Activo**.

#### Fase D — Corrección (opcional)

1. Desk: **Solicitar Corrección** en otra solicitud de prueba.
2. API o futuro formulario con token; hoy: `actualizar_solicitud` vía curl/Postman con token.
3. **Reenviar** → **Validar** de nuevo.

### Si el browser no carga localhost

- Comprobar `curl -I http://localhost:8000/` desde WSL.
- Revisar que Docker Desktop expone 8000; reiniciar compose si hace falta.
- No usar `dev.localhost` en Cursor si no está en `C:\Windows\System32\drivers\etc\hosts` de Windows.

---

## Nivel 3b — Playwright en WSL (solo headless)

Para smoke automatizado **sin ventana**:

```bash
cd ~/ERSport/club_manager_infra/development/frappe-bench/apps/club_management
./scripts/check-node-env.sh
npm install
./scripts/install-playwright-browser.sh
export PLAYWRIGHT_BASE_URL=http://localhost:8000
npm run qa:e2e
```

`qa:e2e:headed` / `QA_SUPERVISED=1` → solo con **WSLg** (`echo $DISPLAY` definido) o en máquina con GUI.

---

## Evidencia a reportar

- `token_seguimiento`, name de solicitud/socio, estados workflow y Socio.
- Screenshots MCP si hubo fallo visual.
- Si Nivel 1 verde y Browser falla → bug de UI/plantilla, no de servicios.

## No hacer

- No usar Playwright `--headed` en WSL sin display como sustituto de Cursor Browser.
- No saltar Nivel 1 en PRs.
- No rellenar contraseñas en commits; Secretaría es solo dev.

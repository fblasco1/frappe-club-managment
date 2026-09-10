# BL-6 — Portal autenticado del socio: inscripción a actividades

**Backlog:** BL-6
**Relacionado:** `activities_modulo.md`, `activities_jerarquia.md`, `inscripcion_gestion_desk.md`, `login_dual.md`, `alta_sin_pago_online.md`

## Decisiones de contrato

- BL-6 es una funcionalidad para un **socio autenticado**. La identidad se obtiene exclusivamente de `frappe.session.user`.
- Ningún endpoint acepta `socio`, `user`, email o número de socio enviados por el cliente para decidir qué registros leer o modificar.
- El `pago_token` existente queda limitado al flujo legacy `/inscripcion-actividades` para QA. No autoriza el portal productivo ni sustituye la sesión.
- El canal de cobro no forma parte de BL-6. Un proceso confiable de backend —cobro manual de Secretaría o callback validado— deja al socio en `Pendiente de Inscripción`.
- Confirmar al menos una selección válida crea las inscripciones y pasa al socio a `Activo`. Una selección vacía no activa ni modifica al socio.
- El frontend definitivo vive en Vercel; la página Frappe actual es únicamente un cliente de QA del mismo contrato.

---

## Arquitectura objetivo

| Capa | Rol |
|------|-----|
| **Frontend** | Sitio del club en **Vercel**, dentro del área autenticada del socio. |
| **Backend** | Frappe/ERPNext en Hetzner (`gestion.icdpedroechague.com.ar`) — catálogo, inscripciones, estados de socio. |
| **Identidad** | Website User con rol `Socio`, vinculado a un único `Socio`; sesión Frappe y protección CSRF estándar. |
| **Integración** | APIs `@frappe.whitelist()` autenticadas, CORS restringido y requests con credenciales desde el origen autorizado. |

La página legacy en Frappe (`/inscripcion-actividades`) es provisional y no define el contrato de seguridad productivo.

### Flujo

1. Un cobro confiable deja al socio en `Pendiente de Inscripción` y asegura que tenga un Website User vinculado.
2. El socio inicia sesión por email o DNI.
3. Vercel consulta el contexto y catálogo permitidos para el socio de la sesión.
4. El socio elige actividades según las reglas de negocio.
5. Vercel confirma `selecciones`; Frappe vuelve a resolver identidad, elegibilidad y catálogo.
6. Frappe crea las `Inscripcion Actividad` idempotentemente y activa al socio.

### Requisitos técnicos Vercel ↔ Frappe

- CORS acepta únicamente los orígenes configurados del sitio del club; nunca `*` junto con credenciales.
- Las mutaciones usan sesión autenticada, método POST y token CSRF de Frappe.
- Catálogo y confirmación fallan cerrados para Guest, usuarios sin rol `Socio` y usuarios sin vínculo único.
- La confirmación mantiene rate limit y no registra cookies, CSRF tokens ni datos personales en logs.
- `inscripcion_url` (portal) apunta al área autenticada del dominio Vercel y es configurable por ambiente.
- Los errores de autorización son genéricos y no revelan si existe otro socio o inscripción.

### URL del portal autenticado

La URL productiva **no lleva `pago_token`**. Precedencia:

1. `site_config.json` → `portal_socio_url`
2. `Club Settings.portal_socio_url`
3. Default `https://www.icdpedroechague.com.ar/socios/actividades`

Si el valor es solo el origen (`https://www.icdpedroechague.com.ar`), se concatena `/socios/actividades`. Cualquier query `token` / `pago_token` se descarta.

El builder legacy `build_inscripcion_actividades_url(pago_token)` queda para QA (`/inscripcion-actividades?token=`). El stub de pago puede devolver ambas: `inscripcion_url` (legacy) y `portal_url` (sesión).

### Scenario: URL de portal no incluye token

Given `Club Settings.portal_socio_url` o `site_config.portal_socio_url` configurado
When el backend arma la URL del portal
Then el resultado es el área `/socios/actividades`
And no contiene `token` ni `pago_token`.

### Scenario: site_config tiene prioridad sobre Club Settings

Given `site_config.portal_socio_url = http://localhost:3000/socios/actividades`
And Club Settings apunta a producción
When se resuelve la URL
Then se usa el valor de `site_config`.

### Scenario: CORS nunca es wildcard

Given `allow_cors` en site_config
When se calculan los orígenes permitidos del portal
Then `*` no forma parte de la lista
And el origen derivado de `portal_socio_url` sí está incluido.

### Scenario: bootstrap de sesión entrega CSRF

Given el socio completó el login nativo de Frappe y obtuvo una cookie `sid`
When el BFF consulta por GET el bootstrap autenticado del portal
Then recibe un token CSRF no vacío para las mutaciones posteriores
And el endpoint vuelve a validar rol `Socio` y vínculo único de la sesión
And Guest no puede obtener un token.

---

## Reglas de negocio — qué elige el socio

No hay cascada única «actividad → tira → equipo» para todo. Depende del **tipo de actividad**:

| Tipo | Ejemplos | Portal (socio) | Secretaría (Desk) |
|------|----------|----------------|-------------------|
| **Plana** | Zumba, Ritmos Latinos | Solo **actividad** | — |
| **Deporte** | Basquet, Fútbol, Voley | Solo **actividad** | Asigna **grupo/tira** y **equipo** al validar el alta |
| **Variante de grupo** | Funcional 1 clase/semana, Gimnasia 2 clases, escuelita no competitiva | **Actividad + grupo** (el grupo es el plan/arancel) | No asigna tira/equipo deportivo |

**El socio nunca elige tira deportiva ni categoría U11/U13 en el portal.** Eso lo carga Secretaría cuando valida el alta del deportista.

### Metadata requerida

Campo en **`Actividad`** (Select): `tipo_inscripcion_portal`

| Valor | Comportamiento portal |
|-------|------------------------|
| `plana` | Default si `usa_grupos = 0`. Solo nombre de actividad. |
| `deporte` | Solo actividad. Inscripción sin `grupo_actividad` / `equipo_actividad` → pendiente de asignación Desk. |
| `variante_grupo` | Actividad + selector de **Grupo Actividad** cuyos grupos tengan `portal_socio_elige = 1`. |

Campo en **`Grupo Actividad`** (Check): `portal_socio_elige` — solo grupos marcados aparecen en el selector del portal (ej. «1 clase por semana», escuelita recreativa).

---

## Scenario: deporte — socio elige solo Basquet

Given un socio autenticado y elegible
And `Actividad` «Basquet» con `tipo_inscripcion_portal = deporte`
When confirma `selecciones = [{ "actividad": "Basquet" }]`
Then se crea `Inscripcion Actividad` sin `grupo_actividad` ni `equipo_actividad`
And la inscripción queda pendiente de asignación deportiva
And `Socio.estado` pasa a `Activo`
And Secretaría completa tira y equipo desde Desk al validar el alta.

---

## Scenario: variante — Funcional 1 clase por semana

Given un socio autenticado y elegible
And `Actividad` «Funcional» con `tipo_inscripcion_portal = variante_grupo`
And `Grupo Actividad` «1 clase por semana» con `portal_socio_elige = 1`
When confirma actividad y grupo desde el portal
Then la inscripción queda con actividad + grupo y arancel del ítem del grupo
And no se exige equipo.

---

## Scenario: actividad plana — Zumba

Given un socio autenticado y elegible
And `Actividad` «Zumba» con `tipo_inscripcion_portal = plana`
And `usa_grupos = 0`
When el socio elige solo «Zumba»
Then inscripción con arancel de `Actividad.item`.

---

## Scenario: API catálogo para Vercel

Given un socio autenticado
When Vercel llama al catálogo de inscripción
Then recibe actividades habilitadas con `tipo_inscripcion_portal`
And para `variante_grupo` incluye lista de grupos con `portal_socio_elige = 1`
And **no** expone equipos deportivos al socio (endpoint equipos solo Desk / futuro admin).

---

## Scenario: Guest no puede consultar ni confirmar

Given una petición sin sesión autenticada
When consulta el contexto o confirma actividades
Then recibe error de autenticación
And no se consulta ni modifica ningún `Socio`.

---

## Scenario: aislamiento entre dos socios

Given los usuarios autenticados A y B vinculados a socios distintos
And ambos tienen inscripciones
When A lista, abre o confirma sus inscripciones
Then solo puede leer y modificar registros cuyo `socio` sea el vinculado a A
And conocer el nombre de una inscripción de B no permite abrirla
And filtros, parámetros o payloads manipulados no permiten seleccionar a B.

---

## Scenario: usuario Socio sin vínculo único

Given un usuario autenticado con rol `Socio`
And no existe exactamente un `Socio` habilitado vinculado a ese usuario
When consulta el contexto o confirma actividades
Then el sistema falla cerrado con un error genérico
And no intenta inferir identidad por parámetros del cliente.

---

## Scenario: confirmación requiere elegibilidad y selecciones

Given un socio autenticado cuyo estado no es `Pendiente de Inscripción`
When intenta confirmar actividades
Then no se crean inscripciones y no cambia su estado.

Given un socio autenticado en `Pendiente de Inscripción`
When confirma una lista vacía, inválida o sin actividades permitidas
Then no se crean inscripciones
And el socio permanece `Pendiente de Inscripción`.

---

## Scenario: replay idempotente

Given un socio autenticado confirmó una actividad
When repite la misma confirmación
Then recibe el mismo resultado funcional
And no se duplica una inscripción activa
And no se duplican suscripciones ni cargos.

---

## Scenario: grupo y equipo manipulados

Given una actividad plana o deportiva
When el socio envía `grupo_actividad` o `equipo_actividad`
Then la confirmación se rechaza sin efectos.

Given una actividad `variante_grupo`
When el socio envía un grupo no marcado `portal_socio_elige`, deshabilitado o perteneciente a otra actividad
Then la confirmación se rechaza sin efectos.

---

## Contrato API objetivo

| Operación | Autorización | Resultado |
|-----------|-------------|-----------|
| Contexto del socio actual | Sesión + rol `Socio` + vínculo único | Estado y elegibilidad, sin exponer identificadores ajenos. |
| Catálogo de inscripción | Sesión + rol `Socio` | Actividades habilitadas y únicamente grupos seleccionables. |
| Inscripciones propias | Sesión + rol `Socio` | Solo filas del socio actual. |
| Confirmar selecciones | Sesión + rol `Socio` + elegibilidad + CSRF | Resultado idempotente de las inscripciones propias. |

Los métodos actuales de `activities/api/inscripcion_publica.py` son una base legacy. Antes del cutover:

- Se crean endpoints autenticados para BL-6 o se elimina `allow_guest=True` de los que pasen a ser productivos.
- `get_equipos_grupo` deja de ser público.
- `get_grupos_actividad` no publica tiras deportivas ni grupos sin `portal_socio_elige`.
- Las respuestas no incluyen el `name` interno del `Socio` salvo necesidad documentada.

---

## Permisos y aislamiento de datos

- `Inscripcion Actividad` implementa `permission_query_conditions` y `has_permission` para el rol `Socio`.
- La condición SQL (PostgreSQL, identificadores entre comillas dobles) resuelve el socio desde `frappe.session.user` y aplica el mismo alcance a listas, reportes y lectura directa. No lee `socio` ni `user` del body.
- `validate` del DocType vuelve a atar `Inscripcion Actividad.socio` al vínculo de la sesión. Un `insert` con otro socio en el payload falla cerrado, aunque el caller use `ignore_permissions`.
- El rol `Socio` no tiene `create`/`write` en DocPerm: la mutación productiva pasa por `confirmar_inscripcion_actividades`, que no acepta identidad del cliente.
- Las consultas usan APIs compatibles con PostgreSQL 14; no usan backticks ni SQL de MariaDB.
- Las pruebas crean dos usuarios y dos socios y cubren lista, lectura directa, insert cruzado, confirmación y replay.
- Secretaría y System Manager mantienen sus permisos Desk explícitos sin heredar el alcance del portal.

---

## Transición desde cobranza

- BL-6 consume una señal interna de elegibilidad; no confía en estados enviados desde Vercel.
- Cobro manual y Supervielle podrán converger en el mismo servicio de backend que:
  1. valida que el pago corresponda al socio;
  2. cambia el estado a `Pendiente de Inscripción`;
  3. asegura el Website User vinculado;
  4. devuelve o notifica la URL del portal autenticado.
- Hasta integrar Supervielle de extremo a extremo, el cobro manual de Secretaría es el disparador aceptado para desarrollo y QA.
- El `pago_token` no concede acceso a inscripciones ni permite cambiar el socio de sesión.

---

## Fuera de alcance BL-6

- Carnet, historial de pagos y autogestión de datos personales.
- Cambio de inscripciones post-alta desde el sitio del club.
- Checkout y pago online en Vercel; la conciliación Supervielle pertenece a su épica.
- Implementación del frontend Vercel (repo aparte); este spec define contrato API y reglas Frappe.
- Asignación de tira/equipo deportivo por el socio.
- Baja o transferencia de una inscripción existente.

---

## Artefactos previstos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/portal_socio_inscripcion.md` (este archivo) |
| API autenticada | `activities/api/portal_socio.py` |
| URL portal / CORS | `activities/services/portal_urls.py`, `Club Settings.portal_socio_url` |
| Servicios | `activities/services/actividades_catalog.py`, `grupos_portal.py`, `inscripcion_socio.py` |
| Permisos | `activities/permissions.py` y hooks correspondientes |
| Desk | Completar tira/equipo en `inscripcion_gestion_desk.md` |
| Tests | `activities/tests/test_portal_socio_inscripcion.py` y regresión de `test_inscripcion_post_pago.py` |
| Legacy UI | `www/inscripcion-actividades.html` — QA, sin considerarlo superficie productiva BL-6 |

---

## Gate de aceptación

1. Specs y tests cubren plana, deporte y variante de grupo.
2. Tests con dos socios demuestran aislamiento de lista, lectura directa y mutación.
3. Guest, rol incorrecto y vínculo ambiguo fallan cerrados.
4. Replay no duplica inscripción, suscripción ni cargo.
5. Migración agrega metadata y permisos sin modificar datos históricos de forma implícita.
6. Suite dirigida de portal y permisos verde.
7. Suite completa de la app verde antes de promover al MVP.
8. UAT verifica sesión, CORS, CSRF y flujo cobro manual → portal en el ambiente local/sandbox.

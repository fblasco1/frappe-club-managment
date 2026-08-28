# Backlog de implementación — Gestión de Socios y Actividades



Índice de specs para implementar en chats separados (orden **SDD → test fallando → código**).



**Ruta:** `club_management/specs/`  

**Estado:** `[ ]` pendiente · `[~]` parcial (ver spec «ya implementado») · `[x]` hecho



**Última revisión MVP producción:** 2026-08-19 — commit en Hetzner: **`43b226f`** (validación Adherente/Jubilado en alta pública).  
**Última actualización backlog:** 2026-08-27 (módulo Spaces — resumen + pendientes FMV/Excel).  

**Destino producción:** Hetzner Cloud **CX23** — https://gestion.icdpedroechague.com.ar  
**Landing (wizard):** https://www.icdpedroechague.com.ar/asociate/inscripcion  

**Gap local → prod:** el go-live de agosto está desplegado. Queda WIP local en `stash@{0}` (`wip leftover KPIs/post-baja`) — **no** incluye post-baja (eso ya está en prod). Ver «Pendiente post go-live 2026-08-19».



---



## Producción — Hetzner CX23



| Recurso | Valor ([Cost-Optimized CX23](https://www.hetzner.com/cloud/cost-optimized)) |

|---------|-------------------------------------------------------------------------------|

| vCPU | 2 (Intel®/AMD) |

| RAM | **4 GB** |

| Disco local | **40 GB** SSD |

| Uso previsto | 1 sitio Frappe + ERPNext + `club_management`, Secretaría interna ICDPE |



**Adecuado para MVP** con decenas/cientos de socios si se configura bien. **No** es margen holgado: monitorear RAM y disco desde el día 1.



### Recomendaciones antes de crear la VM



- **SO:** Ubuntu 24.04 LTS.

- **Región:** `eu-central` (Nuremberg / Falkenstein) u otra EU; DNS del dominio → IP pública.

- **Swap 2 GB** en el host (4 GB RAM es justo con Postgres + Redis + workers + scheduler).

- **Firewall Hetzner:** entrante `22` (SSH restringido), `80`, `443`.

- **Backups:** Backups de Hetzner en la VM + cron `bench backup --with-files`; Volume extra si crecen adjuntos.

- **Imagen:** build **custom** con `club_management` (ver `docs/02-setup/02-build-setup.md` en club-manager-infra).



### Stack Compose sugerido (un solo bench)



```bash

cd ~/club_manager_infra

docker compose \

  -f compose.yaml \

  -f overrides/compose.postgres.yaml \

  -f overrides/compose.redis.yaml \

  -f overrides/compose.https.yaml \

  up -d

```



Variables mínimas en `.env` (desde `example.env`): `ERPNEXT_VERSION`, `DB_PASSWORD`, `LETSENCRYPT_EMAIL`, `SITES_RULE`, `FRAPPE_SITE_NAME_HEADER`.



Servicios críticos cobranza: **scheduler**, **queue-long**, **queue-short**, **backend**, **db**.



### Orden primer arranque en CX23



1. Crear CX23, SSH, Docker + Compose v2, swap.

2. Clonar club-manager-infra + imagen con `club_management`.

3. `.env` producción (nunca en git).

4. `docker compose … up -d` (esperar DB healthy).

5. `bench new-site --db-type postgres … <sitio-prod>`

6. `install-app erpnext club_management` + `migrate` + `build`

7. Club Settings, Secretaría, ciclo cobranza (runbook bloque C).



**Dev local** = ensayo (bloque A). **Prod** = SSH al CX23 (bloques B–D).



---



## Leyenda de dependencias



| Símbolo | Significa |

|---------|-----------|

| → | Implementar después de |

| ‖ | Puede ir en paralelo |



---



## Alcance MVP producción (Secretaría interna ICDPE)



**Incluye (listo para operar en Desk):**



| Área | Specs / notas |

|------|----------------|

| Socios | Alta guiada, edición, estados, tutor menor, cobranza manual puntual |

| Inscripciones | Diálogo en Socio (Link cascada), form `Inscripcion Actividad`, baja/listado |

| Actividades | Jerarquía Actividad → Grupo → Equipo, panel gestión, aranceles inline |

| Equipo Actividad | Layout grupo+título en fila, roster de socios inscriptos (`equipo_actividad_form_roster.md`) |

| Cobranza | Club Settings, facturación día 1, recargo 2.º vencimiento, moroso automático, cargos extra |

| Informes | Deuda por equipo, pagos por equipo, liquidación manual en rango |

| Workspace Secretaría | Panel KPI (socios, recaudación, morosos), sidebar, navegación Desk acotada |



**Fuera de alcance todavía (no desplegado):**



| Tema | Spec | Motivo |

|------|------|--------|

| Inscripción a actividades desde el portal (socio logueado) | `portal_socio_inscripcion.md` | BL-6: el wizard de **alta** ya está en prod; falta el portal post-pago |

| Pagos online Supervielle / Cobrand | `supervielle_cobros_plus_*.md` | Alta pública es sin cobro online (`alta_sin_pago_online.md`) |

| Job categoría Vitalicio | `socios_categoria_validacion.md` | Futuro |

| Filtro tendencia KPI + informe pagos del día (WIP stash) | `secretaria_workspace_panel_kpis.md`, `informe_pagos_del_dia.md` | Extraído del stash 2026-08-19; no bloquea operación |



---



## Fase 0 — Ya implementado (referencia)



| Spec | Estado | Notas |

|------|--------|-------|

| `socio_minimo.md` | [~] | DocType Socio; falta job Vitalicio |

| `solicitud_asociacion_publica.md` | [x] | Código listo; **no** se expone en MVP interno |

| `mvp_operacion_secretaria_sin_pagos.md` | [x] | Estados, inscripción Desk, cobranza manual puntual |

| `secretaria_operacion_interna_mvp.md` | [x] | Desk sin solicitudes/grupo familiar; tutor menor obligatorio |

| `secretaria_workspace_listas.md` | [x] | Panel listas + cuotas inline (montos) |

| `secretaria_workspace_panel_kpis.md` | [x] | Cards KPI Secretaría (socios, recaudación mes, morosos + deuda) |

| `gestion_actividades_panel.md` | [x] | Catálogo, alta, aranceles inline |

| `gestion_actividades_edicion_panel.md` | [x] | Editar / deshabilitar nodos en panel actividades |

| `socio_alta_edicion_secretaria.md` | [x] | Alta manual + edición Desk; **número de socio opcional** en alta guiada (2026-07-10, `b53ed5b`) |

| `inscripcion_gestion_desk.md` | [x] | Baja/listado inscripciones; cascada actividad→grupo→equipo en diálogos |

| `equipo_actividad_form_roster.md` | [x] | Roster socios en formulario Equipo Actividad |

| `cuotas_sync_erpnext.md` | [x] | Guardar cuotas → Item Price + Subscription Plan |

| `activities_jerarquia.md` | [x] | DocTypes Actividad / Grupo / Equipo / Inscripción |
| `basquet_estructura_unificada.md` | [x] | Actividad única **Basquet** + 6 grupos; migración inscripciones prod (2026-07-05, `1aedd3a`) |
| `basquet_cost_center_consolidado.md` | [x] | CC único **Deportes - Basquet - ICDPE** (BL-4, 2026-07-06) |

| `cuotas_sociales_suscripcion.md` | [x] | Suscripción ERPNext solo cuota social |

| `cobranza_config_club_settings.md` | [x] | Calendario de deuda y recargo en Club Settings |

| `cobranza_periodica_mensual.md` | [x] | Job día 1: facturar cuota + aranceles activos |

| `cargo_extra_socio.md` | [x] | DocType Cargo Socio + UI Secretaría |

| `cobranza_recargo_segundo_vencimiento.md` | [x] | Recargo fin de mes + segunda exigibilidad |

| `moroso_automatico.md` | [x] | Job moroso post-2.º vencimiento |

| `recibo_pago_escpos.md` | [x] | Recibo térmico ESC/POS tras registrar cobro Desk (2026-07-08, `e58bfbc`) |

| `registrar_cobro_fecha.md` | [x] | Fecha de cobro en diálogo Secretaría + validación (2026-07-08 `8aed9ef`, tests `b53ed5b`) |

| `portal_alta_grupo_familiar.md` | [x] | **Prod 2026-08-19** — wizard Vercel + API Guest; Adherente/Jubilado server-side (`43b226f`) |
| `alta_sin_pago_online.md` | [x] | Tras validar, Secretaría cierra con Activar / Omitir pago (sin gateway) |
| `almacenamiento_documentacion_socios.md` | [x] | Docs vigentes: un File privado por campo; pisa al renovar; clona al Socio (`e94ea02`) |
| `informes_tesoreria_pnl_cashflow.md` | [x] | P&L + Flujo de efectivo desde panel Tesorería (`b4ed98b`) |
| `socio_alta_post_baja.md` | [x] | Alta post-baja + cascada de inscripciones (`4dfe560`) |
| `portal_socio_inscripcion.md` | [ ] | BL-6 — inscripción **post-pago** (socio logueado); distinto del wizard de alta |

| `liquidacion_equipo_deuda_rango.md` | [x] | Reporte deuda por equipo + liquidación manual en rango |

| `socios_categoria_validacion.md` | [ ] | Validación categoría, job Vitalicio — futuro |



---



## Fase 1 — Completar operación Desk (bajo riesgo)



| # | Spec | Depende de | Entregable principal |

|---|------|------------|----------------------|

| 1.1 | `socio_alta_edicion_secretaria.md` | socio_minimo | Alta manual + edición guiada desde Desk — **hecho** |

| 1.2 | `inscripcion_gestion_desk.md` | mvp_operacion | Baja/listado inscripciones desde formulario Socio — **hecho** |

| 1.3 | `cuotas_sync_erpnext.md` | cuotas_sociales_suscripcion | Guardar cuotas → Item Price + Subscription Plan — **hecho** |

| 1.4 | `gestion_actividades_edicion_panel.md` | gestion_actividades_panel | Editar / deshabilitar nodos en panel actividades — **hecho** |

| 1.5 | `equipo_actividad_form_roster.md` | activities_jerarquia, inscripcion_gestion_desk | Roster socios en Equipo Actividad — **hecho** |

| 1.7 | `cargo_extra_conceptos_y_facturacion.md` | cargo_extra_socio | Conceptos por actividad + auto-factura único — **hecho** (2026-07-05) |

| 1.8 | `deuda_socio_desk.md` | mvp_operacion, cargo_extra_socio | Panel deuda en formulario Socio — **hecho** (2026-07-05) |

| 1.9 | `valores_cuota_social_page.md` | secretaria_workspace_listas | Página Desk cuotas + sidebar — **hecho** (2026-07-05) |

| 1.10 | `gestion_socios_dashboard.md` | secretaria_workspace_panel_kpis | Dashboard socios, tendencia recaudación, medios pago — **hecho** (2026-07-05) |



**Paralelo posible:** 1.1 ‖ 1.2 ‖ 1.3 ‖ 1.4 ‖ 1.5



---



## Fase 1b — Liquidación por equipo (operación interna)



| # | Spec | Depende de | Entregable principal |

|---|------|------------|----------------------|

| 1.6 | `liquidacion_equipo_deuda_rango.md` | mvp_operacion, activities_jerarquia, cobranza_periodica | Script Report + API liquidación manual en rango — **hecho** |



---



## Fase 2 — Cobranza periódica (crítico para operación mensual)



| # | Spec | Depende de | Entregable principal |

|---|------|------------|----------------------|

| 2.1 | `cobranza_config_club_settings.md` | — | Campos calendario y recargo en Club Settings — **hecho** |

| 2.2 | `cobranza_periodica_mensual.md` | 2.1, cuotas_sync | Job día 1: facturar cuota + aranceles activos — **hecho** |

| 2.3 | `cargo_extra_socio.md` | 2.1 | DocType Cargo Socio + UI Secretaría — **hecho** |

| 2.4 | `cobranza_periodica_mensual.md` (ext.) | 2.3 | Incluir cargos extra en facturación mensual — **hecho** |

| 2.5 | `cobranza_recargo_segundo_vencimiento.md` | 2.2 | Recargo fin de mes + segunda exigibilidad — **hecho** |

| 2.6 | `moroso_automatico.md` | 2.5 | Job moroso post-2.º vencimiento — **hecho** |



**Orden estricto:** 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 — **completo**



---



## Fase 3 — Integración pagos y portal (posterior al go-live)



| Spec | Notas |

|------|-------|

| `supervielle_cobros_plus_webhook.md` | Ya existe; alinear con cobranza periódica |

| `supervielle_cobros_plus_api.md` | Botón pago real |

| `activities_modulo.md` | Portal socio inscripciones autenticado |

| `login_dual.md` | Acceso portal + Desk |

| `grupo_familiar_minimo.md` | Alta familiar pública **hecha** (`portal_alta_grupo_familiar.md`); quedan reglas Desk (hermanos, cotitularidad avanzada) |

| BL-6 `portal_socio_inscripcion.md` | Inscripción a actividades **después** de ser socio |



---



## Mapa requisito de negocio → spec



| Requisito Secretaría | Spec |

|----------------------|------|

| CREAR / EDITAR socio | `socio_alta_edicion_secretaria.md` |

| Actualizar pago manual | `mvp_operacion_secretaria_sin_pagos.md` |

| Inscribir a actividades | `mvp_operacion_secretaria_sin_pagos.md` + `inscripcion_gestion_desk.md` |

| Ver socios de un equipo / tira | `equipo_actividad_form_roster.md` |

| Cargos extra (federativa, multa, viaje…) | `cargo_extra_socio.md` |

| Actualizar CUOTA SOCIAL y ARANCEL | `secretaria_workspace_listas.md` + `cuotas_sync_erpnext.md` + `gestion_actividades_edicion_panel.md` |

| Panel KPI Secretaría | `secretaria_workspace_panel_kpis.md` |

| Deuda día 1, vence 10, recargo fin mes | `cobranza_config_club_settings.md` + `cobranza_periodica_mensual.md` + `cobranza_recargo_segundo_vencimiento.md` |

| Moroso automático | `moroso_automatico.md` |

| CREAR / EDITAR actividad, subgrupo, equipo | `gestion_actividades_panel.md` + `gestion_actividades_edicion_panel.md` |

| Liquidación / deuda por equipo y rango de fechas | `liquidacion_equipo_deuda_rango.md` |



---



## Checklist salida a producción (antes del cutover)

**Sesión 2026-06-16 (sin CX23 aún):** ver estado al pie de cada ítem.



### Código y calidad



- [~] Tag o commit acordado en **frappe-club-management** (app) y **club-manager-infra** (compose/imagen).  
  **Hoy:** `infra` `92322f8` (main, ahead 1, muchos cambios sin commit). App `b435147` (`develop`, **gran volumen sin commit**). **Pendiente:** commit + tag `mvp-secretaria-2026-06-16` antes del deploy.

- [~] Tests verdes en contenedor dev.  
  **Hoy:** suite completa 342 tests → **1 fail + 5 errors** (flujo solicitud pública / ICDPE catalog; fuera del MVP interno).  
  **Módulos MVP críticos (71 tests): OK** — inscripción Desk, cobranza manual/periódica, moroso, KPI panel, equipo roster, alta Secretaría, liquidación, operaciones Secretaría.

```bash
docker compose -p devcontainer-example -f .devcontainer/docker-compose.yml up -d
docker exec devcontainer-example-frappe-1 bash -c 'cd /workspace/development/frappe-bench && \
  bench --site dev.localhost run-tests --app club_management --skip-before-tests'
```

- [x] `bench build --app club_management` en dev (**2026-06-16**, OK).

- [x] Revisión checklist **security-auditor** (MVP Desk) — ver informe abajo.

- [~] `.env` producción desde plantilla; **no** commitear credenciales.  
  **Hoy:** plantilla `docs/club/example.prod.env`; `.env` en `.gitignore`.



### Informe seguridad MVP Desk (2026-06-16)

| Área | Estado |
|------|--------|
| Whitelist Desk (`socio_operaciones_desk`, `cobranza_desk`, `liquidacion_equipo_desk`, `equipo_actividad_desk`, `secretaria_workspace`) | OK — `ensure_secretaria_operacion_access()` o rol + `has_permission` en Club Settings |
| Aislamiento socio | OK en tests `test_socio_isolation`; APIs Desk restringidas a Secretaría |
| Guest (`solicitud_publica`, inscripción pública) | Fuera de go-live MVP; tokens/spec existentes |
| SIRO / Supervielle | No en uso prod MVP |
| XSS panels Desk | Datos de usuario con `frappe.utils.escape_html` en tablas dinámicas |

**Recomendación pre-go-live:** no exponer rutas públicas de solicitud en DNS prod hasta Fase 3.



### Club Settings dev (replicar en prod)

| Campo | Valor dev |
|-------|-----------|
| `dia_generacion_deuda` | 1 |
| `dia_primer_vencimiento` | 10 |
| `dia_segundo_vencimiento` | Último día del mes |
| `recargo_segundo_vencimiento_pct` | 10 |
| `incluir_aranceles_en_deuda_mensual` | sí |
| `incluir_cargos_extra_en_deuda_mensual` | sí |
| `cuotas_categoria` | 6 filas |
| `company` | verificar en Desk antes del cutover |



### Infraestructura (bloqueado hasta CX23)



- [ ] VM **Hetzner CX23** (Ubuntu 24.04, swap 2 GB, firewall 22/80/443).

- [ ] DNS dominio prod → IP pública CX23.

- [ ] Imagen Docker Frappe v16 + ERPNext + `club_management` (custom).

- [ ] PostgreSQL en compose (`overrides/compose.postgres.yaml`).

- [ ] TLS Let's Encrypt (`compose.https.yaml`).

- [ ] Servicios **scheduler** y colas en compose (cobranza + moroso).

- [ ] Backup Hetzner y/o cron `bench backup --with-files`.

- [ ] `bench --site <sitio-prod> migrate` en ventana de mantenimiento.

- [ ] `bench --site <sitio-prod> clear-cache` tras migrate/build.



### Datos maestros (post-migrate)



- [ ] **Club Settings:** empresa ICDPE, días generación deuda / 1.er y 2.º vencimiento, recargo, cuotas por categoría.

- [x] Verificar patches de seed: actividades ICDPE, estructura básquet unificada, workspaces Secretaría / Gestión Actividades. **2026-07-05:** patch `migrate_basquet_estructura_unificada` en prod — 185 inscripciones activas bajo `Basquet`, legacy deshabilitadas.

- [ ] Ítems y aranceles revisados con contabilidad (ver `docs/docs/Accounting - ICDPE - Revision Contable.md`).

- [ ] Usuarios **Secretaria** creados (sin compartir contraseña por chat; usar correo institucional).

- [ ] Rol **Socio** sin permisos de escritura indebidos en Desk.



### Smoke test en producción (Secretaría)



- [ ] Login → workspace **Secretaría** → panel KPI carga y «Ver más» abre listas filtradas.

- [ ] Alta guiada de socio menor con tutor.

- [ ] Inscribir en actividades (diálogo Socio) con grupo/tira y equipo.

- [ ] Abrir **Equipo Actividad** → roster de socios visible.

- [ ] Registrar cobro manual sobre factura pendiente.

- [ ] Informes **Deuda por equipo** y **Pagos por equipo** con filtros.

- [ ] (Opcional staging) Simular `generar_deuda_mensual` en un socio de prueba antes del día 1 real.



### Rollback



- [ ] Backup completo (`bench --site all backup --with-files`) **inmediatamente antes** del migrate en prod.

- [ ] Procedimiento documentado: restaurar backup + imagen anterior si falla smoke test.



---



## Pasos para mañana (2026-06-16) — runbook acordado

**Sesión conjunta:** despliegue MVP + **primer ciclo de cobranza** (generación de deuda junio + carga de pagos manual en Desk).

Participantes: equipo técnico + al menos una persona de Secretaría para probar cobro real.

**Entorno:** dev local (ensayo) → **prod en Hetzner CX23** (SSH). Ajustar `<sitio-prod>` y dominio real.

---

### ⚠ Calendario automático vs. mañana (día 16)

El job diario `run_generar_deuda_si_corresponde` **solo factura** cuando **hoy == `dia_generacion_deuda`** en Club Settings (default **día 1**).

| Situación | Qué pasa el 16/06 |
|-----------|-------------------|
| `dia_generacion_deuda = 1` (default) | El scheduler **no** genera facturas solo por ser día 16. |
| Queremos facturar junio mañana | **Opción A (recomendada go-live):** ejecución **manual** tras el deploy (comandos abajo). |
| | **Opción B:** poner `dia_generacion_deuda = 16` solo para el primer mes; el scheduler dispara a la madrugada; **volver a 1** antes de julio. |

Para el **primer mes en producción**, usar **Opción A** da control total (revisar facturas antes de avisar a socios).

**Pagos:** no hay gateway online en MVP. Secretaría registra cobros con **Registrar cobro** en el formulario Socio (`cobranza_desk.registrar_cobro` → `Payment Entry`).

---

### Bloque A — Mañana temprano (dev / ensayo, sin prod)

1. Congelar versión (SHA o tag `mvp-secretaria-2026-06-16`).
2. Tests finales:

```bash
docker compose exec backend bash -c 'cd /workspace/development/frappe-bench && \
  bench --site dev.localhost run-tests --app club_management --skip-before-tests'
```

3. **Ensayo cobranza en dev** (2 socios activos con cuota e inscripción):

```bash
docker compose exec backend bash -c 'cd /workspace/development/frappe-bench && bench --site dev.localhost console'
```

```python
from club_management.members.services.cobranza_periodica import (
    generar_deuda_mensual_socio,
    generar_deuda_mensual_socios,
)
from frappe.utils import today

# Un socio piloto
generar_deuda_mensual_socio("SOC-XXXX-XXXX", reference_date=today())

# O lote completo elegible
generar_deuda_mensual_socios(reference_date=today())
```

4. En Desk (dev): abrir ese Socio → **Registrar cobro** → elegir factura pendiente → confirmar.
5. Verificar: `Payment Entry` submitted, `Socio.saldo_deuda` baja, panel KPI recaudación del mes refleja el cobro.
6. Anotar valores de **Club Settings** a replicar en prod.

---

### Bloque B — Mediodía (despliegue en Hetzner CX23)

7. SSH al CX23; verificar `docker compose ps` (todos healthy).
8. Backup prod (obligatorio):

```bash
cd ~/club_manager_infra   # o ruta del clone en el servidor
docker compose exec backend bench --site <sitio-prod> backup --with-files
```

9. Actualizar imagen / `git pull` en el servidor + `bench --site <sitio-prod> migrate`
10. `docker compose exec backend bench build --app club_management`
11. `docker compose exec backend bench --site <sitio-prod> clear-cache`
12. `docker compose restart backend queue-short queue-long scheduler`

---

### Bloque C — Tarde (config + primer ciclo cobranza real)

11. **Club Settings (prod):** Company ICDPE, cuotas por categoría, `dia_generacion_deuda` (dejar **1** si usamos manual mañana), `dia_primer_vencimiento` (ej. 10), `dia_segundo_vencimiento`, recargo %.
12. Usuarios Secretaría creados y login probado.
13. Smoke Desk: KPI, alta, inscripción, roster equipo (sin facturar aún).

#### C.1 Generación de deuda junio (manual controlado)

14. Confirmar socios **Activo** / **Moroso** elegibles y que tengan (o auto-crean) **Customer**.
15. Ejecutar en prod (ventana acordada con Secretaría):

```bash
ssh root@<ip-cx23>
cd ~/club_manager_infra
docker compose exec backend bash -c 'cd /home/frappe/frappe-bench && bench --site <sitio-prod> console'
```

```python
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socios
from frappe.utils import today

result = generar_deuda_mensual_socios(reference_date=today())
print(result)  # facturas_creadas, errores, invoice_names
```

16. Revisar muestra de **Sales Invoice** (cuota + aranceles + cargos extra si aplican), `due_date`, período `06/2026`.
17. Si hay errores en `result["detalle_errores"]` → Error Log / corregir antes de seguir.

#### C.2 Carga de pagos (Secretaría)

18. Por cada cobro recibido en efectivo/transferencia (piloto: 2–3 socios):
    - Formulario **Socio** → botón **Registrar cobro** (grupo Cobranza manual).
    - Elegir factura del período → confirmar.
19. Verificar `Payment Entry`, saldo deuda del socio, estado **Moroso → Activo** si correspondía.
20. Panel KPI: card recaudación mes y morosos coherentes.

#### C.3 Scheduler a futuro

21. Confirmar servicio **scheduler** activo (jobs `daily`: deuda, recargo 2.º vencimiento, moroso).
22. A partir de **julio**, con `dia_generacion_deuda = 1`, el día 1/07 el job corre solo (no hace falta consola).

---

### Bloque D — Cierre del día

23. Go/no-go documentado (versión, hora, facturas emitidas, cobros piloto OK).
24. Capacitación Secretaría (30 min): generación ya hecha + cómo registrar cobros el resto del mes.
25. Pendientes → issues; nuevas features → Fase 3 del backlog.

---

### Checklist rápido cobranza mañana

- [ ] Ensayo dev: 1 factura + 1 cobro manual OK
- [ ] Backup prod antes de migrate
- [ ] Migrate + build + restart scheduler
- [ ] Club Settings prod verificado
- [ ] `generar_deuda_mensual_socios` ejecutado (manual) — revisar resumen
- [ ] Al menos 2 cobros registrados en Desk por Secretaría
- [ ] KPI / saldo deuda / informes de equipo coherentes
- [ ] Equipo informado: próximo ciclo automático día 1 del mes siguiente

---



## Convenciones para cada chat de implementación



1. Leer la spec indicada y `AGENTS.md` / reglas SDD+TDD.

2. Escribir o ajustar test **antes** del código de producción.

3. `bench migrate` si hay cambios JSON de DocType.

4. No modificar `apps/frappe` ni `apps/erpnext`.

5. PostgreSQL v14 si hay SQL crudo.



---



## Pendientes menores post-MVP (no bloquean go-live)



| Tema | Prioridad | Notas |

|------|-----------|-------|

| Roster en **Grupo Actividad** (solo grupo, sin equipo) | Baja | Hoy está en Equipo Actividad; grupo se ve al abrir equipos o vía informes |

| Job categoría **Vitalicio** automático | Media | `socios_categoria_validacion.md` |

| Labels Select diálogo inscripción (título vs name interno) | Baja | UX |

| Tests E2E supervisados flujo completo Secretaría | Media | Skill `qa-solicitud-supervisada` adaptable |



---



## Backlog — sesión 2026-07-05



| # | Tema | Prioridad | Spec (a crear) | Notas |

|---|------|-----------|----------------|-------|

| BL-1 | **Beca al socio** | Media | `beca_socio.md` | **Hecho 2026-07-05** — DocType `Beca Socio`, integración en `build_invoice_items_for_socio`. |

| BL-2 | **Login — estética SICLUB** | Media | `login_siclub_branding.md` | **Hecho 2026-07-05** — `siclub_login.css` + `web_include_css` en hooks. |

| BL-3 | **Básquet — actividad única** | Media | `basquet_estructura_unificada.md` | **Hecho 2026-07-05** — seed unificado (6 grupos), migración 185 inscripciones activas en prod, roster/padrón actualizados, commit `1aedd3a`. Legacy Masculino/Femenino/Escuelita deshabilitadas. |

| BL-4 | **CC ERPNext básquet** | Baja | `basquet_cost_center_consolidado.md` | **Hecho 2026-07-06** — CC único `Deportes - Basquet - ICDPE`, patch `consolidate_basquet_cost_centers`, script `verify_and_purge_basquet_legacy`; purga prod: 3 actividades, 18 grupos, 44 equipos, 3 CC (`f436d2c`). |

| BL-5 | **Specs legacy básquet** | Baja | `activities_jerarquia.md`, `basquet_aranceles_icdpe.md`, `vinculacion_basquet_roster.md`, `import_socios_actividades_padron.md` | **Hecho 2026-07-06** — escenarios alineados a actividad única **Basquet**. |

| BL-7 | **Recibo térmico en cobro Desk** | Alta | `recibo_pago_escpos.md` | **Hecho 2026-07-08** — fix import `build_recibo_pago` en `cobranza_desk.registrar_cobro` (`e58bfbc`); 8 tests `test_recibo_pago` OK; probado UI Socio 11479. |

| BL-8 | **Fecha de cobro manual** | Media | `registrar_cobro_fecha.md` | **Hecho 2026-07-08** — campo en diálogo Desk, `posting_date` en PE (`8aed9ef`); tests fecha pasada/futura (`b53ed5b`). |

| BL-9 | **Número de socio manual en alta** | Media | `socio_alta_edicion_secretaria.md` | **Hecho 2026-07-10** — `numero_socio` opcional en JSON/alta guiada/API; validación duplicado (`b53ed5b`). |

| BL-6 | **Portal socio inscripción (Vercel + API)** | Media | `portal_socio_inscripcion.md` | **Pendiente** (post-pago / socio logueado). El **wizard de alta** ya está en prod (`portal_alta_grupo_familiar.md`, 2026-08-19). |



**Orden sugerido al retomar:** **1)** commit + deploy GF (local → prod) · **2)** portal socio (BL-6) · **3)** grupo familiar · ops Excel.



---

## Resumen sesión 2026-07-05 (tarde)

### Dashboard Actividades (mañana / sesión previa)

- Gráfico «Inscripciones por deporte / actividad»: título renombrado, leyenda oculta, tooltip por grupo, filtros y colores. Deploy prod `eb1ebb1`.
- Import real padrón prod: 481 inscripciones nuevas, 664 activas totales; socio 12063 no encontrado.

### BL-3 — Básquet unificado (tarde)

| Entregable | Detalle |
|------------|---------|
| Spec | `basquet_estructura_unificada.md` |
| Seed | `ESTRUCTURA_BASQUET` — actividad única **Basquet**, 6 grupos, equipos con aranceles ICDPE |
| Catálogo ICDPE | 16 actividades (antes 18); una entrada `Basquet` |
| Migración | `migrate_basquet_inscripciones.py` + patch `migrate_basquet_estructura_unificada` |
| Mapeo compartido | `basquet_unified_map.py` (migración, roster Excel, padrón CSV) |
| Fix PostgreSQL | `table_exists("Actividad")` en lugar de `"tabActividad"` |
| Tests | seed, catálogo, migración, roster, padrón, aranceles — OK |
| Commit | `1aedd3a` en `mvp/secretaria-2026-06` |
| Prod | Deploy OK; 185 inscripciones activas bajo `Basquet`; 0 en legacy; 6 grupos habilitados |

### Pendientes derivados (no bloquean operación)

| # | Tema | Prioridad | Notas |
|---|------|-----------|-------|
| BL-6 | **Portal socio inscripción (Vercel + API)** | Media | `portal_socio_inscripcion.md` | **Pendiente** — ver spec: deportes = solo actividad; variantes = actividad + grupo; tira/equipo deportivo = Secretaría al validar alta. |

---

## Resumen sesión 2026-07-06 — cierre sprint BL-1–BL-5

### Deploy producción (tarde 2026-07-05 + mañana 2026-07-06)

| Entregable | Detalle |
|------------|---------|
| Beca Socio | `2e5a3e9` — DocType, cobranza, panel Desk |
| Secretaría fixes | `6389d69` — cargo extra, KPIs, login SICLUB, sidebar |
| BL-4/BL-5 | `f436d2c` — CC unificado, specs legacy, verify/purge |
| Verificación prod | `verify_and_purge_basquet_legacy` OK → purga legacy ejecutada |

### Sprint backlog — estado final

| Ítem | Estado |
|------|--------|
| BL-1 Beca Socio | Hecho + prod |
| BL-2 Login SICLUB | Hecho + prod |
| BL-3 Básquet unificado | Hecho + prod |
| BL-4 CC ERPNext básquet | Hecho + prod + purga |
| BL-5 Specs legacy | Hecho |
| BL-6 Portal socio (Vercel + API) | **Pendiente** |
| BL-7 Recibo cobro Desk | Hecho + prod (`e58bfbc`) |
| BL-8 Fecha de cobro | Hecho + prod (`8aed9ef` / tests `b53ed5b`) |
| BL-9 Número socio manual | Hecho + prod (`b53ed5b`) |
| Grupo familiar | **Pendiente** (sin spec dedicada aún) |
| GF-0…GF-9 Gestión Financiera | **Hecho en local** — **falta commit parcial + deploy prod** (ver Gap producción 2026-07-19) |

**Retomar desde:** deploy GF a prod → luego BL-6 o grupo familiar.



## Resumen sesión 2026-07-08 / 2026-07-10 — cobranza Secretaría

### Contexto

Error en producción al **Registrar cobro** desde formulario Socio: `NameError: build_recibo_pago is not defined` en `cobranza_desk.registrar_cobro` (ruta `Form/Socio/11479`, factura `ACC-SINV-2026-00380`).

### Entregables

| Tema | Commit | Detalle |
|------|--------|---------|
| Fix recibo en cobro | `e58bfbc` | Import `build_recibo_pago` en `cobranza_desk.py` |
| Cobranza julio + datos críticos | `8aed9ef` | Advertencia datos críticos, complementar aranceles, ops import Excel, fecha de cobro en Desk |
| Guardar Socio incompleto | `cdeb0d8`–`4a2bcea` | Secretaría puede guardar Socio sin mandatory completos |
| Sync saldo sin tocar modified | `a904e36` | `sync_saldo_deuda_socio` no altera `modified` del Socio |
| Número socio manual + tests fecha | `b53ed5b` | Alta guiada/API, JSON opcional, tests duplicado y `posting_date` |

### Validación local (`dev.localhost`)

| Módulo | Tests | Resultado |
|--------|-------|-----------|
| `test_socio` | `test_numero_socio_duplicado_falla_en_insert` | OK |
| `test_socio_alta_secretaria` | alta manual + duplicado | OK (2) |
| `test_registrar_cobro_postgres` | fecha pasada / futura | OK (2) |
| `test_recibo_pago` | formato + integración cobro | OK (8) |

### Validación UI

- Local: Socio **11479**, cobro `ACC-SINV-2026-00380`, Efectivo → PE `ACC-PAY-2026-00009`, saldo $0, recibo generado.
- Prod: Desk carga Socio 11479 con menú cobranza; `get_recibo_pago` OK.

### Deploy producción

- Script: `scripts/prod/deploy-club-management.sh`
- Commit en Hetzner: **`b53ed5b`** (2026-07-10)
- URL: https://gestion.icdpedroechague.com.ar

### Pendientes derivados (no bloquean operación)

| # | Tema | Prioridad | Notas |
|---|------|-----------|-------|
| BL-6 | **Portal socio inscripción (Vercel + API)** | Media | `portal_socio_inscripcion.md` — deportes: solo actividad; variantes: actividad + grupo; tira/equipo: Secretaría. |
| — | **Grupo familiar** | Media | Sin spec dedicada aún. |
| — | **Ops cobranza Excel julio** | Baja | Scripts `members/ops/import_cobranza_excel.py` en prod; validar carga masiva con Secretaría. |




## Bugs conocidos — producción



| # | Bug | Prioridad | Detalle |

|---|-----|-----------|---------|

| B1 | **Cancelación de Sales Invoice falla en PostgreSQL** | ~~Alta~~ **Resuelto 2026-07-01** | `delink_original_entry` asignaba `delinked=true` (boolean) a columna `smallint`. Parche en `payment_ledger_postgres.py` + spec `sales_invoice_cancel_postgres.md` + test `test_sales_invoice_cancel_postgres.py`. Desplegar y reiniciar workers para activar. |
| B2 | **`get_negative_outstanding_invoices` en Payment Entry (PostgreSQL)** | ~~Media~~ **Resuelto 2026-07-05** | Parche en `payment_ledger_postgres.py`. `test_moroso_automatico`: 6/6 OK. |
| B3 | **`NameError: build_recibo_pago` en registrar cobro Desk** | ~~Alta~~ **Resuelto 2026-07-08** | Faltaba import en `cobranza_desk.py`. Fix `e58bfbc`; tests `test_recibo_pago` + UI Socio 11479 OK. |



---



## Módulo Gestión Financiera (GF)



**Decisión:** egresos vía **Purchase Invoice** + Payment Entry. Ingresos eventuales vía Sales Invoice + Payment Entry. Cuotas/aranceles siguen cobranza existente.



| Ítem | Spec | Estado | Notas |

|------|------|--------|-------|

| GF-0 Specs | `rol_tesoreria_permisos.md`, `carga_rapida_ingreso_egreso.md`, `proyeccion_flujo_fondos.md`, `items_finance_cost_center.md` | [x] | 2026-07-10 · **solo local** |

| GF-1 Rol Tesorería + permisos | `rol_tesoreria_permisos.md` | [x] | Rol `Tesoreria`; workspace Tesorería · **solo local** |

| GF-2 Carga rápida ingreso/egreso | `carga_rapida_ingreso_egreso.md` | [x] | SI / PI / PE; `club_concepto` · **solo local** (egreso ahora = Borrador, ver GF-8) |

| GF-3 Proyección flujo de fondos | `proyeccion_flujo_fondos.md` | [x] | Script Report + API; ventana 5 días · **solo local** (+ borradores en GF-8) |

| GF-4 Ítems + Cost Center | `items_finance_cost_center.md` | [x] | Catálogo `ICDPE-FIN-*` · **solo local** |

| GF-5 Recordatorio provisión sueldos | `recordatorio_provision_sueldos_secretaria.md` | [x] | Banner último día hábil · **solo local** |

| GF-6 Feriados + acceso operativo Secretaría | `recordatorio_provision_sueldos_secretaria.md`, `rol_tesoreria_permisos.md` | [x] | **2026-07-17 · solo local.** Feriados AR en último día hábil (`Holiday List` + seed 2026); acceso operativo Secretaría a Finanzas (PI/PE/Supplier; sin flujo/P&L). Commits `6779ce2`, `d7c9117`, `d12f313`. |

| GF-7 Español en UI | `ui_espanol_sin_ingles.md` | [x] | **2026-07-17 · solo local.** Labels Tesorería + `es.csv`. Incluido en `60795d0`. |

| GF-7b i18n global | `ui_espanol_sin_ingles.md` | [x] | **2026-07-17 · solo local.** `app_title` SICLUB; módulos ES; panel Actividades. |

| GF-8 Flujo egresos Borrador → Aprobación | `flujo_egresos_borrador_aprobacion.md`, `tesoreria_panel_operaciones.md` | [x] | **2026-07-17/19 · solo local, sin commit.** Elimina Purchase Order del club. Secretaría carga PI en Borrador (sin submit); Tesorería aprueba (Submit) / rechaza. Validación `due_date` + `cost_center`. Panel Tesorería custom (PAGOS PENDIENTES = borradores). Flujo de fondos: fila «Gastos proyectados (pendientes de aprobación)». Botón Secretaría «Registrar Nuevo Gasto / Comprobante». Tests `test_purchase_invoice_flujo` (10) + suites relacionadas OK. |

| GF-9 Centros de costo cobranza | `centro_costo_arancel_actividad.md` | [x] | **2026-07-17 · solo local, sin commit.** Aranceles → CC de la actividad (Item Default); Cuota Social → CC dedicado **Cuotas Sociales**; backfill histórico + repost GL. |

| GF-HRMS | — | [ ] | **Fase posterior:** app HRMS / liquidación nativa de sueldos. **No implementar aquí.** |



**Fuera de alcance GF (esta fase):** conciliación bancaria automática, gateway Cobros Plus en prod, Payment Log SIRO, modificar plan de cuentas importado.

**Update 2026-07-19:** GF-0…GF-9 cerrados en **código local**. **Ninguno** está en producción (prod = `35eb00c`). Pendiente: **commit** del working tree (GF-8/GF-9 + panel), **push**, **deploy** Hetzner + migrate/build. Pendiente UX: validar con Secretaría/Tesorería reales. **Fix render Query Report Flujo de Fondos:** `frappe.router.slug()` sin argumento en `club_desk_navigation.js` / `inicio_workspace.js` (error `toLowerCase`) — corregido y verificado en Desk local.



---



## Gap producción (2026-07-19)



| Entorno | Commit HEAD | Notas |
|---------|-------------|-------|
| **Producción** Hetzner | `35eb00c` | Informes Desk (páginas separadas / colapsables). Sin módulo Finanzas. |
| **Local** (rama `mvp/secretaria-2026-06`) | `d12f313` + **working tree dirty** | 4 commits ahead de `origin`; cambios GF-8/GF-9 y panel **sin commit**. |

### En producción hoy (ya desplegado)

- MVP Secretaría (socios, inscripciones, cobranza, KPIs, informes).
- BL-1…BL-5, BL-7…BL-9 (beca, login SICLUB, básquet unificado, recibo, fecha cobro, nº socio).
- Informes Desk ampliados hasta `35eb00c`.

### Implementado en local — **falta deploy a prod**

| Bloque | Commits / estado | Qué incluye |
|--------|------------------|-------------|
| GF-0…GF-5 + GF-7/7b | `60795d0` (committed, no en prod) | Módulo Finanzas, rol Tesorería, carga rápida, flujo de fondos, ítems FIN-*, recordatorio sueldos, UI ES / SICLUB |
| GF-6 | `6779ce2`, `d7c9117`, `d12f313` | Feriados AR + Holiday List; Secretaría operativa en Finanzas; módulo visible |
| GF-8 + panel Tesorería | **sin commit** | Flujo PI Borrador→Aprobación; quitar PO; panel custom; permisos PI; validación; flujo fondos con proyectados |
| GF-9 | **sin commit** | CC arancel = actividad; CC Cuotas Sociales + backfill |

### Pendiente de implementar (producto / backlog)

| # | Tema | Prioridad | Spec / notas |
|---|------|-----------|--------------|
| BL-6 | Portal socio inscripción (Vercel + API) | Media | `portal_socio_inscripcion.md` |
| — | Grupo familiar | Media | Sin spec dedicada |
| GF-HRMS | Liquidación sueldos nativa | Baja | Fuera de fase GF actual |
| — | Cancelar SI impaga + regenerar cargo | Alta | Spec `cancelar_factura_venta_impaga.md` — implementado local (Desk Socio) |
| — | Ops cobranza Excel / validar con Secretaría | Baja | Scripts ops |
| — | Job Vitalicio | Media | `socios_categoria_validacion.md` |



---



## Resumen sesión 2026-07-17 / 2026-07-19 — Gestión Financiera (local)



### Features cerradas en local

1. **GF-6** — Feriados argentinos en recordatorio de provisión de sueldos + acceso operativo de Secretaría a Finanzas (sin P&L / flujo).
2. **GF-7 / GF-7b** — UI en español (Finanzas) + branding SICLUB + traducción de módulos.
3. **Panel Tesorería custom** — workspace full-width, sidebar 🏦, botones + listas PAGOS PENDIENTES / PAGOS REALIZADOS / COBRANZA.
4. **GF-8** — Flujo único de egresos: `Purchase Invoice` Borrador (Secretaría) → Presentar (Tesorería); sin `Purchase Order`.
5. **GF-9** — Imputación correcta de centros de costo (aranceles → actividad; cuota social → «Cuotas Sociales») + backfill.

### Verificación

- Suites: `test_purchase_invoice_flujo`, `test_tesoreria_panel`, `test_flujo_fondos`, `test_carga_rapida`, `test_secretaria_finance_permissions` — OK en `dev.localhost`.
- Navegador local: panel Tesorería y formulario PI OK; reporte Flujo de Fondos con bug de render (datos OK vía `bench execute`).

### Próximo paso operativo

1. Commit del working tree (GF-8, GF-9, panel, patches).
2. Push a `origin/mvp/secretaria-2026-06` (incluye los 4 commits GF ya locales).
3. Deploy: `./scripts/prod/deploy-club-management.sh` + smoke Desk (Secretaría + Tesorería).
4. Post-migrate: confirmar Holiday List AR, permisos PI, CC Cuotas Sociales.

> **Nota 2026-08-19:** GF ya está en producción (panel Tesorería, P&L, cash flow, liquidez 5 días, factores mora 10/20). El «próximo paso» de julio quedó cerrado. Ver sesión 2026-08-19.

---

---

## Módulo Gestión de Espacios (Spaces)

**Resumen completo:** `spaces_modulo_resumen.md`  
**Estado general:** `[~]` MVP+ operativo en Desk (local); **sin deploy prod documentado** al 2026-08-27.  
**Tests:** ~74 casos en `club_management.spaces.*` — ver resumen del módulo.

### Entregado

| ID | Tema | Spec | Estado |
|----|------|------|--------|
| SP-MVP | Catálogo `Espacio` + grilla `Horario Entrenamiento` | `spaces_catalogo_ocupacion.md` | [x] |
| SP-MVP | `Reserva Espacio` (Confirmada ocupa; tipos abajo) | `spaces_catalogo_ocupacion.md` | [x] |
| SP-MVP | Alquiler externo Temporal / Recurrente | `spaces_alquiler_externo.md` | [x] |
| SP-MVP | Planilla Desk 08:00–04:00 (`/desk/ocupacion-espacios`) | `spaces_ocupacion_dashboard.md` | [x] |
| SP-MVP | Import CSV grilla L–V y sábado | `import_horarios.py` | [x] |
| SP-MVP | Fixtures FeBAMBA GES (JSON + sync Desk + ventanas partido) | `spaces_fixtures_partidos.md` | [x] |
| SP-MVP | Superposiciones (rojo) + selector al clic | `spaces_ocupacion_dashboard.md` | [x] |
| SP-MVP | Excepción día: reubicar / suspender entrenamiento | `spaces_excepcion_horario_dia.md` | [x] |
| SP-MVP | Suspensión día: reserva/evento sin cancelar base | `spaces_suspension_reserva_dia.md` | [x] |
| SP-MVP | Eventos sociales CSV → Evento club recurrente | `spaces_evento_club_social.md` | [x] |
| SP-MVP | Tipos planilla + orden fijo de columnas | `spaces_modulo_resumen.md` | [x] |
| SP-MVP | Rol `Coordinacion` + workspace Espacios | patches `sync_espacios_*` | [x] |

**Tipos de evento en planilla:** Entrenamiento · Preparacion Fisica · Alquiler externo · Alquiler socio · Evento club · Bloqueo.

**Orden columnas:** Cancha 1 → Cancha 2 → Cancha 3 → Gimnasio Bajo Tribuna → SALON PB → SUM PB → SUBSUELO → SALA ALBAMONTE → PARRILLA/TERRAZA → LA CASONA.

### Pendiente (Spaces)

| ID | Tema | Prioridad | Spec / notas |
|----|------|-----------|--------------|
| **SP-1** | **Sincronizar fixtures FMV (Vóley)** | **Alta** | Adaptador en `spaces/fixtures/sources/`; contrato payload + upsert idempotente; botón/cron en planilla. Hoy: solo carga manual. `spaces_fixtures_partidos.md` § otras federaciones. |
| **SP-2** | **Carga fixtures de ligas desde Excel** | **Alta** | Import Desk: Excel → preview → upsert `Reserva Espacio` (idempotente). Complementa CSV FeBAMBA y grilla Coordinación. |
| SP-3 | Reservas online socio + externo + comprobante PDF | Media | Épica 1 — `spaces_sprint_gestion.md` |
| SP-4 | Disponibilidad en vivo (estados que bloquean) | Media | Épica 2 — `spaces_sprint_gestion.md` |
| SP-5 | Reporte diario PDF/Excel → email coordinador/es | Media | Épica 4 — replicación manual WhatsApp CD |
| SP-6 | Cobro alquiler (Cobrand / ítems ICDPE-ALQ) | Baja | `spaces_fases_futuras.md` |
| SP-7 | Portal socio — reserva espacios alquilables | Baja | `spaces_fases_futuras.md` |
| SP-8 | Deploy prod Hetzner + smoke planilla/fixtures | Media | Tras validación Coordinación en dev |

### Próximo paso sugerido (Spaces)

1. **SP-1 FMV:** definir fuente (API, Excel periódico o export web) → spec Given/When/Then → adaptador + tests.
2. **SP-2 Excel ligas:** plantilla Excel acordada con Coordinación → import Desk con informe de errores.
3. Validar en dev con Coordinación un viernes con cena vitalicios + partido FeBAMBA + superposición.
4. Deploy a prod cuando CD apruebe planilla operativa.

---

## Pendiente post go-live 2026-08-19

| # | Tema | Prioridad | Spec / notas |
|---|------|-----------|--------------|
| BL-10 | **Wizard de alta pública (landing + Frappe)** | — | **Hecho + prod** — `portal_alta_grupo_familiar.md`, landing `d2cd386`, Frappe `43b226f` |
| BL-11 | **Adjuntos vigentes / File privado** | — | **Hecho + prod** — `almacenamiento_documentacion_socios.md`, `e94ea02` |
| BL-12 | **Tesorería P&L + cash flow** | — | **Hecho + prod** — `informes_tesoreria_pnl_cashflow.md`, `b4ed98b` |
| BL-13 | **Alta post-baja** | — | **Hecho + prod** — `socio_alta_post_baja.md`, `4dfe560` |
| BL-14 | Filtro tendencia KPI (todos / cuota / arancel / mora) | Media | WIP `stash@{0}` — no bloquea |
| BL-15 | Informe pagos del día (concepto `Cuota Social · categoría`) | Baja | WIP `stash@{0}` |
| BL-16 | Liquidación por inscripción (cuota/arancel/federativa) | Baja | WIP `stash@{0}` — validar con caso real |
| BL-6 | Portal socio inscripción post-pago | Media | Distinto del wizard de alta |
| — | Smoke humano: 1 Adherente + 1 Jubilado de prueba en prod | Alta | Verificar solicitud en Desk y adjuntos privados |
| — | UAT Cloudflare / túnel | — | **Cerrado** — túnel apagado; Preview ya no apunta a Frappe local |

---

## Resumen sesión 2026-08-19 — go-live portal + Tesorería

### Qué salió a producción (Hetzner `mvp/secretaria-2026-06`, HEAD `43b226f`)

| Bloque | Commit | Qué |
|--------|--------|-----|
| Portal alta familiar | `9385c1b` | `Solicitud Grupo Familiar` + API Guest + wizard |
| Mora proyección 10/20 | `131aec9` | Factores en flujo de fondos |
| Liquidez 5 días | `fba539e` | KPI Tesorería |
| Spec storage | `610cbbf` | Plan docs multi-club |
| P&L + cash flow | `b4ed98b` | Reportes Desk + panel Tesorería (roles Tesorería) |
| Adjuntos vigentes | `e94ea02` | Pisa File anterior; clona privados al Socio |
| Validación Adherente/Jubilado | `43b226f` | Edad, whitelist deportes, comprobante haberes |

**Landing** (`pedro-echague-landing-page` `main` `d2cd386`): wizard en https://www.icdpedroechague.com.ar/asociate/inscripcion  
Vercel Production: `FRAPPE_BASE_URL` / `FRAPPE_SITE_HOST` = `gestion.icdpedroechague.com.ar`. Túnel UAT apagado.

### Verificación automática

- Tests: `test_alta_grupo_familiar` 18/18, `test_documentacion_socio` 7/7, `test_informes_tesoreria` 7/7, `test_datos_criticos_socio` 6/6.
- Smoke: `/api/inscripcion/catalogo` 200 — categorías Activo/Menor/Adherente/Jubilado; `actividades_adherente` Fitness/Funcional/Yoga/Crossfit; adjunto `comprobante_jubilado`.
- Desk: `get_panel_lists` OK (~1091 socios). Rol Tesorería: Carolina Antoliche, Luis Oriolo. Guest upload files: on.

### Qué **no** se desplegó (stash leftover)

Post-baja / botón «Dar de alta» ya estaba en prod (`4dfe560`). El stash restante es KPIs de tendencia, pagos del día y liquidación por equipo.

### Mañana (prioridad)

1. Secretaría: 1 alta de prueba Adherente + 1 Jubilado en el sitio público → revisar en Desk (Pendiente, adjuntos privados).
2. Tesorería: hard refresh → Ganancias y Pérdidas / Flujo de efectivo / liquidez.
3. Decidir si extraer BL-14/15/16 del stash a un PR chico.






# Resumen — Módulo Gestión de Espacios (Spaces)

**Módulo Frappe:** `Spaces`  
**Rol principal:** `Coordinacion` (+ `Secretaria` escritura, `Tesoreria` lectura)  
**Workspace Desk:** Espacios · planilla: `/desk/ocupacion-espacios`  
**Última revisión:** 2026-09-07 — **en testing** (Coordinación / Desk local). SP-1 FMV live habilitado; SP-2 listo; SP-3 pendiente.

---

## Objetivo

Gestionar la **ocupación física** del club (canchas, gimnasios, salones): grilla semanal
de entrenamientos, reservas puntuales/recurrentes, partidos importados de federaciones
y la **planilla operativa** tipo Excel (08:00 → 04:00) para Coordinación.

Separado del catálogo deportivo (`Actividad` → `Grupo` → `Equipo`): un **Espacio** es
un lugar; un **Horario Entrenamiento** es quién entrena cuándo; una **Reserva Espacio**
es ocupación adicional (evento, alquiler, partido, bloqueo).

---

## Modelo de datos

```
Espacio
├── horarios[]           → Horario Entrenamiento (grilla semanal recurrente)
├── Reserva Espacio      → ocupación puntual o recurrente (Confirmada ocupa)
├── Excepcion Horario Dia → ajuste/suspensión de grilla solo un día
└── Suspension Reserva Dia → omitir reserva Confirmada solo un día
```

| DocType | Rol |
|---------|-----|
| **Espacio** | Catálogo físico (`titulo`, `tipo`, `alquilable`, `habilitado`) |
| **Horario Entrenamiento** | Child table — día, horas, tipo sesión, vínculos Actividad/Grupo/Equipo |
| **Reserva Espacio** | Evento, alquiler, bloqueo, partido fixture; puntual o recurrente |
| **Reserva Espacio Dia** | Días de recurrencia (alquiler externo / evento club semanal) |
| **Excepcion Horario Dia** | Reubicar o **suspender** entrenamiento de grilla un día |
| **Suspension Reserva Dia** | **Suspender** reserva/evento un día sin cancelar la base |

---

## Tipos de evento en la planilla

Seis categorías con color estable en la leyenda:

| Categoría | Origen |
|-----------|--------|
| **Entrenamiento** | Grilla — `Horario Entrenamiento.tipo_sesion` |
| **Preparacion Fisica** | Grilla |
| **Alquiler externo** | `Reserva Espacio` |
| **Alquiler socio** | `Reserva Espacio` |
| **Evento club** | `Reserva Espacio` (cenas, jubilados, partidos locales, etc.) |
| **Bloqueo** | `Reserva Espacio` (reparación, mantenimiento) |

Además: **Reubicado** (violeta, excepción del día) y **Superposición** (rojo, revisar).

Catálogo central: `spaces/planilla.py` (`COLOR_POR_TIPO`, `ESPACIO_ORDEN_PLANILLA`).

---

## Orden de columnas (planilla)

1. Cancha 1 · 2. Cancha 2 · 3. Cancha 3  
4. Gimnasio Bajo Tribuna · 5. SALON PB · 6. SUM PB  
7. SUBSUELO · 8. SALA ALBAMONTE · 9. PARRILLA/TERRAZA · 10. LA CASONA  

Encabezados abreviados vía `titulo_planilla` (ej. «Cancha 1» en lugar del nombre largo del DocType).

---

## Motor de ocupación (`availability.py`)

- Expande **grilla** del día (omite filas con excepción Activa).
- Suma **excepciones destino** (solo acción Reubicar).
- Suma **reservas Confirmada** (puntual o recurrente; excluye suspendidas ese día).
- Valida solapes al confirmar reservas (fixtures pueden coexistir con grilla vía flag).
- PostgreSQL v14; sin SQL MariaDB.

---

## Importación de datos

### Grilla fija L–V y sábado (`import_horarios.py`)

- CSV Coordinación (`horarios_lunes_viernes.csv`, `horarios_sabado.csv`).
- Mapeo GIMNASIO 1/2/3 → Canchas 1/2/3.
- `ALQ.*` → **Alquiler externo** recurrente.
- Eventos sociales (`CENA`, `VITALICIO`, `JUBILADOS`, …) → **Evento club** recurrente (no grilla).
- Patches: `import_horarios_lunes_viernes`, `import_horarios_sabado`.

### Fixtures / partidos (`spaces/fixtures/`)

- Contrato `FixturePartidoPayload` → upsert idempotente en `Reserva Espacio`.
- Ventanas por categoría (Liga Metro, Superior B, Formativas, default).
- Básquet local sin espacio → **Cancha 3**; `superposicion_detectada` si solapa grilla.
- **FeBAMBA GES:** JSON desde `formativas_ges` (URL canónica GitHub raw).
- API Desk: `sync_fixtures_febamba`, `import_fixtures_json`, `import_fixtures_csv`.
- Botón «Sincronizar FeBAMBA» en planilla.
- Cron opcional 08:00 / 20:00 ART (`febamba_ges_fixture_sync_enabled` en `site_config.json`).

---

## Planilla Desk (`/desk/ocupacion-espacios`)

- Ventana **08:00 – 04:00** (día siguiente incluido en madrugada).
- Columnas = espacios; filas = franjas 30 min.
- **Superposición:** clic muestra diálogo para elegir cuál evento modificar.
- **Entrenamiento (grilla):** reubicar o suspender solo ese día.
- **Reserva/evento:** suspender solo ese día o abrir formulario.
- Roles: Coordinacion, Secretaria, Tesoreria (lectura), System Manager.

---

## APIs Desk (whitelist + permisos)

| Método | Uso |
|--------|-----|
| `spaces.api.ocupacion_dashboard.get_ocupacion_dashboard` | Payload planilla |
| `spaces.api.excepcion_horario.reubicar_horario_dia` | Reubicar grilla |
| `spaces.api.excepcion_horario.suspender_horario_dia` | Suspender grilla |
| `spaces.api.suspension_reserva.suspender_reserva_dia` | Suspender reserva |
| `spaces.api.fixtures_desk.*` | Import/sync fixtures |

---

## Espacios sembrados (`seed.py`)

GIMNASIO BAJO TRIBUNA, SALON P.B., SUM P.B., SUBSUELO, SALA ALBAMONTE,
PARRILLA - TERRAZA, LA CASONA (+ canchas con nombres oficiales vía import/patches).

---

## Specs (SDD)

| Spec | Tema |
|------|------|
| `spaces_catalogo_ocupacion.md` | Espacio, grilla, reservas base |
| `spaces_alquiler_externo.md` | Alquiler Temporal / Recurrente |
| `spaces_ocupacion_dashboard.md` | Planilla Desk |
| `spaces_fixtures_partidos.md` | Partidos manual + FeBAMBA |
| `spaces_excepcion_horario_dia.md` | Reubicar / suspender grilla |
| `spaces_suspension_reserva_dia.md` | Suspender reserva |
| `spaces_evento_club_social.md` | Cenas / eventos sociales CSV |
| `spaces_sprint_gestion.md` | Épicas futuras (online, reporte CD) |
| `spaces_fases_futuras.md` | Portal socio, cobro externo |

---

## Tests automatizados (~74 casos)

Ubicación: `spaces/tests/`, `spaces/doctype/*/test_*.py`.

Cobertura principal: disponibilidad, import CSV, fixtures FeBAMBA, ventanas partido,
dashboard, excepciones, suspensiones, eventos sociales, permisos Coordinacion,
DocTypes Espacio / Reserva Espacio.

```bash
bench --site dev.localhost run-tests --app club_management \
  --module club_management.spaces.tests
```

---

## Comandos operativos

```bash
# Migrar tras cambios DocType
bench --site dev.localhost migrate
bench build --app club_management

# Reimportar grilla L–V
bench --site dev.localhost execute club_management.spaces.import_horarios.import_horarios_csv

# Sync FeBAMBA
bench --site dev.localhost execute \
  club_management.spaces.fixtures.sources.febamba_ges.sync_febamba_ges_from_url \
  --kwargs '{"cancel_missing": true}'
```

---

## Entregado vs pendiente

### Entregado (MVP+ operativo Desk) — **en testing Coordinación (2026-09-07)**

- [x] Catálogo Espacio + grilla semanal + reservas Confirmada
- [x] Alquiler externo Temporal / Recurrente
- [x] Evento club recurrente (cenas, jubilados)
- [x] Import CSV grilla L–V y sábado
- [x] Fixtures FeBAMBA GES (JSON + API + planilla)
- [x] Sync FMV Vóley live (JSON + API + planilla + cron local habilitado) — SP-1
- [x] Import Excel ligas (preview/apply Desk) — SP-2
- [x] Planilla 08:00–04:00 con tipos, colores y orden de columnas
- [x] Superposiciones visibles + selector al clic
- [x] Reubicar / suspender entrenamiento del día
- [x] Suspender reserva/evento del día
- [x] Rol Coordinacion + workspace Espacios

### Pendiente (próximos tramos)

| # | Tema | Notas |
|---|------|-------|
| SP-3 | Reservas online socio/externo + comprobante | Épica 1 — `spaces_sprint_gestion.md` |
| SP-4 | Disponibilidad en vivo (estados que bloquean) | Épica 2 |
| SP-5 | Reporte PDF/Excel diario → email coordinador/es | Épica 4 |
| SP-6 | Cobro alquiler (Cobrand / ítems ICDPE-ALQ) | `spaces_fases_futuras.md` |
| SP-7 | Portal socio reserva espacios alquilables | `spaces_fases_futuras.md` |

---

## Dependencias externas

| Fuente | Estado |
|--------|--------|
| **FeBAMBA / formativas_ges** | Integrado (JSON GitHub) |
| **FMV (Vóley)** | Integrado; JSON raw público y cron habilitado en `dev.localhost` |
| **Excel ligas varias** | **Integrado** — plantilla canónica + preview/apply Desk |
| **Google Sheet CM** | Consumido vía export JSON del repo GES (no lectura directa Sheet en prod) |

---

## Archivos clave (código)

```
spaces/
  planilla.py              # tipos, colores, orden columnas
  availability.py          # motor ocupación
  import_horarios.py       # CSV grilla + eventos sociales
  fixtures/                # partidos federativos
  services/ocupacion_dashboard.py
  api/                     # whitelist Desk
  doctype/                 # Espacio, Reserva, Excepcion, Suspension
public/js/ocupacion_espacios_page.js
public/scss/ocupacion_espacios.scss
```

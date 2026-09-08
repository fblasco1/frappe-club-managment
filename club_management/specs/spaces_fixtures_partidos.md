# Spec: Fixtures / partidos — carga manual y conectores federativos

Partidos y jornadas **variables** (no entran en la grilla semanal fija). Complementan
`Horario Entrenamiento` (actividades recurrentes) y `Reserva Espacio` (alquileres,
eventos puntuales).

**Relacionado:** `spaces_catalogo_ocupacion.md`, `spaces_sprint_gestion.md`,
`import_horarios.py` (grilla fija L–V / sábado).

---

## Principio

| Tipo | Fuente típica | Destino en sistema |
|------|---------------|-------------------|
| Actividades fijas | CSV Coordinación / import manual | `Horario Entrenamiento` en `Espacio` |
| Partidos / jornadas | Manual, CSV, Excel (pendiente), o federación | `Reserva Espacio` Confirmada (`Evento club`, `Alquiler socio`, etc.) |
| «Si hay jornada» (ej. vóley sábado) | Solo cuando hay fixture | No va en grilla; solo reservas del día |

La ocupación del dashboard y el motor `availability.py` ya leen grilla + reservas Confirmada.

---

## Épica A — Carga manual de fixtures (MVP)

### Scenario: Coordinación importa partidos desde CSV

Given un CSV con columnas mínimas: `fecha`, `hora_desde`, `hora_hasta`, `espacio` (o `GIMNASIO N`), `actividad`/`equipo`, `rival`, `origen=manual`
When Coordinación ejecuta import desde Desk o `bench execute`
Then se crean o actualizan `Reserva Espacio` Confirmada por clave estable (`origen` + `id_externo` o hash fecha+espacio+hora+equipo)
And el espacio se mapea con las mismas reglas que `import_horarios` (GIMNASIO 1 → Cancha 1, …)
And un reporte lista filas omitidas y conflictos de solape (no pisa Confirmada sin confirmación explícita).

### Scenario: alta manual en Desk

Given rol Coordinacion o Secretaria
When crea `Reserva Espacio` tipo `Evento club` o `Uso interno`, Confirmada, con equipo/actividad en motivo
Then ocupa el calendario y aparece en la planilla del día
And puede editarse o cancelarse sin tocar la grilla semanal.

### Scenario: idempotencia

Given el mismo fixture importado dos veces
When corre el import con la misma clave externa
Then no duplica reservas; actualiza motivo/horario si cambió en la fuente.

---

## Épica B — Conectores federativos (adaptadores)

### Scenario: registro de fuente

Given Club Settings (o Single `Fixture Source`) con entradas: `febamba_basquet`, `manual`, …
When una fuente está `habilitada = 1`
Then aparece en «Sincronizar fixtures» y en jobs programados opcionales.

### Scenario: sync FeBAMBA vía formativas_ges (Básquet)

Given el Action **Sync fixture Echagüe → Sheets** en
[`fblasco1/formativas_ges`](https://github.com/fblasco1/formativas_ges)
(`analysis/sync_fixture_echague_sheets.py`, workflow `sync_echague_sheets.yml`)
And el Sheet/CSV de CMs ya tiene columnas
`FECHA | HORA | TIRA | CATEGORIA | RIVAL | LOCALIA | DIRECCION | RESULTADO | ID_PARTIDO`
When SICLUB sincroniza desde esa fuente (lectura Sheet o CSV export)
Then por cada fila con `LOCALIA = Local` se upsertea `Reserva Espacio` Confirmada
And `origen = febamba_ges`, `id_externo = ID_PARTIDO`
And `motivo` / etiqueta = `CATEGORIA` + tira + rival (ej. «U17 AZUL vs Rival»)
And filas `LOCALIA = Visitante` **no** ocupan espacios del club (solo informativas)
And partidos que desaparecen / cambian fecha se cancelan o actualizan por `ID_PARTIDO`.

### Scenario: payload alineado al Sheet CM (contrato)

El pipeline GES **sigue** escribiendo Google Sheets (uso de CMs). SICLUB **consume**
el mismo contrato sin re-scrapear GES:

```json
{
  "source": "febamba_ges",
  "external_id": "<ID_PARTIDO>",
  "fecha": "2026-09-06",
  "hora": "20:00",
  "tira": "AZUL",
  "categoria": "U17",
  "rival": "Club Visitante",
  "localia": "Local",
  "direccion": "Portela 836, CABA (CP 1406)",
  "resultado": "",
  "espacio": null
}
```

- `fecha` en Sheet viene `DD/MM/YYYY`; SICLUB normaliza a ISO.
- Ventanas de ocupación (kickoff = hora del JSON; si no hay `hora_hasta` explícita):

| Categoría | Entrada en calor | Duración partido | Ejemplo |
|-----------|------------------|------------------|---------|
| Liga Metro | 60 min antes | 90 min | 21:15 → bloquea 20:15–22:45 |
| Superior B (`SUP` + tira `B`) | 30 min antes | 90 min | 21:30 → bloquea 21:00–23:00 |
| Formativas (U9–U21, Flex, Fem) | 0 | 90 min | 09:00 → 09:00–10:30 |
| Resto | 0 | 120 min (default) | — |

- `espacio`: si viene vacío → **Cancha 3** (básquet).
- Upsert clave: `(origen, ID_PARTIDO)`.

### Scenario: básquet en Cancha 3 y superposiciones visibles

Given un partido Local importado desde FeBAMBA GES (básquet)
When el payload no trae `espacio`
Then se asigna **Cancha 3** (`Jorge Horacio Antoliche - Cancha 3`)
And la reserva se crea Confirmada aunque solape con grilla u otro evento
And `superposicion_detectada = 1` si hay conflicto horario en esa cancha/fecha
And el reporte de import incluye entradas en `superposiciones`
And la planilla `/desk/ocupacion-espacios` marca bloques solapados en rojo
And el listado `Reserva Espacio` filtrable por «Superposición detectada».

### Scenario: reubicar entrenamiento puntual del día (sin tocar grilla semanal)

Given un bloque de grilla (`Horario Entrenamiento`) que solapa un partido ese día
When Coordinación elige «Reubicar este día» desde la planilla
Then se crea una `Excepcion Horario Dia` Activa para esa fecha + fila de horario
And la ocupación del día **omite** el slot original de la grilla
And aparece el entrenamiento en `espacio_destino` con `hora_desde`/`hora_hasta` del ajuste
And la grilla semanal del Espacio **no** se modifica
And anular la excepción restaura el slot original ese día.

### Scenario: otras federaciones

Given vóley, futsal, etc. sin conector aún
When no hay adaptador habilitado
Then solo carga manual / CSV; la UI no promete sync automático.

### Scenario: sync FMV — Vóley (Echagüe club 420)

Given el fixture público de ICDPE en FMV:
`https://metrovoley.com.ar/clubs/420/matches`
And un extractor externo (repo tipo `formativas_ges`, **no** dentro de `club_management`)
publica `outputs/echague/fixture_fmv_voley.json` con el contrato de abajo
When Coordinación ejecuta «Sincronizar FMV» o corre el job programado (08:00 / 20:00 ART)
Then se upsertean partidos **locales** como `Reserva Espacio` Confirmada
And `origen_fixture = fmv_voley` + `id_externo_fixture` = ID numérico del partido en metrovoley
And filas visitante (Echagüe de visita) **no** ocupan espacios del club
And el reporte lista filas omitidas y superposiciones
And la planilla refleja los partidos el día correspondiente.

**Fuente web (referencia operativa):**

| Campo | Valor |
|-------|-------|
| URL club | `https://metrovoley.com.ar/clubs/420/matches` |
| `club_id` FMV | `420` |
| Detalle partido | `https://metrovoley.com.ar/matches/{id}` |

**Mapeo espacio (acordado con Coordinación):**

| Condición (equipo / categoría FMV) | Espacio SICLUB |
|-----------------------------------|----------------|
| Equipo exacto `SUPERIOR ECHAGÜE` (sin sufijo B) | **Cancha 1** |
| Equipo `SUPERIOR ECHAGÜE B` | **Cancha 2** |
| Resto de partidos locales en Portela | **Cancha 2** (default vóley) |

- El extractor puede enviar `espacio` ya resuelto; si viene vacío, SICLUB aplica la tabla anterior
  según `equipo` / `categoria` + `tira` del payload.
- Normalización de nombre: comparar case-insensitive, colapsar espacios, ignorar acentos opcionales
  (`ECHAGUE` ≈ `ECHAGÜE`).

**Ventana horaria vóley (propuesta inicial):**

| Tipo | Entrada en calor | Duración |
|------|------------------|----------|
| Formativas (Sub 13, Sub 15, …) | 0 | 90 min |
| Superiores / DH | 30 min | 90 min |
| Resto | 0 | 90 min |

**Contrato JSON (envelope, análogo FeBAMBA):**

```json
{
  "version": 1,
  "source": "fmv_voley",
  "generated_at": "2026-08-28T20:00:00-03:00",
  "club": "PEDRO ECHAGUE",
  "club_id_fmv": 420,
  "partidos": [
    {
      "source": "fmv_voley",
      "external_id": "753076",
      "fecha": "2026-08-28",
      "hora": "21:00",
      "categoria": "Sub 15",
      "tira": "Nivel E",
      "equipo": "SUB 15 ECHAGÜE",
      "rival": "SHOLEM B",
      "localia": "Local",
      "direccion": "Portela 836, CABA",
      "espacio": null
    }
  ]
}
```

- Campo nuevo opcional `equipo`: nombre del plantel en FMV (para reglas Cancha 1 vs 2).
- Upsert clave: `(origen_fixture, id_externo_fixture)`.

**Estado:** adaptador SICLUB y extractor externo — **implementados y publicados (2026-09-07)**.
El JSON canónico está disponible en la rama `main`; `dev.localhost` tiene
`fmv_voley_fixture_sync_enabled = true` y la prueba live resultó idempotente
(2 locales importados, 1 visitante omitido).

### Scenario: import fixtures de ligas desde Excel (SP-2)

Given un Excel (`.xlsx`) con hoja `Fixture` o la primera hoja y columnas canónicas:

| Columna | Requerida | Notas |
|---------|-----------|-------|
| `fecha` | sí | `DD/MM/YYYY` o ISO |
| `hora_inicio` | sí | Inicio aproximado del partido |
| `hora_fin` | sí | Fin aproximado del partido |
| `espacio` | sí | Nombre SICLUB o alias `GIMNASIO N` / `CANCHA N` |
| `categoria` | sí | Categoría deportiva |
| `tira` | sí | Tira / nivel / división |
| `rival` | sí | Club rival |

La planilla operativa no expone campos técnicos. SICLUB fija internamente
`origen = liga_excel` y `localia = Local`, genera `id_externo` determinístico
a partir de los datos del partido y deriva `equipo` como la conjunción
`tira + categoria`.

When Coordinación sube el archivo desde Desk (`preview_fixtures_excel`)
Then se listan filas OK y errores **sin escribir** en BD
And antes de seleccionar el archivo puede descargar `plantilla_fixture_ligas.xlsx`
And la plantilla contiene las columnas canónicas y filas de ejemplo editables
When confirma (`apply_fixtures_excel`)
Then se upsertean `Reserva Espacio` Confirmada por `(origen_fixture, id_externo_fixture)`
And un informe lista omitidos / errores / superposiciones
And reimportar el mismo archivo no duplica filas.

**Estado:** plantilla + parser Desk — **implementado (2026-09-07)**.

---

## Fuente concreta: fmv_voley_ges → JSON

| Pieza | Detalle |
|-------|---------|
| Repo | `github.com/fblasco1/fmv_voley_ges` (local: `../fmv_voley_ges`) |
| Action | `Sync fixture FMV Echagüe` (`sync_echague.yml`) |
| Schedule | 08:00 y 20:00 ART |
| Script | `analysis/sync_fixture_echague.py` |
| Fuente web | `https://metrovoley.com.ar/clubs/420/matches` (Inertia `data-page`) |
| Destino | `outputs/echague/fixture_fmv_voley.json` + CSV |
| Club filter | `club_id_fmv = 420` |
| Idempotencia | `external_id` = ID interno FMV (`match.id`) |

**URL canónica para SICLUB (tras push a main):**

```text
https://raw.githubusercontent.com/fblasco1/fmv_voley_ges/main/outputs/echague/fixture_fmv_voley.json
```

---

## Fuente concreta: formativas_ges → Sheets

| Pieza | Detalle |
|-------|---------|
| Repo | `github.com/fblasco1/formativas_ges` |
| Action | `Sync fixture Echagüe → Sheets` (`sync_echague_sheets.yml`) |
| Schedule | 08:00 y 20:00 ART |
| Script | `analysis/sync_fixture_echague_sheets.py` |
| Destino hoy | Google Sheet pestaña `Fixture` (+ CSV `outputs/echague/fixture_echague.csv`) |
| Club filter | nombre contiene `PEDRO ECHAGUE` |
| Competencias | Formativas 2015, Superior 2013, Flex 2018/2019, Femenina 2028 |
| Idempotencia GES | columna `ID_PARTIDO` (no editar en Sheet) |

**Opciones de puente a SICLUB (orden preferido):**

1. **Leer el mismo Sheet** desde Desk/cron (service account compartida o export).
2. **Extender el Action** con un job opcional: tras Sheets, publica
   `fixture_echague.csv` / JSON artifact o `POST` a API SICLUB (token).
3. **`--solo-csv`** del script en un runner que deposite el archivo en el bench
   y un patch/`bench execute` haga upsert.

No reimplementar scraping GES dentro de `club_management`.

---

## Arquitectura propuesta (módulo Spaces)

```
spaces/
  fixtures/
    contract.py          # FixturePartidoPayload (dataclass)
    parse.py             # fecha/hora/motivo
    espacio_map.py       # categoría/tira → Espacio
    upsert.py            # upsert_fixture_reserva(payload) → Reserva Espacio
    import_partidos.py   # CSV manual (similar a import_horarios)
    febamba_ges_sample.json
    sources/
      febamba_ges.py     # lee JSON del Action formativas_ges
  api/fixtures_desk.py   # whitelist: import_fixtures_json, sync_fixtures_febamba, sync_fixtures_fmv,
                         # preview_fixtures_excel, apply_fixtures_excel, import_fixtures_csv
```

**Implementado (2026-08-26):** upsert + JSON FeBAMBA + CSV + API Desk.
Campos en `Reserva Espacio`: `origen_fixture`, `id_externo_fixture`.
Partidos locales usan `flags.skip_grid_overlap_check` (coexisten con grilla semanal).

### Envelope JSON (formativas_ges → SICLUB)

Tras escribir el CSV, el Action debe publicar también
`outputs/echague/fixture_echague.json`:

```json
{
  "version": 1,
  "source": "febamba_ges",
  "generated_at": "2026-08-26T20:00:00-03:00",
  "club": "PEDRO ECHAGUE",
  "partidos": [ { ... contrato por partido ... } ]
}
```

Cada ítem del array usa el contrato de la sección «payload alineado al Sheet CM».

### Consumo en SICLUB

**Fuente canónica (producción):**

```
https://raw.githubusercontent.com/fblasco1/formativas_ges/main/outputs/echague/fixture_echague.json
```

No leer Google Sheet ni `docs/fixture_echague.json` (Pages). Override opcional en
`site_config.json`: `febamba_ges_fixture_json_url`. Cron automático (08:00 y 20:00 ART)
con `febamba_ges_fixture_sync_enabled`: true.

```bash
# Sync desde URL (producción, tras primer push a main)
bench --site dev.localhost execute \
  club_management.spaces.fixtures.sources.febamba_ges.sync_febamba_ges_from_url \
  --kwargs '{"cancel_missing": true}'

# Dev / fallback archivo local o sample embebido
bench --site dev.localhost execute \
  club_management.spaces.fixtures.sources.febamba_ges.import_febamba_ges_json \
  --kwargs '{"path": "/ruta/fixture_echague.json"}'

# API Desk (rol Coordinacion / Secretaria)
club_management.spaces.api.fixtures_desk.sync_fixtures_febamba   # URL por defecto
club_management.spaces.api.fixtures_desk.import_fixtures_json
```


---

## UI Desk (fase posterior al MVP CSV)

- Workspace **Espacios** → «Importar partidos» (CSV + preview + informe).
- Botones planilla: «Sincronizar FeBAMBA», «Sincronizar FMV», «Importar Excel ligas».
- Listado de reservas con filtro `origen` / próximos partidos.

---

## Orden sugerido

1. **Upsert común** + CSV manual partidos (MVP). — **[x] hecho**
2. **Consumir JSON** de `formativas_ges` (`ID_PARTIDO`, solo `LOCALIA=Local`). — **[x] hecho**
3. Cron Desk + botón planilla + `site_config` opcional. — **[x] hecho**
4. **FMV (Vóley)** — adaptador + sync (SP-1). — **[x] hecho**
5. **Fixtures ligas en Excel** — import Desk con plantilla acordada (SP-2). — **[x] hecho**
6. Otras federaciones (futsal, etc.) según prioridad deportiva.

---

## Fuera de alcance inicial

- Scraping FeBAMBA dentro de `club_management` (duplicar el otro proyecto).
- Portal público de fixture (solo ocupación interna / reporte Directiva).
- Cobro de entradas por partido (ítem ERPNext existe; flujo aparte).

# Activities — jerarquía: actividad, grupo/tira y equipo

## Modelo

```
Actividad (ej. Basquet, Funcional, Zumba)
├── usa_grupos = 0 → inscripción solo a la actividad (arancel en `Actividad.item`)
└── usa_grupos = 1 → puede tener Grupo Actividad (tira, división o variante de plan)
    └── Equipo Actividad (categoría U11, etc.) — solo deportes; lo asigna Secretaría
```

- **Grupo Actividad**: tira/división deportiva (Masculino / Azul) **o** variante de plan (Funcional 1 clase/semana, escuelita recreativa). Cada uno puede tener su **Item** de arancel.
- **Equipo Actividad**: categoría dentro del grupo deportivo (U11, U13). **No** lo elige el socio en el portal.
- **Inscripcion Actividad**: `socio` + `actividad` + `grupo_actividad` (cuando corresponde) + `equipo_actividad` (opcional; Secretaría en deportes).

**Zumba** y **Ritmos Latinos** son actividades distintas (`usa_grupos = 0` por defecto).

Aranceles básquet: `basquet_aranceles_icdpe.md`. Estructura unificada: `basquet_estructura_unificada.md`.

---

## Quién elige qué (Desk vs portal socio)

Ver **`portal_socio_inscripcion.md`** (BL-6). Resumen:

| Contexto | Deporte (Basquet, Fútbol, Voley) | Variante (Funcional, escuelita) | Plana (Zumba) |
|----------|----------------------------------|----------------------------------|---------------|
| **Portal socio (Vercel)** | Solo actividad | Actividad + grupo | Solo actividad |
| **Secretaría (Desk)** | Asigna grupo/tira + equipo al validar alta | — | — |

El portal del club se desarrolla en **Vercel** y se conecta a Frappe por API; no es cascada completa actividad→tira→equipo para el socio.

---

## Scenario: inscripción deportiva completa desde Desk

Given `Actividad` «Basquet» con `usa_grupos = 1`
And `Grupo Actividad` «Masculino / Azul» y `Equipo Actividad` «U11»
When Secretaría inscribe con actividad, grupo y equipo
Then existe `Inscripcion Actividad` activa con los tres vínculos
And el resumen en `Socio.actividad` incluye «Basquet (Masculino / Azul — U11)».

---

## Scenario: portal deporte — solo actividad

Given `Actividad` «Basquet» con `tipo_inscripcion_portal = deporte`
When el socio confirma inscripción desde Vercel con solo actividad
Then la inscripción queda sin grupo/equipo hasta que Secretaría los asigne en Desk.

---

## Scenario: portal variante — actividad y grupo

Given `Actividad` «Funcional» con `tipo_inscripcion_portal = variante_grupo`
And grupo «1 clase por semana» con `portal_socio_elige = 1`
When el socio elige actividad y grupo en Vercel
Then la inscripción incluye actividad + grupo y arancel del ítem del grupo.

---

## Scenario: actividad sin grupos (Zumba)

Given `Actividad` «Zumba» con `usa_grupos = 0`
When se inscribe un socio solo con `actividad = Zumba`
Then la inscripción no requiere grupo ni equipo
And el arancel se resuelve desde `Actividad.item`.

---

## Scenario: arancel por grupo

Given «Masculino / Azul» con `item` = Item arancel A
When se resuelve el ítem de cobro para una inscripción a Masculino / Azul
Then devuelve Item arancel A (no el de la actividad padre si el grupo tiene ítem).

---

## Scenario: catálogo ICDPE incluye Zumba y Ritmos Latinos

Given el patch de sincronización ICDPE
Then existen 14 actividades habilitadas incluyendo **Basquet**, **Zumba** y **Ritmos Latinos** como filas separadas.

---

## Scenario: seed operativo del club

Given el patch `seed_estructura_actividades_completa`
Then las 14 actividades ICDPE están habilitadas
And **Basquet**, **Voley Femenino** y **Futbol** tienen `usa_grupos = 1`
And la actividad **Basquet** tiene grupos Masculino / Azul, Masculino / Amarillo, Masculino / Flex, Femenino / Formativa, Femenino / Superior y Mixto / Escuela con equipos e ítems de arancel.

Fuente de datos: `activities/data/estructura_actividades_club.py` + `estructura_actividades_seed.py`.

---

## Fuera de alcance (siguiente iteración)

- Frontend Vercel del club (repo aparte); contrato en `portal_socio_inscripcion.md`.
- Facturación de aranceles deportivos antes de que Secretaría asigne grupo/equipo (definir con operación).
- Portal autenticado del socio para cambiar inscripciones.

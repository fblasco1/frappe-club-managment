# Activities — jerarquía: actividad, grupo/tira y equipo

## Modelo

```
Actividad (ej. Basquet Masculino, Zumba, Ritmos Latinos)
├── usa_grupos = 0 → inscripción solo a la actividad (arancel en `Actividad.item`)
└── usa_grupos = 1 → el socio elige Grupo Actividad (tira/división) con arancel propio
    └── Equipo Actividad (categoría U11, etc.) — agrupación deportiva dentro del grupo
```

- **Grupo Actividad**: tira o división (Tira Azul, Primera División B). Cada uno tiene su **Item** de arancel mensual.
- **Equipo Actividad**: categoría dentro del grupo (U11, U13, …). Puede tener **Item** propio (aranceles básquet ICDPE).
- **Inscripcion Actividad**: `socio` + `actividad` + `grupo_actividad` (obligatorio si `usa_grupos`) + `equipo_actividad` (opcional).

**Zumba** y **Ritmos Latinos** son actividades distintas (`usa_grupos = 0` por defecto).

Aranceles básquet: ver `specs/basquet_aranceles_icdpe.md` (sin packs CLASES).

## Scenario: actividad con grupos exige tira al inscribir

Given `Actividad` «Basquet Masculino» con `usa_grupos = 1`
And `Grupo Actividad` «Tira Azul» hijo de esa actividad
And `Equipo Actividad` «Categoria U11» hijo de «Tira Azul»
When se inscribe un socio con actividad, grupo y equipo
Then existe `Inscripcion Actividad` activa con esos tres vínculos
And el resumen en `Socio.actividad` incluye «Basquet Masculino (Tira Azul — Categoria U11)».

## Scenario: actividad sin grupos (Zumba)

Given `Actividad` «Zumba» con `usa_grupos = 0`
When se inscribe un socio solo con `actividad = Zumba`
Then la inscripción no requiere grupo ni equipo
And el arancel se resuelve desde `Actividad.item`.

## Scenario: arancel por grupo

Given «Tira Azul» con `item` = Item arancel A
And «Tira Amarilla» con `item` = Item arancel B
When se resuelve el ítem de cobro para una inscripción a Tira Azul
Then devuelve Item arancel A (no el de la actividad padre si el grupo tiene ítem).

## Scenario: catálogo ICDPE incluye Zumba y Ritmos Latinos

Given el patch de sincronización ICDPE
Then existen 14 actividades habilitadas incluyendo **Basquet Escuelita** (mixta), **Zumba** y **Ritmos Latinos** como filas separadas.

## Scenario: seed operativo del club

Given el patch `seed_estructura_actividades_completa`
Then las 14 actividades ICDPE están habilitadas
And **Basquet Masculino**, **Basquet Escuelita**, **Basquet Femenino**, **Voley Femenino** y **Futbol** tienen `usa_grupos = 1`
And cada tira del básquet masculino (Tira Azul, Tira Amarilla, Tira Flex) tiene equipos con ítem de arancel
And vóley y fútbol tienen sus divisiones seed (Primera, Reserva, Juveniles, etc.) con las mismas categorías de equipo.

Fuente de datos: `activities/data/estructura_actividades_club.py` + `estructura_actividades_seed.py`.

## Fuera de alcance (siguiente iteración)

- UI post-pago en cascada (actividad → tira → equipo) completa en portal.
- Facturación automática por ítem de grupo.
- Items ERPNext por tira (códigos documentados; se enlazan cuando existan en el sitio).

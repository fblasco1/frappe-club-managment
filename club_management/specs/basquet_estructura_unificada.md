# Spec: Básquet — actividad única con grupos género / tira

Unifica **Basquet Masculino**, **Basquet Femenino** y **Basquet Escuelita** en una sola
actividad **Basquet**, con grupos que expresan género/modalidad y tira, y equipos por
categoría de edad.

**Relacionado:** `activities_jerarquia.md`, `basquet_aranceles_icdpe.md`,
`vinculacion_basquet_roster.md`, `import_socios_actividades_padron.md`

**Estado:** seed + migración inscripciones implementados (2026-07-05); deploy prod pendiente.

---

## Modelo objetivo

```
Actividad: Basquet (usa_grupos = 1)
├── Masculino / Azul
│   └── equipos: U9, U11, U13, U15, U17, U21
├── Masculino / Amarillo
│   └── equipos: U9, U11, U13, U15, U17, U21
├── Masculino / Flex
│   └── equipos: U15, U19, Superior C
├── Femenino / Formativa
│   └── equipos: U9, U11, U13, U15, U17
├── Femenino / Superior
│   └── equipos: Superior Fem
└── Mixto / Escuela
    └── equipos: U7 / U9, U11 / U13
```

Los **ítems de arancel** por equipo se mantienen según `basquet_aranceles_icdpe.md`
(resolución Equipo → Grupo → Actividad).

---

## Scenario: actividad única Basquet

Given el patch de estructura unificada aplicado
Then existe una sola `Actividad` habilitada titulada **Basquet** con `usa_grupos = 1`
And **no** se usan para inscripciones nuevas las actividades legacy
`Basquet Masculino`, `Basquet Femenino`, `Basquet Escuelita` (deshabilitadas tras migración).

---

## Scenario: grupos masculinos

Given la actividad **Basquet**
Then existen los grupos **Masculino / Azul**, **Masculino / Amarillo** y **Masculino / Flex**
And cada uno tiene los equipos listados en el modelo objetivo
And los aranceles por equipo coinciden con la matriz ICDPE vigente (minibásquet, formativas azul/amarilla/flex).

---

## Scenario: femenino formativa y superior

Given la actividad **Basquet**
Then existe el grupo **Femenino / Formativa** con equipos U9, U11, U13, U15, U17
And existe el grupo **Femenino / Superior** con un único equipo **Superior Fem**
And las inscripciones formativas usan el ítem de escuelita/formativa según `basquet_aranceles_icdpe.md`
And las inscripciones a Superior Fem usan `ICDPE-BASQUET-FEMENINO-SUP`.

---

## Scenario: escuelita mixta

Given la actividad **Basquet**
Then existe el grupo **Mixto / Escuela** con equipos **U7 / U9** y **U11 / U13**
And el arancel se resuelve con `ICDPE-BASQUET-ESCUELITA`.

---

## Scenario: migración desde estructura legacy

Given inscripciones activas bajo actividades legacy
When corre la migración de estructura unificada
Then se reasignan según la tabla:

| Legacy actividad | Legacy grupo | Legacy equipo | Nuevo grupo | Nuevo equipo |
|------------------|--------------|---------------|-------------|--------------|
| Basquet Masculino | Tira Azul | * | Masculino / Azul | * |
| Basquet Masculino | Tira Amarilla | * | Masculino / Amarillo | * |
| Basquet Masculino | Tira Flex | * | Masculino / Flex | * |
| Basquet Femenino | Femenino | U9…U17 | Femenino / Formativa | * |
| Basquet Femenino | Femenino | Superior Fem | Femenino / Superior | Superior Fem |
| Basquet Escuelita | Mixta | * | Mixto / Escuela | * |

And todas quedan con `actividad = Basquet`
And no se pierden inscripciones activas salvo filas huérfanas registradas en log.

---

## Scenario: roster Excel categoría + equipo

Given fila roster con `Equipo = Femenino` y categoría U7…U17
When se resuelve la selección
Then `actividad = Basquet`, `grupo = Femenino / Formativa`, `equipo = U{n}` (U7 → U9).

Given fila roster con `Equipo = Femenino` y categoría MAYOR
When se resuelve la selección
Then `actividad = Basquet`, `grupo = Femenino / Superior`, `equipo = Superior Fem`.

Given fila roster con `Equipo = Azul|Amarillo|Flex`
When se resuelve la selección
Then `actividad = Basquet` y `grupo = Masculino / {Azul|Amarillo|Flex}` con equipo según edad.

Given fila roster con `Equipo = Escuelita`
When se resuelve la selección
Then `actividad = Basquet`, `grupo = Mixto / Escuela`, equipo U7/U9 o U11/U13 según categoría.

---

## Fuera de alcance (decidir en implementación)

- Consolidación de Cost Centers ERPNext (3 CC básquet → 1 CC «Deportes - Basquet»).
- UI portal socio (cascada actividad → grupo → equipo).
- Borrado físico de DocTypes legacy; solo deshabilitar actividades/grupos viejos.

---

## Orden de implementación sugerido

1. Actualizar `estructura_actividades_club.py` + tests seed.
2. Patch migración inscripciones + deshabilitar actividades legacy.
3. Actualizar `padron_actividades_link.py`, `basquet_roster_link.py`, catálogo ICDPE.
4. Verificar dashboard «Inscripciones por deporte / actividad» (una barra Basquet).

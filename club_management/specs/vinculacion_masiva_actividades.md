# Spec: Vinculación masiva de socios a actividades

Alta masiva de `Inscripcion Actividad` desde CSV/Excel con jerarquía
Actividad → Grupo Actividad → Equipo Actividad, sin duplicar vigentes.

**Relacionado:** `inscripcion_gestion_desk.md`, `activities_jerarquia.md`,
`import_socios_actividades_padron.md`

Ejecución:

```text
bench --site dev.localhost execute club_management.scripts.bulk_activity_enrollment.run \
  --kwargs '{"csv_path": "/ruta/inscripciones.csv", "dry_run": true}'
```

---

## Input

| Columna | Descripción |
|---------|-------------|
| `nro_socio` (`numero_socio`) **o** `dni` | Socio existente |
| `actividad` | Name o título de `Actividad` |
| `grupo_actividad` (`grupo`) | Name o título de `Grupo Actividad` (si la actividad usa grupos) |
| `equipo_actividad` (`equipo`) | Opcional: name o título de `Equipo Actividad` |
| `fecha_desde` (`fecha_inscripcion`) | Fecha de alta; default hoy |

---

## Scenario: dry-run no persiste

Given un CSV con socio Activo y jerarquía existente
When `dry_run=True`
Then no se crea `Inscripcion Actividad`
And el reporte marca la fila como simulada.

---

## Scenario: socio inexistente o no Activo

Given `nro_socio`/`dni` desconocido
When se procesa
Then error `socio_no_encontrado`.

Given socio en estado distinto de `Activo`
When se procesa
Then error `socio_no_activo`.

---

## Scenario: jerarquía inválida

Given actividad inexistente o deshabilitada
Then error `actividad_no_encontrada`.

Given la actividad usa grupos y el grupo no existe / no pertenece a la actividad
Then error `grupo_no_encontrado`.

Given equipo indicado que no pertenece al grupo o está deshabilitado
Then error `equipo_no_encontrado`.

And **no** se crean nodos de catálogo “por si acaso”.

---

## Scenario: no duplicar inscripción vigente

Given ya existe `Inscripcion Actividad` Activa para la misma combinación socio + actividad + grupo (+ equipo)
When se procesa
Then se omite como `ya_inscrito`
And no se inserta otra fila.

---

## Scenario: alta con arancel y roster

Given socio Activo y jerarquía válida, sin inscripción vigente equivalente
When `dry_run=False`
Then se crea `Inscripcion Actividad` Activa con `fecha_inscripcion = fecha_desde`
And se asigna el arancel vigente (ítem equipo → grupo → actividad) vía `enroll_socio_arancel_inscripcion`
And si hay `equipo_actividad`, el socio aparece en el roster del equipo
And el resumen `Socio.actividad` se sincroniza.

---

## Scenario: reporte

Given una corrida
When termina
Then el resultado incluye altas, omitidas (duplicados) y errores de validación
And se puede persistir JSON en `log_path`.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Script | `scripts/bulk_activity_enrollment.py` |
| Tests | `tests/test_bulk_activity_enrollment.py` |

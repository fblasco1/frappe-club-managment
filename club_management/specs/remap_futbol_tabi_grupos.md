# Spec: Remap grupos Fútbol TABI legacy → TABI A / TABI B

Normaliza inscripciones de **Futbol** que quedaron en grupos legacy:

| Grupo origen | Grupo destino |
|--------------|---------------|
| `Futbol / TABI-1` | `Futbol / TABI A` |
| `Futbol / TABI-2` | `Futbol / TABI B` |
| `Futbol / Escuelita` | `Futbol / TABI B` |

**Nota de negocio:** la escuelita de fútbol opera como TABI B (ver `futbol_aranceles_icdpe.GRUPO_FUTBOL_ESCUELITA`).

**Relacionado:** `reporte_inscriptos_actividad.md`, `arancel_item_naming.md`

---

## Scenario: dry-run lista remapeos

Given inscripciones (Activa o Baja) en grupos origen
When corre `run(apply=False)`
Then el reporte lista cada fila con `grupo_origen`, `grupo_destino`, `socio`, `estado`
And no modifica la base.

---

## Scenario: apply remapea sin conflicto

Given una inscripción en `Futbol / TABI-1` sin otra Activa del mismo socio en `Futbol / TABI A`
When corre `run(apply=True, confirm=…)`
Then `grupo_actividad` pasa a `Futbol / TABI A`
And si `equipo_actividad` no pertenece al grupo destino, se limpia
And se sincroniza el resumen `Socio.actividad`.

---

## Scenario: conflicto Activa en destino

Given el socio ya tiene inscripción **Activa** en el grupo destino
And otra **Activa** en el grupo origen
When corre `run`
Then esa fila figura en `conflictos` y **no** se remapea (evita duplicar Activa).

---

## Scenario: Baja se remapea siempre

Given inscripción `estado = Baja` en grupo origen
When corre apply
Then se remapea al destino aunque exista Activa en destino (no viola unicidad Activa).

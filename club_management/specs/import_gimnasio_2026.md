# Spec: Importación del listado del Gimnasio de Musculación 2026

Carga inicial de las personas que asisten al **Gimnasio Fitness** a partir de
`GIMNASIO DE MUSCULACION 2026 - Resumen Socios.csv`
(columnas `Nombre y Apellido`, `Condición`, `Profesor / Turno`, `Tipo de Membresía`).

Script: `club_management.members.ops.import_gimnasio_2026.run` (dry-run por defecto).

**Relacionado:** `gimnasio_cobro_socios_no_socios.md`

---

## Reglas

- La columna `Profesor / Turno` no se carga.
- Los nombres se comparan normalizados: sin tildes, en mayúsculas, espacios simples.
- El CSV escribe «NOMBRE APELLIDO», salvo algunas filas invertidas. Para separar nombre y
  apellido se usa la frecuencia de cada palabra como nombre o como apellido en el padrón.
- Filas `No socio` cuyo nombre es casi igual (similitud ≥ 0,85 sobre las palabras ordenadas) se
  consideran la misma persona. Si alguna de sus filas es `MES`, la persona es mensual.

## Scenario: socio con coincidencia exacta

Given una fila `Socio` / `MES` cuyo nombre coincide con un único `Socio` existente
When se aplica el import
Then el socio queda inscripto en Gimnasio Fitness, grupo `Socio`
And si ya tenía esa inscripción activa no se duplica.

## Scenario: socio con coincidencia probable

Given una fila `Socio` sin coincidencia exacta pero con un candidato parecido
When se corre el import sin confirmar ese candidato
Then la fila figura como `probable` en el reporte y no se inscribe
When se corre con `confirmados = {"<nombre csv>": "<socio>"}`
Then se inscribe al socio confirmado.

## Scenario: socio no encontrado

Given una fila `Socio` sin candidatos
Then figura como `no_encontrado` en el reporte y no se crea nada.

## Scenario: socio dado de baja

Given una fila `Socio` cuyo socio está en `Baja`
Then figura en el reporte para revisar y no se inscribe.

## Scenario: no socio mensual nuevo

Given una fila `No socio` / `MES` sin coincidencia en el padrón
When se aplica el import
Then se crea un practicante `No Socio` (serie `NS-`) con DNI provisorio `GYM-PEND-###`
  y datos de contacto de marcador (`@local.invalid`)
And queda inscripto en Gimnasio Fitness, grupo `No Socio`.

## Scenario: no socio por hora o quincena

Given una persona `No socio` cuyas filas son solo `HORA` o `QUINCENA`
When se aplica el import
Then se crea el practicante `No Socio` sin inscripción mensual y sin generar cargos.

## Scenario: no socio que ya es socio activo

Given una fila `No socio` que coincide exacto con un `Socio` activo que no es `Menor`
Then se lo trata como socio: se inscribe en el grupo `Socio` y no se crea un No Socio.
Given la coincidencia está en `Baja` o es `Menor`
Then figura en el reporte para revisar y no se carga.

## Scenario: reimportación idempotente

Given el import ya aplicado
When se vuelve a aplicar
Then no se crean practicantes nuevos (se reconocen por nombre entre los `No Socio`)
And no se duplican inscripciones ni DNIs provisorios.

## Scenario: nombre incompleto

Given una fila con una sola palabra en el nombre
Then figura como `nombre_incompleto` en el reporte y no se crea.

## Scenario: apply protegido

Given `apply = 1`
When `confirm` no es `local-dev` (local) o `APPLY_PROD` (producción)
Then se rechaza (criterio de `scripts/bulk_io.ensure_bulk_apply_allowed`).

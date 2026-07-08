# Spec: vinculación roster básquet por DNI



Vincula socios existentes del padrón con su **categoría** y **equipo/tira** de básquet

mediante `Inscripcion Actividad`, a partir del Excel operativo de jugadores.



**Relacionado:** `activities_jerarquia.md`, `basquet_aranceles_icdpe.md`, `basquet_estructura_unificada.md`



---



## Scenario: mapeo categoría + equipo 2026 a jerarquía ICDPE



Given una fila con `Categoria 2026` (U7…U21, MAYOR) y `Equipo 2026` (Azul, Amarillo, Flex, Femenino, Escuelita)

When se resuelve la selección de inscripción

Then se obtiene `actividad = Basquet`, `grupo` y `equipo` coherentes con la estructura unificada

And Azul/Amarillo masculino apuntan a `Basquet` / `Masculino / Azul|Amarillo` / `U{n}`

And Flex masculino usa `Masculino / Flex` con equipo según edad (U15, U19 o Superior C)

And Femenino apunta a `Basquet` / `Femenino / Formativa` / `U{n}` (o `Femenino / Superior` / `Superior Fem` si MAYOR o U21)

And Escuelita apunta a `Basquet` / `Mixto / Escuela` / `U7 / U9` o `U11 / U13`.



---



## Scenario: vincular socio existente por DNI



Given un `Socio` activo con `dni` normalizado (solo dígitos)

And una fila del roster con el mismo DNI

When Secretaría ejecuta el import con `dry_run=False`

Then se da de baja cualquier inscripción activa previa de actividades `Basquet%`

And se crea una `Inscripcion Actividad` activa con grupo y equipo resueltos

And `Socio.actividad` refleja el resumen actualizado

And la suscripción ERPNext incorpora el arancel del equipo si corresponde.



---



## Scenario: DNI ausente en fila pero nombre en dataNIF



Given una fila del roster sin DNI numérico

And el nombre coincide con la hoja `dataNIF` del mismo Excel

When se procesa la fila

Then se resuelve el DNI desde `dataNIF` antes de buscar al socio.



---



## Scenario: socio no encontrado



Given un DNI del roster sin `Socio` correspondiente

When se ejecuta el import

Then la fila se registra en `errores` sin abortar el lote

And `dry_run` la cuenta en `socios_no_encontrados`.



---



## Scenario: simulación dry_run



Given el archivo Excel o CSV del roster

When se ejecuta con `dry_run=True`

Then no se crean ni modifican inscripciones

And el resumen indica cuántos socios se vincularían, omitirían o fallarían.

---

## Scenario: import CSV Jugadorxs sin inscripción previa

Given el CSV `JUGADORES BASQUET - PEDRO ECHAGUE - Jugadorxs.csv`

When se ejecuta `import_roster_jugadores` con `dry_run=False`

Then cada fila busca al socio por **DNI** o **nombre completo**

And si existe y no tiene inscripción activa de básquet, se crea la inscripción

And no se da de baja una inscripción de básquet ya existente.

---

## Scenario: logs de import roster Jugadorxs

When finaliza `import_roster_jugadores`

Then genera tres CSV de salida:

1. JUGADORES QUE NO ESTAN EN EL PADRON y NO TIENEN DNI EN EL CSV
2. JUGADORES QUE NO ESTAN EN EL PADRON y TIENEN DNI EN EL CSV
3. JUGADORES QUE YA TENIAN INSCRIPCION CARGADA


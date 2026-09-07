# Spec: Dashboard ocupación de espacios (planilla)

Vista Desk tipo planilla Excel: columnas = espacios habilitados, filas = franjas
de 30 minutos desde **08:00** hasta **04:00** del día siguiente.

**Roles:** Coordinacion, Secretaria, Tesoreria, System Manager (lectura).

**Relacionado:** `spaces_catalogo_ocupacion.md`, `spaces_alquiler_externo.md`

---

## Scenario: payload del día

Given existen espacios habilitados y ocupación (grilla semanal y/o reservas Confirmada)
When un usuario autorizado consulta el dashboard para la fecha `2026-09-05` (sábado)
Then recibe `dia_semana`, lista de `slots` 08:00…03:30, lista de `espacios` y `bloques`
And cada bloque tiene `espacio`, `titulo`, `inicio_min` / `fin_min` relativos a la ventana 08:00→04:00 (+24h)
And los bloques de la madrugada (00:00–04:00) corresponden al día calendario siguiente.

---

## Scenario: varios bloques en el mismo espacio y franja

Given dos horarios solapados en la misma cancha el mismo día
When se consulta el dashboard
Then ambos bloques aparecen en la columna de ese espacio (pueden solaparse visualmente).

---

## Scenario: color por tipo

Given bloques de `Preparacion Fisica`, `Entrenamiento`, `Alquiler externo`, `Alquiler socio`, `Evento club` y `Bloqueo`
When se renderiza el payload
Then cada bloque trae un `color` estable para distinguir categorías.

---

## Scenario: orden fijo de columnas (espacios)

Given espacios habilitados del catálogo ICDPE
When se consulta el dashboard
Then las columnas siguen el orden operativo:
  Cancha 1, Cancha 2, Cancha 3, Gimnasio Bajo Tribuna, SALON PB, SUM PB,
  SUBSUELO, SALA ALBAMONTE, PARRILLA/TERRAZA, LA CASONA
And los encabezados usan `titulo_planilla` abreviado cuando corresponde.

---

## Scenario: acceso restringido

Given un usuario sin roles de Spaces
When llama al endpoint del dashboard
Then recibe PermissionError.

---

## Scenario: página Desk

Given Coordinacion en el workspace Espacios
When abre **Ocupación de espacios**
Then navega a `/desk/ocupacion-espacios` y ve la grilla del día seleccionado.

---

## Scenario: navegación lateral de Espacios

Given Coordinacion está en el workspace `Espacios` o en `/desk/ocupacion-espacios`
When se muestra la barra lateral de Desk
Then ve un acceso a `Espacios` como dashboard principal
And ve un acceso a `Ocupación de espacios`
And ambos accesos navegan dentro de Desk.

---

## Scenario: clic en superposición muestra selector

Given dos o más bloques solapados en el mismo espacio (p. ej. entrenamiento + partido fixture)
When Coordinación hace clic en cualquiera de los bloques del solape
Then ve un diálogo con la lista de todos los eventos superpuestos (título, horario, tipo)
And al confirmar uno ejecuta la acción de edición de ese bloque (no solo el visible encima).

---

## Scenario: suspender entrenamiento o evento del día

Given un bloque de grilla o de reserva en la planilla
When Coordinación elige **Suspender solo este día**
Then el bloque deja de mostrarse ese día sin modificar la grilla semanal ni cancelar la reserva base.

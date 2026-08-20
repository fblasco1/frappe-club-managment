# Spec: Panel catálogo en workspace Gestión de Actividades

Panel Desk para rol `Secretaria`: listado jerárquico de actividades,
grupos/tiras y equipos/categorías, con creación rápida y aranceles editables inline.

---

## Scenario: catálogo completo ordenado

Given existen actividades habilitadas con grupos y equipos seed
When Secretaria abre el workspace **Gestión de Actividades** o llama `get_catalog`
Then devuelve todas las actividades con `habilitada = 1`
And están ordenadas por `orden`, luego `titulo`
And cada actividad incluye sus `Grupo Actividad` hijos
And cada grupo incluye sus `Equipo Actividad` hijos.

---

## Scenario: crear actividad desde el panel

Given el workspace **Gestión de Actividades** abierto
When Secretaria llama `create_actividad` con `titulo` (y opcionalmente `usa_grupos`)
Then se crea una `Actividad` habilitada con ese título
And aparece en el catálogo al recargar.

---

## Scenario: crear grupo bajo actividad

Given una `Actividad` existente
When Secretaria llama `create_grupo` con `actividad` y `titulo`
Then se crea un `Grupo Actividad` vinculado a esa actividad
And queda `habilitada = 1`.

---

## Scenario: crear equipo bajo grupo

Given un `Grupo Actividad` existente
When Secretaria llama `create_equipo` con `grupo_actividad` y `titulo`
Then se crea un `Equipo Actividad` vinculado a ese grupo
And queda `habilitada = 1`.

---

## Scenario: arancel inline en actividad o grupo

Given una `Actividad` o `Grupo Actividad` existente
When Secretaria llama `set_arancel` con `doctype`, `name`, `item` y `rate`
Then se actualiza el campo `item` del documento
And se actualiza `Item.standard_rate` del ítem indicado
And la respuesta incluye el `rate` resuelto.

---

## Scenario: acceso restringido al panel de actividades

Given un usuario sin rol `Secretaria` ni `System Manager`
When intenta llamar a cualquier endpoint del panel de actividades
Then recibe error de permisos.

---

## Scenario: navegación compacta con muchas tiras y equipos

Given una actividad con muchos `Grupo Actividad` y `Equipo Actividad` (p. ej. seed básquet)
When Secretaria abre el workspace **Gestión de Actividades**
Then cada actividad aparece en **acordeón colapsado** por defecto con resumen de tiras/equipos o arancel
And al expandir una actividad se muestran sus acciones, arancel (si aplica) y grupos en acordeón anidado
And los grupos/tiras aparecen colapsados por defecto con resumen de arancel y cantidad de equipos
And puede filtrar actividades, tiras o equipos con el campo de búsqueda
And la actividad y el grupo expandido se recuerdan en la sesión del navegador.

---

## Scenario: arancel de grupo persiste tarifa e ítem

Given un `Grupo Actividad` con ítem de arancel asignado
When Secretaria actualiza solo la tarifa desde el panel
Then persiste en `Item.standard_rate` del ítem vinculado
And el catálogo refleja la tarifa al recargar.

---

## Scenario: crear ítem ERP desde panel de arancel

Given Secretaria crea una actividad o grupo sin ítem de arancel previo
When abre el selector de ítem y elige **Crear ítem**
Then puede crear un `Item` de servicio ICDPE con código, nombre y tarifa
And el ítem queda aplicado al nodo (actividad o grupo) con esa tarifa.

---

## Scenario: acceso administrativo jerárquico Actividad > Grupo > Equipo

Given Secretaria o System Manager en el workspace **Gestión de Actividades**
When usa la barra **Administración** del panel
Then puede abrir la lista Desk de **Actividad**, **Grupo Actividad** y **Equipo Actividad**
And si hay una actividad seleccionada, la lista de grupos se abre filtrada por esa actividad
And si hay un grupo expandido, la lista de equipos se abre filtrada por ese grupo

---

## Scenario: arancel efectivo visible en fila de equipo del catálogo

Given un `Equipo Actividad` sin `item` propio
And su `Grupo Actividad` (o `Actividad` si el grupo tampoco tiene) con ítem y tarifa
When Secretaria carga `get_catalog`
Then cada fila de equipo incluye el arancel **efectivo** de cobro (`item`, `item_name`, `rate`, `origen`)
And `origen` es `Equipo`, `Grupo`, `Actividad` o `Sin arancel` según la cascada equipo → grupo → actividad
And el catálogo Desk muestra ese resumen junto al título del equipo
And en el formulario Desk de una **Actividad** aparece el dashboard con sus **Grupos / tiras**
And en el formulario Desk de un **Grupo Actividad** aparece el dashboard con sus **Equipos / categorías**.

---

## Scenario: arancel inline editable en equipo / categoría

Given un `Equipo Actividad` en el catálogo del panel
When Secretaría asigna ítem y tarifa con `set_arancel` (`doctype` = `Equipo Actividad`)
Then el campo `item` del equipo se actualiza
And `Item.standard_rate` y `Item Price` de venta reflejan la tarifa
And el catálogo muestra inputs de **Ítem arancel** y **Tarifa** en la fila del equipo (igual que actividad/grupo)
And un resumen de arancel efectivo (origen Equipo / Grupo / Actividad) permanece visible como texto plano, **sin** etiquetas HTML literales.

# Spec: Catálogo de actividades — navegación estable y alta guiada

Complementa `gestion_actividades_panel.md` y `gestion_actividades_edicion_panel.md`.

**Problemas reportados por Secretaría (2026-10-07):**

1. Al expandir una actividad del listado después de scrollear, la vista vuelve arriba y hay que volver a buscarla.
2. Crear una actividad es engorroso: se reparte en varios pasos sueltos y expone términos de ERPNext
   («Ítem», «Producto», «Grupo de productos») que Secretaría no asocia con la cuota de la actividad.

**Vocabulario en UI:** el `Item` de ERPNext se presenta como **«Arancel (cuota mensual)»**.
Cuando haga falta, se aclara que «en contabilidad figura como *Producto*». El `Grupo Actividad`
se presenta como **«Grupo / tira de la actividad»** y nunca se mezcla con «Grupo de productos» (`Item Group`),
que se asigna automáticamente.

---

## Scenario: expandir actividad mantiene la posición en pantalla

Given el catálogo con muchas actividades y Secretaría scrolleó hasta una actividad de la mitad
When hace clic en esa actividad para expandirla (o colapsarla)
Then la actividad clickeada queda en el mismo lugar de la pantalla
And no se redibuja el listado completo
And lo mismo vale al expandir/colapsar un grupo / tira y al guardar una tarifa.

---

## Scenario: buscar en el catálogo no pierde el foco

Given Secretaría escribe en el buscador del catálogo
When el listado se filtra
Then el cursor sigue en el buscador y puede seguir escribiendo.

---

## Scenario: alta guiada de actividad con cuota única

Given Secretaría abre **Nueva actividad**
When indica nombre «Natación», elige «Una sola cuota para todos» y monto 15000
Then se crea la `Actividad` «Natación» habilitada con `usa_grupos = 0`
And se crea automáticamente un arancel (`Item` de servicio, grupo de ingresos por actividades) llamado «Cuota mensual Natación»
And el arancel queda vinculado a la actividad con tarifa 15000.

---

## Scenario: alta guiada de actividad con grupos / tiras

Given Secretaría abre **Nueva actividad**
When indica nombre «Hockey», elige «Tiene grupos / tiras con cuotas distintas» y carga
  «Formativas» con 9000 y «Primera» con 12000
Then se crea la `Actividad` «Hockey» con `usa_grupos = 1`
And se crean los `Grupo Actividad` «Hockey / Formativas» y «Hockey / Primera»
And cada grupo tiene su propio arancel «Cuota mensual Hockey — Formativas» (9000) y «Cuota mensual Hockey — Primera» (12000).

---

## Scenario: alta guiada reutilizando un arancel existente

Given existe un arancel (`Item` ICDPE) «ARANCEL-X»
When Secretaría crea la actividad eligiendo «Usar un arancel que ya existe» y selecciona «ARANCEL-X»
Then la actividad queda vinculada a «ARANCEL-X» y no se crea ningún `Item` nuevo.

---

## Scenario: alta guiada sin arancel

Given Secretaría no conoce todavía el monto
When crea la actividad eligiendo «Definir la cuota más tarde»
Then se crea la actividad sin arancel
And el catálogo la muestra con «Sin arancel».

---

## Scenario: alta guiada es atómica

Given un error al crear alguno de los grupos (p. ej. título vacío)
When se envía el alta guiada
Then no queda creada la actividad ni ningún arancel a medias.

---

## Scenario: código de arancel automático y único

Given Secretaría crea un arancel sin indicar código
When el nombre es «Cuota mensual Natación»
Then el código generado es `ARANCEL-CUOTA-MENSUAL-NATACION` (mayúsculas, sin acentos)
And si ya existe, se agrega sufijo `-2`, `-3`, … hasta que sea único.

---

## Scenario: nuevo grupo / tira con cuota en un solo paso

Given una actividad existente
When Secretaría agrega un grupo / tira indicando un monto mayor a 0
Then se crea el grupo con su arancel «Cuota mensual {actividad} — {grupo}» y esa tarifa
And si el monto queda vacío, el grupo se crea sin arancel propio.

---

## Scenario: cada diálogo indica qué se está creando y dónde

Given cualquier diálogo de alta del catálogo (actividad, grupo / tira, equipo / categoría, arancel)
When se abre
Then el título dice qué se crea («Nueva actividad», «Nuevo grupo / tira en Básquet», …)
And incluye una explicación breve en lenguaje de Secretaría
And el selector de arancel existente **no** ofrece «Crear nuevo Producto» de ERPNext.

---

## Scenario: permisos del alta guiada

Given un usuario sin rol `Secretaria` ni `System Manager`
When llama al endpoint de alta guiada
Then recibe error de permisos.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Servicio | `activities/services/gestion_actividades_panel.py` |
| API | `activities/api/gestion_actividades_workspace.py` |
| UI | `public/js/gestion_actividades_workspace_panel.js` |
| Tests | `activities/tests/test_gestion_actividades_panel.py` |

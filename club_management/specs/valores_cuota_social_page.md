# Spec: Página Valores de Cuota Social (Secretaría)

Montos de cuota social por categoría de socio, editables desde Desk sin abrir el Single `Club Settings`.

---

## Scenario: acceso desde sidebar Secretaría

Given un usuario con rol `Secretaria`
When abre el workspace **Secretaría** y observa la sidebar izquierda
Then ve el enlace **Valores de Cuota Social**
When hace clic en ese enlace
Then navega a la página Desk `valores-cuota-social`
And ve el título **Valores de Cuota Social**.

---

## Scenario: listado y edición de montos

Given `Club Settings` con filas en `cuotas_categoria`
When Secretaria abre la página **Valores de Cuota Social**
Then ve una tabla con cada categoría operativa, su monto mensual y el ítem ERPNext asociado
When modifica montos válidos (> 0) y guarda
Then se persisten en `Club Settings`
And se sincronizan precios ERPNext vía `sync_cuotas_sociales_erpnext`.

---

## Scenario: panel dashboard sin cuotas inline

Given Secretaria en el workspace **Secretaría** (dashboard Gestión de Socios)
When carga el panel operativo
Then **no** ve la sección colapsable de cuotas sociales en el dashboard
And las cuotas solo se gestionan desde la página dedicada.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When intenta llamar `get_cuotas_sociales` o `save_cuotas_sociales`
Then recibe error de permisos.

---

## Scenario: landing pública refleja los montos de gestión

Given `Club Settings.cuotas_categoria` con montos por categoría
And `Club Settings.cuotas_vigente_desde` con una fecha
When un visitante (Guest) llama `get_valores_cuota` (`allow_guest=True`)
Then recibe `vigente_desde` y una lista `categorias` con `categoria`, `valor` y `condicion`
And **no** recibe ítems ERPNext, nombres internos ni otros datos de `Club Settings`
And el `valor` de cada categoría coincide con el monto guardado en Desk.

When Secretaría guarda un monto distinto en **Valores de Cuota Social**
And el visitante vuelve a llamar `get_valores_cuota`
Then el `valor` público de esa categoría es el nuevo monto.

---

## Scenario: Guest no muta cuotas

Given un usuario Guest
When intenta `save_cuotas_sociales`
Then recibe error de permisos
And los montos en `Club Settings` no cambian.

---

## Notas

- Categorías: `Activo`, `Menor`, `2° Hermano`, `3° Hermano`, `Adherente`, `Jubilado`.
- La página comparte la navegación superior del club (pestañas Gestión de Socios / Actividades).
- La web pública `/socios/cuota` (landing) consume `get_valores_cuota`. El texto de **condición** es copy fijo por categoría (no se edita en Desk en esta iteración).
- El endpoint público no expone PII. No listar categorías con monto ≤ 0.

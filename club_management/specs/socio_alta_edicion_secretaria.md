# Spec: Alta y edición de Socio por Secretaría

Secretaría debe poder **crear** y **editar** socios desde Desk sin depender exclusivamente del flujo Solicitud de Asociación.

**Relacionado:** `socio_minimo.md`, `mvp_operacion_secretaria_sin_pagos.md`  
**Módulo:** `members/`  
**Fuera de alcance:** promoción Vitalicio automática (`socios_categoria_validacion.md`).

---

## Modelo

- El alta manual crea `Socio` + `Customer` ERPNext (si ERPNext instalado).
- `estado` inicial configurable: `Pendiente de Pago` (default) o `Activo` si Secretaría marca «Activar al guardar».
- `estado` sigue siendo read-only en formulario; transiciones especiales usan servicios existentes.
- DNI único; email puede repetirse (menor/tutor).

---

## Scenario: Secretaría crea socio adulto manualmente

Given un usuario con rol `Secretaria`
And no existe otro `Socio` con el mismo `dni`
When llama `crear_socio_desk` con datos personales obligatorios y `categoria = Activo`
Then se crea un documento `Socio` con `estado = Pendiente de Pago`
And se registra `fecha_alta` vacía hasta primera activación
And si ERPNext está disponible, se crea o vincula `Customer`
And se dispara `sync_suscripcion_cuota_al_validar_socio` equivalente (alta suscripción cuota social si aplica).

---

## Scenario: Secretaría crea socio y activa en el mismo paso

Given los mismos datos de alta
When `crear_socio_desk` incluye `activar_al_guardar = 1`
Then tras crear el socio se ejecuta `activar_socio_manual`
And `estado = Activo` y `fecha_alta` = hoy.

---

## Scenario: Secretaría edita datos personales de socio existente

Given un `Socio` existente en cualquier estado excepto `Baja`
When Secretaría guarda cambios en `nombre`, `apellido`, `telefono`, `domicilio`, `categoria`, adjuntos
Then los cambios persisten
And no se modifica `estado` ni `fecha_alta` sin servicio de transición.

---

## Scenario: advertencia de datos críticos incompletos al editar (sin bloquear)

Given un `Socio` existente abierto por Secretaría
And faltan datos críticos (contacto, domicilio, adjuntos o tutor si `categoria = Menor`)
When Secretaría guarda otros cambios en el formulario
Then el guardado **no** se bloquea por esos faltantes (ni modal «Campos Faltantes» del cliente)
And el cliente omite `check_mandatory` en edición Secretaría (parche global por rol, sin depender de `frm.save`)
And el servidor aplica `ignore_mandatory` en `Socio.before_save`
And el cliente muestra advertencia con la lista de campos críticos pendientes
And el formulario sigue mostrando el indicador de incompletitud al reabrir
And las invariantes duras se mantienen (DNI único, `estado` read-only, edad del tutor si está cargado).

---

## Scenario: bloqueo DNI duplicado en alta manual

Given ya existe `Socio` con `dni = 30123456`
When Secretaría intenta `crear_socio_desk` con el mismo DNI
Then recibe error de validación y no se crea el documento.

---

## Scenario: Secretaría asigna número de socio en alta manual

Given no existe un `Socio` con `name` = `"1500"` (ni `numero_socio` = 1500)
When Secretaría crea un socio desde **Alta guiada** o `crear_socio_desk` con `numero_socio = 1500`
Then el documento se persiste con `name` = `"1500"` y `numero_socio` = 1500
And el número queda inmutable en ediciones posteriores.

---

## Scenario: número de socio duplicado en alta manual

Given ya existe un `Socio` con `numero_socio` = 1500 (`name` = `"1500"`)
When Secretaría intenta crear otro socio con `numero_socio` = 1500
Then recibe `frappe.ValidationError` con mensaje claro (número ya asignado)
And no se crea el documento.

---

## Scenario: número de socio vacío en alta manual

Given Secretaría crea un socio sin indicar `numero_socio`
When se ejecuta el alta
Then el controller asigna `MAX(numero_socio) + 1` (misma regla que `socio_minimo.md`).

---

## Scenario: menor con tutor en alta manual

Given `categoria = Menor`
When `crear_socio_desk` sin `tipo_tutor` / `tutor`
Then recibe error de validación
When completa vínculo tutor (Socio o Tutor No Socio)
Then el socio se crea con esos vínculos
And `grupo_familiar` es opcional en operación interna (fase 2).

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When invoca `crear_socio_desk` o APIs de edición restringida
Then recibe `PermissionError`.

---

## Scenario: alta guiada sin solicitud digital (sprint operación Desk)

Given no hay flujo de solicitud pública activo en este sprint
When Secretaría usa **Alta guiada** desde workspace o formulario `Socio` nuevo
Then completa datos personales y domicilio en un asistente (sin adjuntos obligatorios)
And puede elegir destino: **Activar ahora** (default), **Pendiente de inscripción** u **Pendiente de pago**
And opcionalmente inscribir en una actividad en el mismo paso
And los adjuntos (`foto_perfil`, DNI, ficha médica) quedan **opcionales** en alta manual Desk
  (siguen obligatorios en solicitud pública cuando exista).

---

## Scenario: sugerencia de categoría por edad

Given `fecha_nacimiento` indica menor de 18 años
When Secretaría cambia la fecha en el asistente
Then se sugiere `categoria = Menor` y se muestran campos de tutor/grupo.

---

## UI Desk (criterios de aceptación)

Given el formulario `Socio` abierto por Secretaría
When el socio es nuevo (`__islocal`)
Then muestra **Alta guiada** como acción principal (asistente)
And oculta la sección de documentos adjuntos como obligatoria en pantalla
When el socio existe
Then los campos editables siguen las reglas del DocType (estado read-only).

Given workspace **Secretaría**
When Secretaría hace clic en **Nuevo socio**
Then abre el mismo asistente de alta guiada.

---

## Artefactos esperados

| Artefacto | Ubicación sugerida |
|-----------|-------------------|
| Servicio | `members/services/socio_alta_secretaria.py` |
| Datos críticos | `members/services/datos_criticos_socio.py` |
| API whitelist | `members/api/socio_operaciones_desk.py` |
| Client script | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_socio_alta_secretaria.py`, `members/tests/test_datos_criticos_socio.py` |

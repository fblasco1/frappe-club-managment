# MVP operación Secretaría sin integración de pagos

Operación manual en Desk para cerrar el ciclo socio activo, inscripciones y
cuenta corriente básica **sin** SIRO / Supervielle ni pago online.

---

## Scenario: Secretaría omite pago y habilita inscripción

Given un `Socio` con `estado = Pendiente de Pago` (tras validar solicitud)
And un usuario con rol `Secretaria`
When ejecuta la acción **Omitir pago (alta manual)**
Then `estado` pasa a `Pendiente de Inscripción`
And se registra auditoría (`ultimo_cambio_estado_*`, motivo).

---

## Scenario: Secretaría activa socio sin inscripciones

Given un `Socio` en `Pendiente de Pago` o `Pendiente de Inscripción`
When ejecuta **Activar socio**
Then `estado` = `Activo`
And `fecha_alta` se setea si estaba vacía
And no se exigen inscripciones activas.

---

## Scenario: Secretaría inscribe actividades desde Desk

Given un `Socio` en `Pendiente de Inscripción` o `Activo`
And selecciones `{actividad, grupo?, equipo?}` válidas
When llama a `inscribir_actividades_desk`
Then se crean `Inscripcion Actividad` activas (sin duplicar par socio+actividad+grupo)
And `Socio.actividad` se sincroniza
And si el socio estaba en `Pendiente de Inscripción`, pasa a `Activo`.

---

## Scenario: transiciones moroso / reactivar / baja

Given un `Socio` `Activo`
When Secretaría ejecuta **Marcar moroso**
Then `estado` = `Moroso`.

Given un `Socio` `Moroso`
When Secretaría ejecuta **Reactivar**
Then `estado` = `Activo`.

Given un `Socio` `Activo`, `Moroso` o `Suspendido`
When Secretaría ejecuta **Dar de baja** con motivo
Then `estado` = `Baja`.

---

## Scenario: acceso restringido a operaciones Desk

Given un usuario sin rol `Secretaria` ni `System Manager`
When invoca cualquier operación Desk de socio
Then recibe `PermissionError`.

---

## Scenario: generar cargo mensual manual

Given `Club Settings` con cuota social para la categoría del socio
And el socio tiene `Customer` ERPNext vinculado
And inscripciones activas con ítems de arancel (si aplica)
When Secretaría ejecuta **Generar cargo**
Then se crea una `Sales Invoice` submitted con líneas de cuota social, aranceles y cargos extra recurrentes vigentes (si `incluir_cargos_extra_en_deuda_mensual`)
And la factura referencia al `Socio` (campo custom)
And `Socio.saldo_deuda` refleja el saldo pendiente ERPNext.

---

## Scenario: registrar cobro manual

Given una `Sales Invoice` pendiente vinculada al socio
When Secretaría ejecuta **Registrar cobro**
Then se crea y submittea un `Payment Entry` por el saldo pendiente
And `Socio.saldo_deuda` se actualiza
And si el socio estaba `Moroso` y el saldo queda en 0, pasa a `Activo`.

## Scenario: botón Registrar cobro en Desk

Given un `Socio` con `saldo_deuda` > 0
And facturas pendientes vinculadas al socio
When Secretaría abre el formulario `Socio` en Desk
Then ve el botón **Registrar cobro** en el grupo Cobranza manual
And al confirmar se llama a `cobranza_desk.registrar_cobro` con la factura elegida.

---

## Scenario: navegación Desk con dos pestañas

Given un usuario con rol `Secretaria`
When inicia sesión en Desk
Then aterriza en el workspace `Secretaría` (Gestión de Socios)
And ve una barra superior con solo **Gestión de Socios** y **Gestión de Actividades**
And los informes no aparecen en esa barra superior
And al elegir **Gestión de Actividades** navega al workspace `Gestión de Actividades` en la misma pestaña
And el workspace `Inicio` no se muestra ni duplica botones de acceso.

---

## Scenario: sidebar del workspace Secretaría

Given Secretaría en Desk dentro del contexto de socios (workspace `Secretaría`, listado `Socio` o informes del club)
When observa la sidebar izquierda del workspace
Then ve **Secretaría** para volver al panel del workspace
And ve **Socio** para abrir el listado de socios
And ve **Valores de Cuota Social** para abrir la página de montos por categoría
And no ve `Grupo Familiar` ni `Solicitud Asociacion`
And ve una sección **Informes** con acceso a **Deuda por equipo** y **Pagos por equipo**.

---

## Scenario: cuotas sociales en página dedicada

Given `Club Settings` con filas en `cuotas_categoria`
When Secretaria abre la página **Valores de Cuota Social** desde la sidebar
Then ve categoría, monto e ítem por fila
When llama `save_cuotas_sociales` con montos válidos
Then se persisten en `Club Settings` sin abrir el formulario Single
And un usuario sin rol `Secretaria` recibe error de permisos.
And el dashboard del workspace **Secretaría** no incluye la tabla de cuotas inline.

---

## Fuera de alcance (iteración siguiente)

- Facturación batch masiva del mes.
- Integración SIRO / botón de pago real.
- Portal autenticado del socio para cambiar inscripciones.

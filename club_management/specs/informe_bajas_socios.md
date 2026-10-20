# Spec: Informe «Bajas de socios»

Secretaría necesita **listar socios dados de baja** en un rango de fechas, ver
qué actividad realizaban, y saber si quedaron con deuda pendiente.

**Relacionado:** `socio_alta_post_baja.md`, `deuda_socios.md`,
`informes_secretaria_menu.md`, `inscripcion_gestion_desk.md`  
**Módulo:** `members/`  
**Fuera de alcance:** histórico de bajas de un socio que ya volvió a `Activo`
(`fecha_baja` se limpia al dar de alta); bajas de una sola inscripción sin
baja del padrón.

---

## Modelo

- El informe lista socios con `estado = Baja` cuya **fecha de baja de
  negocio** (`Socio.fecha_baja`; si está vacía, `ultimo_cambio_estado_en`)
  cae en el rango **desde / hasta** (inclusive).
- Secretaría puede informar una fecha histórica al dar de baja (bajas del
  sistema viejo no migradas); esa fecha es la que usa el informe.
- Una fila por socio (no por inscripción).
- **Actividades:** títulos de `Inscripcion Actividad` del socio (activa o baja).
  El filtro de actividad incluye a quien **realizó o realiza** esa actividad.
- **Deuda pendiente:** saldo actual de facturas de venta enviadas con
  `outstanding_amount > 0`. Si ERPNext no está disponible, se usa
  `Socio.saldo_deuda`.
- Acceso: roles `Secretaria` y `System Manager`.

---

## Scenario: rango de fechas

Given un socio dado de baja el 15/03/2026
And otro dado de baja el 01/05/2026
And otro aún `Activo`
When Secretaría ejecuta **Bajas de socios** con Desde = 01/03/2026 y Hasta = 31/03/2026
Then solo aparece el socio de marzo
And cada fila muestra apellido, nombre y fecha de baja.

---

## Scenario: filtro por actividad

Given un socio en Baja que tenía inscripción en Básquet
And otro en Baja que solo practicaba Patín
When filtra por actividad Básquet
Then solo aparece quien realizaba Básquet
And la columna de actividades lista los títulos que tenía.

---

## Scenario: deuda pendiente

Given un socio en Baja con factura impaga
And otro en Baja sin saldo
When se ejecuta el informe
Then el primero muestra deuda pendiente = Sí y el monto
And el segundo muestra No y monto 0
When filtra «Con deuda»
Then solo aparece el primero.

---

## Scenario: rango inválido

Given el informe **Bajas de socios**
When falta desde o hasta, o hasta es anterior a desde
Then `ValidationError` con un mensaje claro.

---

## Scenario: acceso restringido

Given un usuario sin rol `Secretaria` ni `System Manager`
When ejecuta el informe
Then `PermissionError`.

---

## Scenario: menú Secretaría / Actividades

Given rol Secretaría o System Manager
When abre el menú de informes
Then ve **Bajas de socios** junto a Cobranza por fechas, Pagos por equipo y
Deuda de socios.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | `specs/informe_bajas_socios.md` |
| Servicio | `members/services/informe_bajas_socios.py` |
| Report | `members/report/bajas_de_socios/` |
| Menú | `CLUB_DESK_REPORTS`, sidebars Socios / Actividades |
| Tests | `members/tests/test_informe_bajas_socios.py` |

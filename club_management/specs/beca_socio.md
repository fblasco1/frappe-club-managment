# Spec: Beca al socio

Beneficio aplicado al **Socio**, renovable cada **6 meses**, con impacto en la
facturación mensual (`cobranza_periodica_mensual.md`).

---

## Scenario: beca total exime cuota y arancel

Given un `Socio` `Activo` con inscripción `Activa` y una `Beca Socio` vigente
  con `tipo_beca = Total`
When se ejecuta `generar_deuda_mensual_socio`
Then la `Sales Invoice` **no** incluye línea de cuota social ni de arancel
And el socio no acumula deuda por esos conceptos en ese período.

---

## Scenario: beca parcial solo arancel

Given una `Beca Socio` vigente con `tipo_beca = Parcial Exime Arancel`
When se genera la deuda mensual
Then la factura incluye cuota social al monto normal
And **no** incluye aranceles de actividades.

---

## Scenario: beca parcial porcentaje

Given una `Beca Socio` vigente con `tipo_beca = Parcial Porcentaje`,
  `pct_cuota_social = 50` y `pct_arancel = 25`
When se genera la deuda mensual
Then la línea de cuota social se factura al **50 %** del monto de categoría
And cada arancel activo se factura al **75 %** de su tarifa.

---

## Scenario: vigencia y renovación

Given una beca con `fecha_desde = 01/01/2026` y `fecha_hasta = 30/06/2026`
When Secretaría consulta becas vigentes al `15/03/2026`
Then la beca aparece como `Activa`
When la fecha de referencia es `01/07/2026`
Then la beca **no** se aplica (fuera de vigencia).

---

## Seguridad

- Alta/edición de `Beca Socio` restringida a rol `Secretaria` / `System Manager`.
- Un socio no puede leer becas de otro socio vía API Desk.

---

## Scenario: botón Crear beca en formulario Socio

Given Secretaría abre un `Socio` existente (no dado de baja)
When observa el grupo **Operación Secretaría**
Then ve el botón **Crear beca**
When lo pulsa
Then se abre un nuevo `Beca Socio` con el campo **Socio** precargado.

---

## Scenario: tabla de becas bajo inscripciones

Given un `Socio` con una o más filas en `Beca Socio`
When Secretaría abre el formulario `Socio`
Then debajo de la tabla de **Inscripciones activas** ve **Becas asignadas**
And cada fila muestra tipo, descuentos, vigencia (desde/hasta), estado y si está **Vigente** hoy
And puede abrir el detalle de cada beca desde la fila.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| DocType | `members/doctype/beca_socio/` |
| Servicio | `members/services/beca_socio.py` |
| API Desk | `members/api/socio_operaciones_desk.py` (`list_becas_socio`) |
| UI Socio | `members/doctype/socio/socio.js` |
| Tests | `members/tests/test_beca_socio_desk.py` |

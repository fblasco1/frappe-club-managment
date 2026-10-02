# Spec: Bonificaciones activas en la ficha del socio

Secretaría ve en el perfil del socio todas las bonificaciones que hoy le aplican y puede cancelarlas
desde ahí, sin buscar cada DocType por separado.

---

## Scenario: panel «Bonificaciones activas»

Given un socio con:
- una **Beca Socio** en estado «Activa» y vigente o futura (fecha hasta vacía o ≥ hoy)
- una **Bonificacion Recurrente** «Activa» con fecha hasta vacía o ≥ hoy
- una **Bonificacion Arancel** individual (campo socio = el socio) en estado «Activa»
When Secretaría abre la ficha del socio
Then ve el panel **Bonificaciones activas** con una fila por cada una:
tipo, descuento, alcance (actividad / grupo / equipo o cuota social / arancel), vigencia o período y motivo
And cada fila tiene los botones **Ver** y **Cancelar**.

---

## Scenario: no se listan las inactivas

Given becas «Cancelada» o «Vencida», becas «Activa» con fecha hasta < hoy,
recurrentes «Anulada» o con fecha hasta < hoy y bonificaciones de arancel «Anulada»
Then no aparecen en el panel
And si no queda ninguna, el panel dice «Sin bonificaciones activas».

---

## Scenario: bonificaciones de arancel masivas

Given una Bonificacion Arancel masiva (sin socio; por actividad, grupo o equipo)
Then **no** aparece en la ficha del socio (cancelarla afectaría a otros socios).

---

## Scenario: cancelar desde la ficha

Given Secretaría pulsa **Cancelar** en una fila y confirma
Then la Beca pasa a estado «Cancelada» y las bonificaciones (recurrente / arancel) a «Anulada»
And la fila deja de mostrarse
And el cambio solo afecta deuda futura; lo ya facturado no se modifica.

Given es una Bonificacion Arancel
Then el diálogo de confirmación advierte que, si ya se aplicó en un cobro, la nota de crédito emitida no se revierte.

---

## Scenario: seguridad

Given un usuario sin rol Secretaría / System Manager
When llama a la API de listado o cancelación
Then recibe PermissionError.

Given se intenta cancelar una bonificación indicando un socio distinto al de la bonificación
Then se rechaza (no se puede cancelar la de otro socio desde una ficha ajena).

Given se indica un DocType que no es Beca Socio, Bonificacion Recurrente ni Bonificacion Arancel
Then se rechaza.

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Servicio | `members/services/bonificaciones_socio.py` |
| API | `members/api/socio_operaciones_desk.list_bonificaciones_activas_socio` / `cancelar_bonificacion_socio` |
| UI | `members/doctype/socio/socio.js` → `render_bonificaciones_activas` |
| Tests | `members/tests/test_bonificaciones_activas_socio.py` |

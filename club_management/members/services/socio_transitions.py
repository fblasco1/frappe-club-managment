"""Transiciones server-side del estado de un `Socio`.

El campo `Socio.estado` es read-only desde el formulario; los cambios deben
pasar por `cambiar_estado()`, que setea el flag
`flags.estado_change_authorized` antes de guardar y registra la auditoría
correspondiente (`ultimo_cambio_estado_por/en`, `motivo_ultimo_cambio_estado`).

Si la transición lleva a `"Activo"` y `fecha_alta` aún está vacía, se setea
con la fecha del día (la primera activación marca el alta).
Si la transición es `Baja` → `Activo` dentro de 6 meses de la baja, se
conserva `fecha_alta`; si pasaron más de 6 meses, se reinicia (nueva antigüedad).
Si la transición es `Baja` → `Activo`, se re-sincronizan las suscripciones
(cuota social; la baja las había cancelado).
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import add_months, getdate, now, today

MESES_CONSERVAR_ANTIGUEDAD_POST_BAJA = 6


def debe_conservar_fecha_alta_tras_baja(fecha_baja: date | str | None) -> bool:
	"""True si el alta es dentro de los 6 meses posteriores a la baja (inclusive)."""
	if not fecha_baja:
		return False
	limite = add_months(getdate(fecha_baja), MESES_CONSERVAR_ANTIGUEDAD_POST_BAJA)
	return getdate(today()) <= getdate(limite)


def cambiar_estado(
	socio_name: str,
	nuevo_estado: str,
	*,
	motivo: str | None = None,
) -> None:
	"""Mueve un `Socio` a `nuevo_estado` y registra la auditoría."""
	socio = frappe.get_doc("Socio", socio_name)
	estado_anterior = socio.estado
	fecha_baja_ref = socio.ultimo_cambio_estado_en if estado_anterior == "Baja" else None
	socio.flags.estado_change_authorized = True
	socio.estado = nuevo_estado
	if estado_anterior == "Baja" and nuevo_estado == "Activo":
		if not debe_conservar_fecha_alta_tras_baja(fecha_baja_ref):
			socio.fecha_alta = today()
	socio.ultimo_cambio_estado_por = frappe.session.user
	socio.ultimo_cambio_estado_en = now()
	socio.motivo_ultimo_cambio_estado = motivo
	socio.save(ignore_permissions=True)
	if nuevo_estado == "Baja":
		from club_management.activities.services.inscripcion_socio import (
			baja_inscripciones_activas_socio,
		)
		from club_management.members.services.suscripciones_socio import (
			sync_suscripciones_al_dar_baja_socio,
		)

		baja_inscripciones_activas_socio(socio_name)
		sync_suscripciones_al_dar_baja_socio(socio_name)
	elif estado_anterior == "Baja" and nuevo_estado == "Activo":
		from club_management.members.services.suscripciones_socio import (
			sync_suscripciones_al_dar_alta_socio,
		)

		sync_suscripciones_al_dar_alta_socio(socio_name)

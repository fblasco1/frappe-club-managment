"""Transiciones server-side del estado de un `Socio`.

El campo `Socio.estado` es read-only desde el formulario; los cambios deben
pasar por `cambiar_estado()`, que setea el flag
`flags.estado_change_authorized` antes de guardar y registra la auditoría
correspondiente (`ultimo_cambio_estado_por/en`, `motivo_ultimo_cambio_estado`).

Si la transición lleva a `"Activo"` y `fecha_alta` aún está vacía, se setea
con la fecha del día (la primera activación marca el alta).
"""

from __future__ import annotations

import frappe
from frappe.utils import now


def cambiar_estado(
	socio_name: str,
	nuevo_estado: str,
	*,
	motivo: str | None = None,
) -> None:
	"""Mueve un `Socio` a `nuevo_estado` y registra la auditoría."""
	socio = frappe.get_doc("Socio", socio_name)
	socio.flags.estado_change_authorized = True
	socio.estado = nuevo_estado
	socio.ultimo_cambio_estado_por = frappe.session.user
	socio.ultimo_cambio_estado_en = now()
	socio.motivo_ultimo_cambio_estado = motivo
	socio.save(ignore_permissions=True)
	if nuevo_estado == "Baja":
		from club_management.members.services.suscripciones_socio import (
			sync_suscripciones_al_dar_baja_socio,
		)

		sync_suscripciones_al_dar_baja_socio(socio_name)

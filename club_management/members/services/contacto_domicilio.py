"""Mapeo y normalización legacy de contacto/domicilio en Members."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.model.document import Document


def normalize_legacy_solicitud_payload(payload: dict[str, Any]) -> None:
	"""Acepta nombres legacy del portal/API y los traduce al schema actual."""
	_pairs = (
		("telefono", "telefono_movil"),
		("telefono_tutor", "telefono_movil_tutor"),
		("localidad", "localidad_barrio"),
		("localidad_tutor", "localidad_barrio_tutor"),
		("domicilio", "calle"),
		("domicilio_tutor", "calle_tutor"),
	)
	for legacy, current in _pairs:
		if payload.get(legacy) and not payload.get(current):
			payload[current] = payload.pop(legacy)
		elif legacy in payload:
			payload.pop(legacy, None)


def map_socio_contacto_domicilio_desde_solicitud(solicitud: Document) -> dict[str, Any]:
	"""Copia contacto/domicilio del solicitante hacia un payload de `Socio`."""
	return {
		"email": solicitud.email,
		"telefono_fijo": solicitud.get("telefono_fijo") or "",
		"telefono_movil": solicitud.get("telefono_movil") or solicitud.get("telefono") or "",
		"calle": solicitud.get("calle") or "",
		"numero": solicitud.get("numero") or "",
		"piso": solicitud.get("piso") or "",
		"departamento": solicitud.get("departamento") or "",
		"provincia": solicitud.get("provincia") or "",
		"ciudad": solicitud.get("ciudad") or "",
		"localidad_barrio": solicitud.get("localidad_barrio") or solicitud.get("localidad") or "",
		"codigo_postal": solicitud.get("codigo_postal") or "",
	}


def map_tutor_contacto_domicilio_desde_solicitud(solicitud: Document) -> dict[str, Any]:
	"""Copia contacto/domicilio del responsable hacia un payload de `Tutor No Socio`."""
	calle = solicitud.get("calle_tutor") or solicitud.get("calle") or ""
	return {
		"email": solicitud.get("email_tutor") or "",
		"telefono_fijo": solicitud.get("telefono_fijo_tutor") or "",
		"telefono_movil": solicitud.get("telefono_movil_tutor")
		or solicitud.get("telefono_tutor")
		or "",
		"calle": calle,
		"numero": solicitud.get("numero_tutor") or "",
		"piso": solicitud.get("piso_tutor") or "",
		"departamento": solicitud.get("departamento_tutor") or "",
		"provincia": solicitud.get("provincia_tutor") or solicitud.get("provincia") or "",
		"ciudad": solicitud.get("ciudad_tutor") or solicitud.get("ciudad") or "",
		"localidad_barrio": solicitud.get("localidad_barrio_tutor")
		or solicitud.get("localidad_tutor")
		or solicitud.get("localidad_barrio")
		or solicitud.get("localidad")
		or "",
		"codigo_postal": solicitud.get("codigo_postal_tutor")
		or solicitud.get("codigo_postal")
		or "",
	}


def assert_contacto_alta_socio(payload: dict[str, Any]) -> None:
	"""Valida email y móvil obligatorios en altas normales (no migración)."""
	faltantes = [
		campo
		for campo, etiqueta in (
			("email", "email"),
			("telefono_movil", "telefono_movil"),
		)
		if not (payload.get(campo) or "").strip()
	]
	if faltantes:
		frappe.throw(
			frappe._("Faltan datos obligatorios: {0}").format(", ".join(faltantes)),
			frappe.MandatoryError,
		)

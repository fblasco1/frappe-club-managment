"""Adaptador HTTP fino para callbacks Botón de Pago Supervielle."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.integrations.supervielle.reconciliation import process_callback
from club_management.integrations.supervielle_api import SupervielleIntegrationError


def _request_payload() -> dict[str, Any]:
	if getattr(frappe, "request", None):
		data = frappe.request.get_json(silent=True)
		if isinstance(data, dict):
			return data
	return dict(getattr(frappe.local, "form_dict", None) or {})


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
	frappe.local.response["http_status_code"] = status_code
	return payload


@frappe.whitelist(allow_guest=True)
def recibir_notificacion_pago() -> dict[str, Any]:
	"""Recibe un callback firmado; la firma es el gate explícito para Guest."""
	payload = _request_payload()
	try:
		result = process_callback(payload)
	except SupervielleIntegrationError:
		return _response(403, {"status": "forbidden", "message": "Firma o payload inválido."})
	except frappe.ValidationError as exc:
		return _response(422, {"status": "rejected", "message": str(exc)})
	except Exception:
		frappe.log_error(title="Supervielle callback temporal")
		return _response(503, {"status": "error", "message": "Error temporal."})
	return _response(200, result)

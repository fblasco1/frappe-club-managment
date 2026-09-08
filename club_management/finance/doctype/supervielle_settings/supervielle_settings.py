"""Supervielle Settings: credenciales Cobranza Ágil / Botón de Pago."""

from __future__ import annotations

from frappe.model.document import Document


class SupervielleSettings(Document):
	sandbox_mode: int
	secret_key: str | None
	cuit_emisor: str
	api_url: str
	concepto_default: str
	url_ok: str
	url_error: str
	convenio: str
	rendicion_api_url: str
	rendicion_apply_enabled: int
	mode_of_payment: str
	clearing_account: str | None

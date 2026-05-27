"""Tokens públicos del flujo Solicitud de Asociación."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import frappe


def get_solicitud_by_seguimiento_token(token: str) -> frappe.model.document.Document | None:
	"""Devuelve la solicitud cuyo `token_seguimiento` coincide, o `None`."""
	if not (token or "").strip():
		return None
	name = frappe.db.get_value("Solicitud Asociacion", {"token_seguimiento": token}, "name")
	if not name:
		return None
	return frappe.get_doc("Solicitud Asociacion", name)


def sign_pago_token(solicitud_name: str) -> str:
	"""Genera un token de pago firmado (no enumerable)."""
	nonce = secrets.token_hex(16)
	payload = f"{solicitud_name}:{nonce}"
	sig = _hmac(payload)
	raw = f"{payload}:{sig}"
	return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def verify_pago_token(token: str) -> str | None:
	"""Verifica el token y devuelve el `name` de la solicitud, o `None`."""
	if not token:
		return None
	try:
		padding = "=" * (-len(token) % 4)
		raw = base64.urlsafe_b64decode(token + padding).decode()
	except (ValueError, UnicodeDecodeError):
		return None

	parts = raw.split(":")
	if len(parts) != 3:
		return None
	solicitud_name, nonce, sig = parts
	payload = f"{solicitud_name}:{nonce}"
	if not hmac.compare_digest(sig, _hmac(payload)):
		return None
	if not frappe.db.exists("Solicitud Asociacion", solicitud_name):
		return None
	return solicitud_name


def _hmac(payload: str) -> str:
	key = (
		frappe.local.conf.get("secret")
		or frappe.local.conf.get("encryption_key")
		or frappe.local.site
		or "club_management_dev"
	)
	if isinstance(key, str):
		key = key.encode()
	return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()

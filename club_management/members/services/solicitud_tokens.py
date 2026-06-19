"""Tokens públicos del flujo Solicitud de Asociación."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from urllib.parse import quote, unquote

import frappe
from frappe.utils import get_url


def get_solicitud_by_seguimiento_token(token: str) -> frappe.model.document.Document | None:
	"""Devuelve la solicitud cuyo `token_seguimiento` coincide, o `None`."""
	if not (token or "").strip():
		return None
	name = frappe.db.get_value("Solicitud Asociacion", {"token_seguimiento": token}, "name")
	if not name:
		return None
	return frappe.get_doc("Solicitud Asociacion", name)


def normalize_pago_token_from_request(raw: str | None) -> str:
	"""Normaliza el token recibido en query/form (strip + unquote una vez)."""
	if not raw:
		return ""
	return unquote(str(raw).strip())


def build_pago_stub_url(pago_token: str, *, base_url: str | None = None) -> str:
	"""URL absoluta a `/pago-stub` con token percent-encoded."""
	encoded = quote(pago_token, safe="")
	path = f"/pago-stub?token={encoded}"
	if base_url:
		return f"{base_url.rstrip('/')}{path}"
	return get_url(path)


def build_inscripcion_actividades_url(pago_token: str, *, base_url: str | None = None) -> str:
	"""URL absoluta a `/inscripcion-actividades` (mismo token firmado que el pago)."""
	encoded = quote(pago_token, safe="")
	path = f"/inscripcion-actividades?token={encoded}"
	if base_url:
		return f"{base_url.rstrip('/')}{path}"
	return get_url(path)


def sign_pago_token(solicitud_name: str) -> str:
	"""Genera un token de pago firmado (no enumerable)."""
	nonce = secrets.token_hex(16)
	payload = f"{solicitud_name}:{nonce}"
	sig = _hmac(payload)
	raw = f"{payload}:{sig}"
	return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def verify_pago_token(token: str) -> str | None:
	"""Verifica el token y devuelve el `name` de la solicitud, o `None`."""
	token = normalize_pago_token_from_request(token)
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

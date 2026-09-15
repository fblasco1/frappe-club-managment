"""Tokens HMAC de sesión guest y token_acceso de reserva externa.

Spec: `club_management/specs/reservas_espacio_externo.md`
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

import frappe

SESION_PREFIX = "ext"
DEFAULT_TTL_SECONDS = 2 * 60 * 60  # ~2 h


def _signing_key() -> bytes:
	key = (
		frappe.local.conf.get("secret")
		or frappe.local.conf.get("encryption_key")
		or frappe.local.site
		or "club_management_dev"
	)
	if isinstance(key, str):
		return key.encode()
	return bytes(key)


def _hmac(payload: str) -> str:
	return hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()


def sign_sesion_token(*, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
	"""Firma un `sesion_token` de corta vida para el canal externo."""
	exp = int(time.time()) + int(ttl_seconds)
	nonce = secrets.token_hex(8)
	payload = f"{SESION_PREFIX}:{exp}:{nonce}"
	sig = _hmac(payload)
	raw = f"{payload}:{sig}"
	return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def verify_sesion_token(token: str | None) -> bool:
	"""True si el token es HMAC válido y no vencido."""
	raw_token = (token or "").strip()
	if not raw_token:
		return False
	try:
		padding = "=" * (-len(raw_token) % 4)
		raw = base64.urlsafe_b64decode(raw_token + padding).decode()
	except (ValueError, UnicodeDecodeError):
		return False

	parts = raw.split(":")
	if len(parts) != 4:
		return False
	prefix, exp_s, nonce, sig = parts
	if prefix != SESION_PREFIX or not exp_s.isdigit() or not nonce:
		return False
	payload = f"{prefix}:{exp_s}:{nonce}"
	if not hmac.compare_digest(sig, _hmac(payload)):
		return False
	if int(exp_s) < int(time.time()):
		return False
	return True


def generate_token_acceso() -> str:
	"""Token opaco único para gestionar una reserva externa."""
	return secrets.token_urlsafe(32)

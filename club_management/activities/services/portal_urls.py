"""URL del portal autenticado y orígenes CORS (BL-6 Fase B)."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import frappe


PORTAL_SOCIO_PATH = "/socios/actividades"
DEFAULT_PORTAL_SOCIO_URL = f"https://www.icdpedroechague.com.ar{PORTAL_SOCIO_PATH}"


def _strip_token_query(url: str) -> str:
	parsed = urlparse(url.strip())
	return urlunparse(parsed._replace(query="", fragment="")).rstrip("/")


def _with_portal_path(url: str) -> str:
	clean = _strip_token_query(url)
	parsed = urlparse(clean)
	path = (parsed.path or "").rstrip("/")
	if path.endswith(PORTAL_SOCIO_PATH):
		return clean
	if path in {"", "/"}:
		return f"{parsed.scheme}://{parsed.netloc}{PORTAL_SOCIO_PATH}"
	return clean


def build_portal_socio_url() -> str:
	"""URL absoluta del área autenticada. Nunca incluye pago_token."""
	conf = str(frappe.conf.get("portal_socio_url") or "").strip()
	if conf:
		return _with_portal_path(conf)
	settings = ""
	if frappe.db.exists("DocType", "Club Settings"):
		settings = str(
			frappe.db.get_single_value("Club Settings", "portal_socio_url") or ""
		).strip()
	if settings:
		return _with_portal_path(settings)
	return DEFAULT_PORTAL_SOCIO_URL


def portal_allowed_origins() -> list[str]:
	"""Orígenes CORS del portal: nunca `*`, incluye el host de portal_socio_url."""
	origins: list[str] = []
	raw = frappe.conf.get("allow_cors")
	if isinstance(raw, str):
		candidates = [raw]
	elif isinstance(raw, (list, tuple)):
		candidates = list(raw)
	else:
		candidates = []
	for item in candidates:
		origin = str(item or "").strip().rstrip("/")
		if origin and origin != "*":
			origins.append(origin)

	portal = urlparse(build_portal_socio_url())
	if portal.scheme and portal.netloc:
		origins.append(f"{portal.scheme}://{portal.netloc}")

	unique = sorted(set(origins))
	return unique


def apply_portal_cors_allowlist() -> None:
	"""Fail closed: Frappe lee `frappe.local.allow_cors`; nunca propaga `*`."""
	frappe.local.allow_cors = portal_allowed_origins()

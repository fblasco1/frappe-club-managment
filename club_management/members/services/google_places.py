"""Configuración de Google Places para el portal público.

Implementación C2.5: Maps JS + Places Autocomplete (legacy). Mejoras futuras
(Places API New, session tokens, proxy de key): ver spec
`solicitud_asociacion_publica.md` — «Mejora a futuro (Google Maps Platform)».
"""

from __future__ import annotations

import frappe


def get_google_maps_api_key() -> str:
	"""Clave de Maps/Places desde `site_config.json` (`google_maps_api_key`)."""
	return (frappe.conf.get("google_maps_api_key") or "").strip()


def get_places_config_for_portal() -> dict[str, str | bool]:
	"""Config expuesta al formulario público (sin secretos adicionales)."""
	api_key = get_google_maps_api_key()
	return {
		"enabled": bool(api_key),
		"api_key": api_key,
	}

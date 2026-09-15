"""Contexto de la página pública `/solicitud-asociacion`."""

from __future__ import annotations

from club_management.members.services.google_places import get_places_config_for_portal


def get_context(context) -> None:
	places = get_places_config_for_portal()
	context.google_places_enabled = places["enabled"]
	context.google_maps_api_key = places["api_key"]

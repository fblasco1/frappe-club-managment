"""API Desk — importación / sync de fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe

from club_management.spaces.fixtures.contract import ORIGIN_FEBAMBA_GES
from club_management.spaces.fixtures.import_partidos import import_partidos_csv
from club_management.spaces.fixtures.sources.febamba_ges import (
	get_fixture_json_url,
	import_febamba_ges_json,
	sync_febamba_ges_from_url,
)
from club_management.spaces.fixtures.upsert import import_fixture_payload
from club_management.spaces.permissions import ensure_spaces_write_access


def _ensure_reserva_write() -> None:
	ensure_spaces_write_access()
	if not frappe.has_permission("Reserva Espacio", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)


@frappe.whitelist()
def import_fixtures_json(payload: str | dict[str, Any], cancel_missing: int = 0) -> dict[str, Any]:
	"""Importa envelope JSON o lista de partidos desde Desk."""
	_ensure_reserva_write()
	data = json.loads(payload) if isinstance(payload, str) else payload
	return import_fixture_payload(data, cancel_missing=bool(cancel_missing))


@frappe.whitelist()
def sync_fixtures_febamba(
	file_path: str | None = None,
	url: str | None = None,
	cancel_missing: int = 0,
) -> dict[str, Any]:
	"""Sync FeBAMBA GES: URL canónica (default), override url, o archivo local."""
	_ensure_reserva_write()
	if file_path:
		return import_febamba_ges_json(
			file_path,
			cancel_missing=bool(cancel_missing),
		)
	return sync_febamba_ges_from_url(
		url or None,
		cancel_missing=bool(cancel_missing),
	)


@frappe.whitelist()
def import_fixtures_csv(file_path: str, cancel_missing: int = 0) -> dict[str, Any]:
	"""Importa CSV de partidos (formato CM o manual)."""
	_ensure_reserva_write()
	path = Path(file_path)
	if not path.is_file():
		frappe.throw(frappe._("Archivo no encontrado: {0}").format(file_path))
	return import_partidos_csv(path, cancel_missing=bool(cancel_missing))


@frappe.whitelist()
def preview_fixture_sources() -> list[dict[str, str]]:
	"""Fuentes de fixture disponibles para sync Desk."""
	ensure_spaces_write_access()
	return [
		{
			"id": ORIGIN_FEBAMBA_GES,
			"label": "FeBAMBA GES (formativas_ges JSON)",
			"enabled": "1",
			"url": get_fixture_json_url(),
		},
	]

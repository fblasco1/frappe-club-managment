"""API Desk — importación / sync de fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.desk.utils import provide_binary_file

from club_management.spaces.fixtures.contract import (
	ORIGIN_FEBAMBA_GES,
	ORIGIN_FMV_VOLEY,
	ORIGIN_LIGA_EXCEL,
)
from club_management.spaces.fixtures.import_excel import (
	apply_excel_fixtures,
	preview_excel_fixtures,
)
from club_management.spaces.fixtures.import_partidos import import_partidos_csv
from club_management.spaces.fixtures.sources.febamba_ges import (
	get_fixture_json_url as get_febamba_url,
)
from club_management.spaces.fixtures.sources.febamba_ges import (
	import_febamba_ges_json,
	sync_febamba_ges_from_url,
)
from club_management.spaces.fixtures.sources.fmv_voley import (
	get_fixture_json_url as get_fmv_url,
)
from club_management.spaces.fixtures.sources.fmv_voley import (
	import_fmv_voley_json,
	sync_fmv_voley_from_url,
)
from club_management.spaces.fixtures.upsert import import_fixture_payload
from club_management.spaces.permissions import ensure_spaces_write_access


def _ensure_reserva_write() -> None:
	ensure_spaces_write_access()
	if not frappe.has_permission("Reserva Espacio", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)


def _is_system_manager() -> bool:
	return "System Manager" in frappe.get_roles()


def _ensure_technical_override_allowed(value: str | None) -> None:
	if value and not _is_system_manager():
		frappe.throw(
			frappe._("Solo System Manager puede reemplazar URL o ruta de fixture"),
			frappe.PermissionError,
		)


def _authorized_excel_file(file_url: str) -> str:
	raw = str(file_url or "").strip()
	if not raw:
		frappe.throw(frappe._("Falta archivo Excel"), frappe.ValidationError)
	if Path(raw).suffix.lower() != ".xlsx":
		frappe.throw(frappe._("Solo se admiten archivos .xlsx"), frappe.ValidationError)
	if _is_system_manager() and Path(raw).is_file():
		return raw
	file_name = frappe.db.get_value("File", {"file_url": raw}, "name")
	if not file_name:
		frappe.throw(frappe._("El archivo debe haber sido subido a SICLUB"), frappe.PermissionError)
	file_doc = frappe.get_doc("File", file_name)
	if not frappe.has_permission("File", ptype="read", doc=file_doc):
		frappe.throw(frappe._("No autorizado para leer el archivo"), frappe.PermissionError)
	return raw


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
	_ensure_technical_override_allowed(file_path or url)
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
def sync_fixtures_fmv(
	file_path: str | None = None,
	url: str | None = None,
	cancel_missing: int = 0,
) -> dict[str, Any]:
	"""Sync FMV Vóley: URL canónica (default), override url, o archivo local."""
	_ensure_reserva_write()
	_ensure_technical_override_allowed(file_path or url)
	if file_path:
		return import_fmv_voley_json(
			file_path,
			cancel_missing=bool(cancel_missing),
		)
	return sync_fmv_voley_from_url(
		url or None,
		cancel_missing=bool(cancel_missing),
	)


@frappe.whitelist()
def import_fixtures_csv(file_path: str, cancel_missing: int = 0) -> dict[str, Any]:
	"""Importa CSV de partidos (formato CM o manual)."""
	_ensure_reserva_write()
	_ensure_technical_override_allowed(file_path)
	path = Path(file_path)
	if not path.is_file():
		frappe.throw(frappe._("Archivo no encontrado: {0}").format(file_path))
	return import_partidos_csv(path, cancel_missing=bool(cancel_missing))


@frappe.whitelist()
def preview_fixtures_excel(file_url: str) -> dict[str, Any]:
	"""Preview Excel ligas sin escribir BD."""
	_ensure_reserva_write()
	return preview_excel_fixtures(_authorized_excel_file(file_url))


@frappe.whitelist()
def apply_fixtures_excel(file_url: str, cancel_missing: int = 0) -> dict[str, Any]:
	"""Aplica import Excel ligas (upsert idempotente)."""
	_ensure_reserva_write()
	return apply_excel_fixtures(
		_authorized_excel_file(file_url),
		cancel_missing=bool(cancel_missing),
	)


@frappe.whitelist()
def download_fixtures_excel_template() -> None:
	"""Descarga la plantilla canónica XLSX para fixtures de ligas."""
	_ensure_reserva_write()
	path = Path(
		frappe.get_app_path(
			"club_management",
			"spaces",
			"fixtures",
			"liga_excel_sample.xlsx",
		)
	)
	if not path.is_file():
		frappe.throw(frappe._("No se encontró la plantilla Excel"), frappe.ValidationError)
	provide_binary_file(
		"plantilla_fixture_ligas",
		"xlsx",
		path.read_bytes(),
	)


@frappe.whitelist()
def preview_fixture_sources() -> list[dict[str, str]]:
	"""Fuentes de fixture disponibles para sync Desk."""
	ensure_spaces_write_access()
	return [
		{
			"id": ORIGIN_FEBAMBA_GES,
			"label": "FeBAMBA GES (formativas_ges JSON)",
			"enabled": "1",
			"url": get_febamba_url(),
		},
		{
			"id": ORIGIN_FMV_VOLEY,
			"label": "FMV Vóley (fmv_voley_ges JSON)",
			"enabled": "1",
			"url": get_fmv_url(),
		},
		{
			"id": ORIGIN_LIGA_EXCEL,
			"label": "Ligas Excel (plantilla canónica)",
			"enabled": "1",
			"url": "",
		},
	]

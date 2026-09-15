"""Fuente FeBAMBA GES — JSON publicado por formativas_ges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
import requests
from frappe import _

from club_management.spaces.fixtures.contract import ORIGIN_FEBAMBA_GES
from club_management.spaces.fixtures.upsert import import_fixture_payload

# URL canónica en main (no usar Google Sheet ni Pages como fuente SICLUB).
FEBAMBA_GES_JSON_URL = (
	"https://raw.githubusercontent.com/fblasco1/formativas_ges/main/"
	"outputs/echague/fixture_echague.json"
)

_FETCH_TIMEOUT_SEC = 60


def default_fixture_json_path() -> Path:
	return (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "fixtures"
		/ "febamba_ges_sample.json"
	)


def get_fixture_json_url() -> str:
	"""URL del JSON máquina; override vía site_config `febamba_ges_fixture_json_url`."""
	return (
		frappe.conf.get("febamba_ges_fixture_json_url")
		or FEBAMBA_GES_JSON_URL
	)


def is_fixture_sync_enabled() -> bool:
	"""Cron/Desk: activar con site_config `febamba_ges_fixture_sync_enabled`: true."""
	return bool(frappe.conf.get("febamba_ges_fixture_sync_enabled"))


def validate_fixture_envelope(data: dict[str, Any]) -> None:
	if data.get("version") != 1:
		frappe.throw(
			_("Fixture FeBAMBA: version JSON no soportada ({0})").format(data.get("version")),
			frappe.ValidationError,
		)
	source = (data.get("source") or "").strip()
	if source and source != ORIGIN_FEBAMBA_GES:
		frappe.throw(
			_("Fixture FeBAMBA: source inesperado ({0})").format(source),
			frappe.ValidationError,
		)
	partidos = data.get("partidos")
	if not isinstance(partidos, list):
		frappe.throw(_("Fixture FeBAMBA: falta lista partidos"), frappe.ValidationError)


def fetch_fixture_json(url: str | None = None) -> dict[str, Any]:
	"""Descarga envelope JSON desde formativas_ges (raw GitHub main)."""
	target = (url or get_fixture_json_url()).strip()
	try:
		response = requests.get(target, timeout=_FETCH_TIMEOUT_SEC)
		response.raise_for_status()
	except requests.RequestException as exc:
		frappe.throw(
			_("No se pudo descargar fixture FeBAMBA desde {0}: {1}").format(target, exc),
			frappe.ValidationError,
		)
	try:
		data = response.json()
	except json.JSONDecodeError as exc:
		frappe.throw(
			_("Respuesta JSON inválida desde {0}: {1}").format(target, exc),
			frappe.ValidationError,
		)
	if not isinstance(data, dict):
		frappe.throw(_("Fixture FeBAMBA: se esperaba un objeto JSON"), frappe.ValidationError)
	validate_fixture_envelope(data)
	return data


def load_json_file(path: str | Path) -> dict[str, Any] | list[Any]:
	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)
	if isinstance(data, dict):
		validate_fixture_envelope(data)
	return data


def import_febamba_ges_json(
	path: str | Path | None = None,
	*,
	cancel_missing: bool = False,
) -> dict[str, Any]:
	"""Importa fixture JSON desde archivo local (dev / fallback)."""
	json_path = Path(path) if path else default_fixture_json_path()
	data = load_json_file(json_path)
	return _import_envelope(data, cancel_missing=cancel_missing, source_label=str(json_path))


def sync_febamba_ges_from_url(
	url: str | None = None,
	*,
	cancel_missing: bool = False,
) -> dict[str, Any]:
	"""Sync producción: descarga JSON canónico e importa (upsert idempotente)."""
	target = (url or get_fixture_json_url()).strip()
	data = fetch_fixture_json(target)
	return _import_envelope(
		data,
		cancel_missing=cancel_missing,
		source_label=target,
	)


def sync_febamba_ges_scheduled() -> None:
	"""Job programado (08:00 y 20:00 ART). Requiere site_config enabled."""
	if not is_fixture_sync_enabled():
		return
	try:
		sync_febamba_ges_from_url(cancel_missing=True)
	except Exception:
		frappe.log_error(title="Sync fixture FeBAMBA GES")


def _import_envelope(
	data: dict[str, Any],
	*,
	cancel_missing: bool,
	source_label: str,
) -> dict[str, Any]:
	result = import_fixture_payload(
		data,
		source=ORIGIN_FEBAMBA_GES,
		cancel_missing=cancel_missing,
	)
	result["source_url"] = source_label
	result["generated_at"] = data.get("generated_at")
	result["club"] = data.get("club")
	return result


def sheet_row_to_payload(row: dict[str, str]) -> dict[str, str]:
	"""Convierte fila Sheet/CSV GES al contrato JSON SICLUB."""
	return {
		"source": ORIGIN_FEBAMBA_GES,
		"external_id": row.get("ID_PARTIDO", ""),
		"fecha": row.get("FECHA", ""),
		"hora": row.get("HORA", ""),
		"tira": row.get("TIRA", ""),
		"categoria": row.get("CATEGORIA", ""),
		"rival": row.get("RIVAL", ""),
		"localia": row.get("LOCALIA", ""),
		"direccion": row.get("DIRECCION", ""),
		"resultado": row.get("RESULTADO", ""),
		"espacio": row.get("ESPACIO") or None,
	}

"""Fuente FMV Vóley — JSON publicado por fmv_voley_ges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
import requests
from frappe import _

from club_management.spaces.fixtures.contract import ORIGIN_FMV_VOLEY
from club_management.spaces.fixtures.upsert import import_fixture_payload

FMV_VOLEY_JSON_URL = (
	"https://raw.githubusercontent.com/fblasco1/fmv_voley_ges/main/"
	"outputs/echague/fixture_fmv_voley.json"
)

_FETCH_TIMEOUT_SEC = 60


def default_fixture_json_path() -> Path:
	return (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "fixtures"
		/ "fmv_voley_sample.json"
	)


def get_fixture_json_url() -> str:
	"""URL del JSON máquina; override vía site_config `fmv_voley_fixture_json_url`."""
	return frappe.conf.get("fmv_voley_fixture_json_url") or FMV_VOLEY_JSON_URL


def is_fixture_sync_enabled() -> bool:
	"""Cron/Desk: activar con site_config `fmv_voley_fixture_sync_enabled`: true."""
	return bool(frappe.conf.get("fmv_voley_fixture_sync_enabled"))


def validate_fixture_envelope(data: dict[str, Any]) -> None:
	if data.get("version") != 1:
		frappe.throw(
			_("Fixture FMV: version JSON no soportada ({0})").format(data.get("version")),
			frappe.ValidationError,
		)
	source = (data.get("source") or "").strip()
	if source and source != ORIGIN_FMV_VOLEY:
		frappe.throw(
			_("Fixture FMV: source inesperado ({0})").format(source),
			frappe.ValidationError,
		)
	partidos = data.get("partidos")
	if not isinstance(partidos, list):
		frappe.throw(_("Fixture FMV: falta lista partidos"), frappe.ValidationError)


def fetch_fixture_json(url: str | None = None) -> dict[str, Any]:
	"""Descarga envelope JSON desde fmv_voley_ges (raw GitHub main)."""
	target = (url or get_fixture_json_url()).strip()
	try:
		response = requests.get(target, timeout=_FETCH_TIMEOUT_SEC)
		response.raise_for_status()
	except requests.RequestException as exc:
		frappe.throw(
			_("No se pudo descargar fixture FMV desde {0}: {1}").format(target, exc),
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
		frappe.throw(_("Fixture FMV: se esperaba un objeto JSON"), frappe.ValidationError)
	validate_fixture_envelope(data)
	return data


def load_json_file(path: str | Path) -> dict[str, Any] | list[Any]:
	with open(path, encoding="utf-8") as fh:
		data = json.load(fh)
	if isinstance(data, dict):
		validate_fixture_envelope(data)
	return data


def import_fmv_voley_json(
	path: str | Path | None = None,
	*,
	cancel_missing: bool = False,
) -> dict[str, Any]:
	"""Importa fixture JSON desde archivo local (dev / fallback)."""
	json_path = Path(path) if path else default_fixture_json_path()
	data = load_json_file(json_path)
	return _import_envelope(data, cancel_missing=cancel_missing, source_label=str(json_path))


def sync_fmv_voley_from_url(
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


def sync_fmv_voley_scheduled() -> None:
	"""Job programado (08:00 y 20:00 ART). Requiere site_config enabled."""
	if not is_fixture_sync_enabled():
		return
	try:
		sync_fmv_voley_from_url(cancel_missing=True)
	except Exception:
		frappe.log_error(title="Sync fixture FMV Vóley")


def _import_envelope(
	data: dict[str, Any],
	*,
	cancel_missing: bool,
	source_label: str,
) -> dict[str, Any]:
	result = import_fixture_payload(
		data,
		source=ORIGIN_FMV_VOLEY,
		cancel_missing=cancel_missing,
	)
	result["source_url"] = source_label
	result["generated_at"] = data.get("generated_at")
	result["club"] = data.get("club")
	result["club_id_fmv"] = data.get("club_id_fmv")
	return result

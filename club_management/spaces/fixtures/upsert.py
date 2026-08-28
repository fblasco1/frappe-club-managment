"""Upsert idempotente de partidos → Reserva Espacio Confirmada."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import getdate, today

from club_management.spaces.availability import find_occupancy_conflicts
from club_management.spaces.fixtures.contract import (
	FixtureImportReport,
	FixturePartido,
	LOCALIA_VISITANTE,
)
from club_management.spaces.fixtures.espacio_map import resolve_espacio
from club_management.spaces.fixtures.parse import normalize_partido
from club_management.spaces.fixtures.superposicion import format_superposicion_messages
from club_management.spaces.import_horarios import ensure_espacios_csv


def find_reserva_by_fixture(source: str, external_id: str) -> str | None:
	return frappe.db.get_value(
		"Reserva Espacio",
		{
			"origen_fixture": source,
			"id_externo_fixture": external_id,
		},
		"name",
	)


def upsert_fixture_partido(
	partido: FixturePartido,
	*,
	report: FixtureImportReport | None = None,
) -> str | None:
	"""Crea o actualiza Reserva Espacio. Devuelve name o None si omitido."""
	if partido.localia == LOCALIA_VISITANTE:
		if report is not None:
			report.omitidos.append(
				f"Visitante {partido.external_id} ({partido.categoria} vs {partido.rival})"
			)
		return None

	espacio = resolve_espacio(partido)
	if not espacio:
		if report is not None:
			report.omitidos.append(
				f"Sin espacio mapeado: {partido.external_id} ({partido.categoria})"
			)
		return None

	existing = find_reserva_by_fixture(partido.source, partido.external_id)
	payload: dict[str, Any] = {
		"espacio": espacio,
		"tipo": "Evento club",
		"estado": "Confirmada",
		"fecha": partido.fecha,
		"hora_desde": partido.hora_desde,
		"hora_hasta": partido.hora_hasta,
		"motivo": partido.motivo,
		"origen_fixture": partido.source,
		"id_externo_fixture": partido.external_id,
	}

	if existing:
		doc = frappe.get_doc("Reserva Espacio", existing)
		for key, value in payload.items():
			setattr(doc, key, value)
		try:
			doc.save(ignore_permissions=True)
		except frappe.ValidationError as exc:
			if report is not None:
				report.errores.append(f"{partido.external_id}: {exc}")
			return None
		_record_superposiciones(doc, partido, espacio, report)
		if report is not None:
			report.actualizados += 1
		return doc.name

	doc = frappe.get_doc({"doctype": "Reserva Espacio", **payload})
	try:
		doc.insert(ignore_permissions=True)
	except frappe.ValidationError as exc:
		if report is not None:
			report.errores.append(f"{partido.external_id}: {exc}")
		return None
	_record_superposiciones(doc, partido, espacio, report)
	if report is not None:
		report.creados += 1
	return doc.name


def _record_superposiciones(
	doc: frappe.model.document.Document,
	partido: FixturePartido,
	espacio: str,
	report: FixtureImportReport | None,
) -> None:
	if report is None:
		return
	conflicts = find_occupancy_conflicts(
		doc.espacio,
		doc.fecha,
		doc.hora_desde,
		doc.hora_hasta,
		exclude_reserva=doc.name,
	)
	if conflicts:
		report.superposiciones.extend(
			format_superposicion_messages(partido, espacio, conflicts)
		)


def cancel_missing_fixtures(
	source: str,
	seen_external_ids: set[str],
	*,
	report: FixtureImportReport | None = None,
	from_date: str | None = None,
) -> int:
	"""Cancela reservas Confirmada del origen que ya no vienen en el payload."""
	cutoff = getdate(from_date or today())
	rows = frappe.get_all(
		"Reserva Espacio",
		filters={
			"origen_fixture": source,
			"estado": "Confirmada",
		},
		fields=["name", "id_externo_fixture", "fecha"],
	)
	cancelados = 0
	for row in rows:
		ext_id = (row.id_externo_fixture or "").strip()
		if not ext_id or ext_id in seen_external_ids:
			continue
		if row.fecha and getdate(row.fecha) < cutoff:
			continue
		doc = frappe.get_doc("Reserva Espacio", row.name)
		doc.estado = "Cancelada"
		doc.superposicion_detectada = 0
		doc.save(ignore_permissions=True)
		cancelados += 1
		if report is not None:
			report.cancelados += 1
	return cancelados


def import_fixture_rows(
	rows: list[dict[str, Any]],
	*,
	source: str | None = None,
	cancel_missing: bool = False,
) -> dict[str, Any]:
	"""Importa lista de dicts (JSON partidos o filas CSV)."""
	ensure_espacios_csv()
	report = FixtureImportReport()
	seen_ids: set[str] = set()
	resolved_source = source

	for raw in rows:
		normalized = normalize_partido(raw)
		if isinstance(normalized, str):
			report.omitidos.append(normalized)
			continue
		partido = normalized
		if source:
			partido.source = source
		if resolved_source is None:
			resolved_source = partido.source
		seen_ids.add(partido.external_id)
		upsert_fixture_partido(partido, report=report)

	if cancel_missing and resolved_source and seen_ids:
		cancel_missing_fixtures(resolved_source, seen_ids, report=report)

	return report.as_dict()


def import_fixture_payload(data: dict[str, Any] | list[Any], **kwargs: Any) -> dict[str, Any]:
	"""Acepta envelope `{partidos: [...]}` o lista directa."""
	if isinstance(data, list):
		return import_fixture_rows(data, **kwargs)
	rows = data.get("partidos") or data.get("fixtures") or []
	kwargs = dict(kwargs)
	source = kwargs.pop("source", None) or data.get("source")
	return import_fixture_rows(rows, source=source, **kwargs)

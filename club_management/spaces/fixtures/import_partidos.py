"""Import CSV manual de partidos (mismas columnas que Sheet CM / JSON)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import frappe

from club_management.spaces.fixtures.contract import ORIGIN_MANUAL
from club_management.spaces.fixtures.sources.febamba_ges import sheet_row_to_payload
from club_management.spaces.fixtures.upsert import import_fixture_rows


def _normalize_header(header: str) -> str:
	return (header or "").strip().upper().replace(" ", "_")


def load_csv_rows(path: str | Path) -> list[dict[str, str]]:
	"""Lee CSV con cabeceras CM o contrato manual."""
	rows: list[dict[str, str]] = []
	with open(path, newline="", encoding="utf-8-sig") as fh:
		reader = csv.DictReader(fh, delimiter=";")
		if not reader.fieldnames:
			return rows
		# Detectar formato Sheet GES (ID_PARTIDO) vs manual (fecha minúscula)
		headers = {_normalize_header(h): h for h in reader.fieldnames}
		is_ges = "ID_PARTIDO" in headers or "FECHA" in headers
		for row in reader:
			if not any((v or "").strip() for v in row.values()):
				continue
			if is_ges:
				ges_row = {k.upper(): (row.get(orig) or "").strip() for k, orig in headers.items()}
				rows.append(sheet_row_to_payload(ges_row))
			else:
				payload = {
					"source": ORIGIN_MANUAL,
					"external_id": row.get(headers.get("ID_EXTERNO", "id_externo"), "")
					or row.get(headers.get("EXTERNAL_ID", "external_id"), "")
					or row.get("id_externo", "")
					or row.get("external_id", ""),
					"fecha": row.get(headers.get("FECHA", "fecha"), "") or row.get("fecha", ""),
					"hora": row.get(headers.get("HORA", "hora"), "")
					or row.get(headers.get("HORA_DESDE", "hora_desde"), "")
					or row.get("hora_desde", "")
					or row.get("hora", ""),
					"hora_hasta": row.get(headers.get("HORA_HASTA", "hora_hasta"), "")
					or row.get("hora_hasta", ""),
					"categoria": row.get(headers.get("CATEGORIA", "categoria"), "")
					or row.get("categoria", ""),
					"tira": row.get(headers.get("TIRA", "tira"), "") or row.get("tira", ""),
					"rival": row.get(headers.get("RIVAL", "rival"), "") or row.get("rival", ""),
					"localia": row.get(headers.get("LOCALIA", "localia"), "")
					or row.get("localia", "")
					or "Local",
					"espacio": row.get(headers.get("ESPACIO", "espacio"), "") or row.get("espacio", ""),
					"motivo": row.get(headers.get("MOTIVO", "motivo"), "") or row.get("motivo", ""),
				}
				if not payload["external_id"]:
					payload["external_id"] = (
						f"{payload['fecha']}|{payload['espacio']}|{payload['hora']}|{payload['categoria']}"
					)
				rows.append(payload)
	return rows


def import_partidos_csv(
	path: str | Path,
	*,
	source: str | None = None,
	cancel_missing: bool = False,
) -> dict[str, Any]:
	rows = load_csv_rows(path)
	return import_fixture_rows(
		rows,
		source=source or ORIGIN_MANUAL,
		cancel_missing=cancel_missing,
	)

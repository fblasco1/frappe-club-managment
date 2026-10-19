"""Remapea grupos Fútbol legacy TABI-1 / TABI-2 / Escuelita → TABI A / TABI B.

Spec: `club_management/specs/remap_futbol_tabi_grupos.md`.
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	sync_socio_actividad_resumen,
)
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed

ACTIVIDAD_FUTBOL = "Futbol"

# name canónico del Grupo Actividad
GRUPO_REMAP: dict[str, str] = {
	"Futbol / TABI-1": "Futbol / TABI A",
	"Futbol / TABI-2": "Futbol / TABI B",
	"Futbol / Escuelita": "Futbol / TABI B",
}


def _equipo_pertenece_a_grupo(equipo: str | None, grupo: str) -> bool:
	if not equipo:
		return True
	return frappe.db.get_value("Equipo Actividad", equipo, "grupo_actividad") == grupo


def _plan() -> dict[str, Any]:
	a_remapear: list[dict[str, Any]] = []
	conflictos: list[dict[str, Any]] = []
	for origen, destino in GRUPO_REMAP.items():
		if not frappe.db.exists("Grupo Actividad", origen):
			continue
		if not frappe.db.exists("Grupo Actividad", destino):
			frappe.throw(f"Falta el grupo destino {destino}")
		rows = frappe.get_all(
			INSCRIPCION_DOCTYPE,
			filters={"actividad": ACTIVIDAD_FUTBOL, "grupo_actividad": origen},
			fields=["name", "socio", "estado", "equipo_actividad", "grupo_actividad"],
			order_by="name asc",
		)
		for row in rows:
			base = {
				"inscripcion": row.name,
				"socio": row.socio,
				"estado": row.estado,
				"grupo_origen": origen,
				"grupo_destino": destino,
				"equipo_actividad": row.equipo_actividad,
			}
			if row.estado == "Activa":
				conflicto = frappe.db.exists(
					INSCRIPCION_DOCTYPE,
					{
						"socio": row.socio,
						"grupo_actividad": destino,
						"estado": "Activa",
						"name": ["!=", row.name],
					},
				)
				if conflicto:
					conflictos.append({**base, "conflicto_con": conflicto})
					continue
			a_remapear.append(base)
	return {"a_remapear": a_remapear, "conflictos": conflictos}


def _aplicar_fila(row: dict[str, Any]) -> None:
	destino = row["grupo_destino"]
	equipo = row.get("equipo_actividad")
	values: dict[str, Any] = {"grupo_actividad": destino}
	if not _equipo_pertenece_a_grupo(equipo, destino):
		values["equipo_actividad"] = None
	frappe.db.set_value(INSCRIPCION_DOCTYPE, row["inscripcion"], values, update_modified=True)
	if row.get("socio"):
		sync_socio_actividad_resumen(row["socio"])


def run(*, apply: bool = False, confirm: str = "", commit: bool = False) -> dict[str, Any]:
	"""Dry-run por defecto; apply remapea inscripciones sin conflicto."""
	ensure_bulk_apply_allowed(dry_run=not apply, confirm=confirm)
	plan = _plan()
	report: dict[str, Any] = {
		"apply": bool(apply),
		"remap": dict(GRUPO_REMAP),
		"a_remapear": plan["a_remapear"],
		"conflictos": plan["conflictos"],
		"remapeadas": [],
		"errores": [],
	}
	if apply:
		for row in plan["a_remapear"]:
			try:
				_aplicar_fila(row)
				report["remapeadas"].append(row["inscripcion"])
				if commit:
					frappe.db.commit()
			except Exception as exc:
				if commit:
					frappe.db.rollback()
				report["errores"].append({"inscripcion": row["inscripcion"], "error": str(exc)})
				frappe.log_error(
					title=f"Remap TABI Fútbol — {row['inscripcion']}",
					message=frappe.get_traceback(),
				)
				if commit:
					frappe.db.commit()
	report["resumen"] = {
		"a_remapear": len(report["a_remapear"]),
		"conflictos": len(report["conflictos"]),
		"remapeadas": len(report["remapeadas"]),
		"errores": len(report["errores"]),
	}
	return report

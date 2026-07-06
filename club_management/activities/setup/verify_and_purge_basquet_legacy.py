"""Verificación y purga de básquet legacy (actividades, CC, ítems).

Spec: basquet_cost_center_consolidado.md — escenarios verificación y purga.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _

from club_management.activities.services.basquet_unified_map import (
	BASQUET_ACTIVIDAD,
	LEGACY_BASQUET_ACTIVIDADES,
)
from club_management.setup.basquet_cost_center import (
	BASQUET_COST_CENTER,
	LEGACY_BASQUET_COST_CENTERS,
)
from club_management.setup.icdpe_company import resolve_icdpe_company

INSCRIPCION_DOCTYPE = "Inscripcion Actividad"
SALES_INVOICE_DOCTYPE = "Sales Invoice"
CONFIRM_PURGE_TOKEN = "PURGE_BASQUET_LEGACY"

_BASQUET_ITEM_PREFIXES = (
	"ICDPE-BASQUET-",
	"ICDPE-ARANCEL-MENSUAL-basquet-",
	"ICDPE-CUOTA-FEDERATIVA-basquet-",
)


@dataclass
class BasquetLegacyVerification:
	ok: bool = True
	inscripciones_legacy: list[dict[str, Any]] = field(default_factory=list)
	facturas_pendientes_legacy: list[dict[str, Any]] = field(default_factory=list)
	item_defaults_legacy_cc: list[dict[str, Any]] = field(default_factory=list)
	cost_centers_legacy_activos: list[str] = field(default_factory=list)
	actividades_legacy_habilitadas: list[str] = field(default_factory=list)
	errores: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"ok": self.ok,
			"inscripciones_legacy": self.inscripciones_legacy,
			"facturas_pendientes_legacy": self.facturas_pendientes_legacy,
			"item_defaults_legacy_cc": self.item_defaults_legacy_cc,
			"cost_centers_legacy_activos": self.cost_centers_legacy_activos,
			"actividades_legacy_habilitadas": self.actividades_legacy_habilitadas,
			"errores": self.errores,
		}


@dataclass
class BasquetLegacyPurgeStats:
	actividades: list[str] = field(default_factory=list)
	grupos: list[str] = field(default_factory=list)
	equipos: list[str] = field(default_factory=list)
	cost_centers: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"actividades": self.actividades,
			"grupos": self.grupos,
			"equipos": self.equipos,
			"cost_centers": self.cost_centers,
		}


def legacy_basquet_actividad_docnames() -> list[str]:
	names: list[str] = []
	for titulo in LEGACY_BASQUET_ACTIVIDADES:
		for name in frappe.get_all("Actividad", filters={"titulo": titulo}, pluck="name"):
			if name and name != BASQUET_ACTIVIDAD:
				names.append(name)
	return names


def _basquet_item_codes() -> list[str]:
	codes: list[str] = []
	for prefix in _BASQUET_ITEM_PREFIXES:
		codes.extend(
			frappe.get_all("Item", filters={"item_code": ["like", f"{prefix}%"]}, pluck="name")
		)
	return codes


def _find_inscripciones_legacy(actividad_names: list[str]) -> list[dict[str, Any]]:
	if not actividad_names or not frappe.db.table_exists(INSCRIPCION_DOCTYPE):
		return []
	return frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"actividad": ["in", actividad_names]},
		fields=["name", "socio", "actividad", "estado", "grupo_actividad", "equipo_actividad"],
		limit=50,
	)


def _find_facturas_pendientes_legacy(company: str) -> list[dict[str, Any]]:
	if not frappe.db.exists("DocType", SALES_INVOICE_DOCTYPE):
		return []

	legacy_items = set(_basquet_item_codes())
	hits: list[dict[str, Any]] = []
	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			"docstatus": 1,
			"outstanding_amount": [">", 0],
			"company": company,
		},
		fields=["name", "customer", "outstanding_amount"],
		limit=500,
	)
	for inv in invoices:
		lines = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": inv.name},
			fields=["name", "item_code", "cost_center"],
		)
		legacy_lines = [
			line
			for line in lines
			if (line.cost_center in LEGACY_BASQUET_COST_CENTERS)
			or (line.item_code in legacy_items)
		]
		if legacy_lines:
			hits.append(
				{
					"invoice": inv.name,
					"outstanding_amount": inv.outstanding_amount,
					"lines": legacy_lines,
				}
			)
	return hits[:50]


def _find_item_defaults_legacy_cc(company: str) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for cc in LEGACY_BASQUET_COST_CENTERS:
		for row in frappe.get_all(
			"Item Default",
			filters={"company": company, "selling_cost_center": cc},
			fields=["name", "parent", "selling_cost_center"],
			limit=50,
		):
			rows.append(row)
	return rows


def _find_cost_centers_legacy_activos() -> list[str]:
	activos: list[str] = []
	for cc in LEGACY_BASQUET_COST_CENTERS:
		if not frappe.db.exists("Cost Center", cc):
			continue
		if not frappe.db.get_value("Cost Center", cc, "disabled"):
			activos.append(cc)
	return activos


def _find_actividades_legacy_habilitadas() -> list[str]:
	habilitadas: list[str] = []
	for titulo in LEGACY_BASQUET_ACTIVIDADES:
		for name in frappe.get_all(
			"Actividad",
			filters={"titulo": titulo, "habilitada": 1},
			pluck="name",
		):
			if name != BASQUET_ACTIVIDAD:
				habilitadas.append(name)
	return habilitadas


def verify_basquet_legacy_cleanup() -> BasquetLegacyVerification:
	"""Comprueba que no queden referencias operativas al básquet legacy."""
	report = BasquetLegacyVerification()
	try:
		company = resolve_icdpe_company()
	except Exception as exc:
		report.ok = False
		report.errores.append(str(exc))
		return report

	if not frappe.db.exists("Cost Center", BASQUET_COST_CENTER):
		report.ok = False
		report.errores.append(f"Falta CC unificado {BASQUET_COST_CENTER!r}.")

	actividad_names = legacy_basquet_actividad_docnames()
	report.inscripciones_legacy = _find_inscripciones_legacy(actividad_names)
	report.facturas_pendientes_legacy = _find_facturas_pendientes_legacy(company)
	report.item_defaults_legacy_cc = _find_item_defaults_legacy_cc(company)
	report.cost_centers_legacy_activos = _find_cost_centers_legacy_activos()
	report.actividades_legacy_habilitadas = _find_actividades_legacy_habilitadas()

	if report.inscripciones_legacy:
		report.ok = False
		report.errores.append(
			_("Hay {0} inscripción(es) en actividades básquet legacy.").format(
				len(report.inscripciones_legacy)
			)
		)
	if report.facturas_pendientes_legacy:
		report.ok = False
		report.errores.append(
			_("Hay facturas con saldo pendiente vinculadas a básquet legacy.").format()
		)
	if report.item_defaults_legacy_cc:
		report.ok = False
		report.errores.append(
			_("Hay ítems con Item Default apuntando a CC legacy de básquet.")
		)
	if report.cost_centers_legacy_activos:
		report.ok = False
		report.errores.append(_("Hay CC legacy de básquet aún habilitados."))
	if report.actividades_legacy_habilitadas:
		report.ok = False
		report.errores.append(_("Hay actividades básquet legacy aún habilitadas."))

	return report


def purge_basquet_legacy_disabled() -> BasquetLegacyPurgeStats:
	"""Elimina actividades/grupos/equipos/CC legacy deshabilitados (solo tras verify OK)."""
	stats = BasquetLegacyPurgeStats()
	actividad_names = legacy_basquet_actividad_docnames()
	if not actividad_names:
		return stats

	grupo_names = frappe.get_all(
		"Grupo Actividad",
		filters={"actividad": ["in", actividad_names]},
		pluck="name",
	)
	for grupo in grupo_names:
		equipos = frappe.get_all(
			"Equipo Actividad",
			filters={"grupo_actividad": grupo},
			pluck="name",
		)
		for equipo in equipos:
			frappe.delete_doc("Equipo Actividad", equipo, force=1, ignore_permissions=True)
			stats.equipos.append(equipo)

	for grupo in grupo_names:
		frappe.delete_doc("Grupo Actividad", grupo, force=1, ignore_permissions=True)
		stats.grupos.append(grupo)

	for actividad in actividad_names:
		if frappe.db.get_value("Actividad", actividad, "habilitada"):
			frappe.throw(_("Actividad legacy {0} sigue habilitada; no se purga.").format(actividad))
		frappe.delete_doc("Actividad", actividad, force=1, ignore_permissions=True)
		stats.actividades.append(actividad)

	for cc in LEGACY_BASQUET_COST_CENTERS:
		if not frappe.db.exists("Cost Center", cc):
			continue
		if not frappe.db.get_value("Cost Center", cc, "disabled"):
			frappe.throw(_("CC legacy {0} no está deshabilitado; no se purga.").format(cc))
		frappe.delete_doc("Cost Center", cc, force=1, ignore_permissions=True)
		stats.cost_centers.append(cc)

	return stats


def run(
	*,
	dry_run: bool = True,
	purge: bool = False,
	confirm: str = "",
) -> dict[str, Any]:
	"""bench execute club_management.activities.setup.verify_and_purge_basquet_legacy.run"""
	report = verify_basquet_legacy_cleanup()
	result: dict[str, Any] = {"verification": report.to_dict(), "purge": None}

	if purge and report.ok:
		if dry_run:
			result["purge"] = {"dry_run": True, "would_purge": True}
		else:
			if confirm != CONFIRM_PURGE_TOKEN:
				frappe.throw(
					_(
						"Verificación OK. Para purgar pase confirm='{0}' y dry_run=False."
					).format(CONFIRM_PURGE_TOKEN)
				)
			stats = purge_basquet_legacy_disabled()
			result["purge"] = stats.to_dict()
	elif purge and not report.ok:
		result["purge"] = {"skipped": True, "reason": "verification_failed"}

	_print_report(result, dry_run=dry_run, purge=purge)
	return result


def _print_report(result: dict[str, Any], *, dry_run: bool, purge: bool) -> None:
	ver = result["verification"]
	mode = "SIMULACIÓN" if dry_run else "EJECUCIÓN"
	print(f"\n=== Verificación básquet legacy ({mode}) ===")
	print(f"OK: {ver['ok']}")
	print(f"Inscripciones legacy: {len(ver['inscripciones_legacy'])}")
	print(f"Facturas pendientes legacy: {len(ver['facturas_pendientes_legacy'])}")
	print(f"Item Default CC legacy: {len(ver['item_defaults_legacy_cc'])}")
	print(f"CC legacy activos: {len(ver['cost_centers_legacy_activos'])}")
	print(f"Actividades legacy habilitadas: {len(ver['actividades_legacy_habilitadas'])}")
	if ver["errores"]:
		print("Errores:")
		for err in ver["errores"]:
			print(f"  - {err}")
	if purge and ver["ok"]:
		if dry_run:
			print("\n(dry_run) La purga eliminaría actividades/grupos/equipos/CC legacy deshabilitados.")
		elif result.get("purge"):
			p = result["purge"]
			print(
				f"\nPurga: {len(p.get('actividades', []))} actividades, "
				f"{len(p.get('grupos', []))} grupos, "
				f"{len(p.get('equipos', []))} equipos, "
				f"{len(p.get('cost_centers', []))} CC."
			)
	print()

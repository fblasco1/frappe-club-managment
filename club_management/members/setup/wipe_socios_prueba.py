"""Elimina socios de prueba y documentos de cobranza vinculados (reset previo al padrón).

Ejecutar con ``bench execute`` **solo** cuando los datos actuales son descartables.

Ejemplo (simulación):

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.members.setup.wipe_socios_prueba.run \\
        --kwargs '{"dry_run": true}'

Ejecución real (requiere token de confirmación):

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.members.setup.wipe_socios_prueba.run \\
        --kwargs '{"dry_run": false, "confirm": "WIPE_SOCIOS_PRUEBA"}'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import frappe
from frappe import _

CONFIRM_TOKEN = "WIPE_SOCIOS_PRUEBA"

SOCIO_DOCTYPE = "Socio"
CUSTOMER_DOCTYPE = "Customer"
SALES_INVOICE_DOCTYPE = "Sales Invoice"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
SUBSCRIPTION_DOCTYPE = "Subscription"


@dataclass
class WipeStats:
	socios: int = 0
	payment_entries: int = 0
	sales_invoices: int = 0
	subscriptions: int = 0
	cargo_socio: int = 0
	inscripciones: int = 0
	solicitudes: int = 0
	grupos_familiares: int = 0
	tutores_no_socio: int = 0
	customers: int = 0
	users: int = 0
	errors: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"socios": self.socios,
			"payment_entries": self.payment_entries,
			"sales_invoices": self.sales_invoices,
			"subscriptions": self.subscriptions,
			"cargo_socio": self.cargo_socio,
			"inscripciones": self.inscripciones,
			"solicitudes": self.solicitudes,
			"grupos_familiares": self.grupos_familiares,
			"tutores_no_socio": self.tutores_no_socio,
			"customers": self.customers,
			"users": self.users,
			"errors": self.errors,
		}


def run(*, dry_run: bool = True, confirm: str = "") -> dict[str, Any]:
	if not dry_run and confirm != CONFIRM_TOKEN:
		frappe.throw(
			_(
				"Para borrar datos reales pase confirm='{0}' y dry_run=false."
			).format(CONFIRM_TOKEN)
		)

	stats = wipe_socios_prueba(dry_run=dry_run)
	_print_resumen(stats, dry_run=dry_run)
	if not dry_run:
		frappe.db.commit()
	return stats.to_dict()


def wipe_socios_prueba(*, dry_run: bool = True) -> WipeStats:
	stats = WipeStats()
	socio_names = frappe.get_all(SOCIO_DOCTYPE, pluck="name")
	stats.socios = len(socio_names)

	if not socio_names:
		return stats

	customer_names = _linked_customers(socio_names)
	pe_names = _payment_entries_for_socios(socio_names, customer_names)
	si_names = _sales_invoices_for_socios(socio_names, customer_names)
	sub_names = _subscriptions_for_customers(customer_names)

	stats.payment_entries = len(pe_names)
	stats.sales_invoices = len(si_names)
	stats.subscriptions = len(sub_names)
	stats.cargo_socio = _count_doctype("Cargo Socio")
	stats.inscripciones = _count_doctype("Inscripcion Actividad", {"socio": ["in", socio_names]})
	stats.solicitudes = _count_doctype("Solicitud Asociacion")
	stats.grupos_familiares = _count_doctype("Grupo Familiar")
	stats.tutores_no_socio = _count_doctype("Tutor No Socio")
	stats.customers = len(customer_names)
	stats.users = len(_portal_users_for_socios(socio_names))

	if dry_run:
		return stats

	frappe.db.rollback()
	_delete_docs(PAYMENT_ENTRY_DOCTYPE, pe_names, stats)
	_delete_docs(SALES_INVOICE_DOCTYPE, si_names, stats)
	_delete_docs(SUBSCRIPTION_DOCTYPE, sub_names, stats)
	_delete_all_cargo_socio(stats)
	_delete_all(
		"Inscripcion Actividad",
		stats,
		field="inscripciones",
		filters={"socio": ["in", socio_names]},
	)
	_delete_all("Solicitud Asociacion", stats, field="solicitudes")
	_delete_all("Grupo Familiar", stats, field="grupos_familiares")
	_delete_all("Tutor No Socio", stats, field="tutores_no_socio")
	_delete_docs(CUSTOMER_DOCTYPE, customer_names, stats)
	_delete_portal_users(socio_names, stats)
	_delete_docs(SOCIO_DOCTYPE, socio_names, stats)
	return stats


def _count_doctype(doctype: str, filters: dict[str, Any] | None = None) -> int:
	if not frappe.db.exists("DocType", doctype):
		return 0
	return frappe.db.count(doctype, filters or {})


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _linked_customers(socio_names: list[str]) -> list[str]:
	if not frappe.db.exists("DocType", CUSTOMER_DOCTYPE):
		return []
	if not _has_field(CUSTOMER_DOCTYPE, "socio"):
		return []
	return frappe.get_all(
		CUSTOMER_DOCTYPE,
		filters={"socio": ["in", socio_names]},
		pluck="name",
	)


def _sales_invoices_for_socios(
	socio_names: list[str],
	customer_names: list[str],
) -> list[str]:
	if not frappe.db.exists("DocType", SALES_INVOICE_DOCTYPE):
		return []
	names: set[str] = set()
	if _has_field(SALES_INVOICE_DOCTYPE, "socio"):
		names.update(
			frappe.get_all(
				SALES_INVOICE_DOCTYPE,
				filters={"socio": ["in", socio_names]},
				pluck="name",
			)
		)
	if customer_names:
		names.update(
			frappe.get_all(
				SALES_INVOICE_DOCTYPE,
				filters={"customer": ["in", customer_names]},
				pluck="name",
			)
		)
	return sorted(names)


def _payment_entries_for_socios(
	socio_names: list[str],
	customer_names: list[str],
) -> list[str]:
	if not frappe.db.exists("DocType", PAYMENT_ENTRY_DOCTYPE):
		return []
	si_names = _sales_invoices_for_socios(socio_names, customer_names)
	if not si_names:
		return []
	return frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", si_names],
		},
		pluck="parent",
		distinct=True,
	)


def _subscriptions_for_customers(customer_names: list[str]) -> list[str]:
	if not customer_names or not frappe.db.exists("DocType", SUBSCRIPTION_DOCTYPE):
		return []
	return frappe.get_all(
		SUBSCRIPTION_DOCTYPE,
		filters={"party_type": "Customer", "party": ["in", customer_names]},
		pluck="name",
	)


def _portal_users_for_socios(socio_names: list[str]) -> list[str]:
	users = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names], "user": ["is", "set"]},
		pluck="user",
	)
	return [u for u in users if u and u != "Administrator"]


def _delete_all_cargo_socio(stats: WipeStats) -> None:
	"""Borra cargos extra; los facturados se eliminan por SQL (reset de prueba)."""
	if not frappe.db.exists("DocType", "Cargo Socio"):
		return
	names = frappe.get_all("Cargo Socio", pluck="name")
	stats.cargo_socio = len(names)
	for name in names:
		try:
			if not frappe.db.exists("Cargo Socio", name):
				continue
			frappe.delete_doc("Cargo Socio", name, force=True, ignore_permissions=True)
		except Exception:
			frappe.db.rollback()
			try:
				frappe.db.set_value("Cargo Socio", name, "estado", "Cancelado", update_modified=False)
				frappe.db.set_value("Cargo Socio", name, "sales_invoice", None, update_modified=False)
				frappe.db.delete("Cargo Socio", {"name": name})
			except Exception as exc:  # noqa: BLE001
				stats.errors.append(f"Cargo Socio {name}: {exc}")


def _delete_all(
	doctype: str,
	stats: WipeStats,
	*,
	field: str,
	filters: dict[str, Any] | None = None,
) -> None:
	if not frappe.db.exists("DocType", doctype):
		return
	names = frappe.get_all(doctype, filters=filters or {}, pluck="name")
	_delete_docs(doctype, names, stats)
	setattr(stats, field, len(names))


def _delete_docs(doctype: str, names: list[str], stats: WipeStats) -> None:
	for name in names:
		try:
			if not frappe.db.exists(doctype, name):
				continue
			doc = frappe.get_doc(doctype, name)
			if getattr(doc, "docstatus", 0) == 1:
				if doctype in (PAYMENT_ENTRY_DOCTYPE, SALES_INVOICE_DOCTYPE):
					_hard_delete_erpnext_voucher(doctype, name)
					continue
				try:
					doc.cancel()
				except Exception:
					frappe.db.rollback()
					_hard_delete_erpnext_voucher(doctype, name)
					continue
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		except Exception as exc:  # noqa: BLE001 — reset masivo: continuar
			frappe.db.rollback()
			stats.errors.append(f"{doctype} {name}: {exc}")


def _hard_delete_erpnext_voucher(doctype: str, name: str) -> None:
	"""Borrado directo de vouchers contables (solo reset de datos de prueba)."""
	if doctype == SALES_INVOICE_DOCTYPE:
		frappe.db.delete("Sales Invoice Item", {"parent": name})
	if doctype == PAYMENT_ENTRY_DOCTYPE:
		frappe.db.delete("Payment Entry Reference", {"parent": name})
		frappe.db.delete("Payment Entry Deduction", {"parent": name})

	frappe.db.sql(
		'DELETE FROM "tabGL Entry" WHERE voucher_type = %s AND voucher_no = %s',
		(doctype, name),
	)
	if frappe.db.table_exists("Payment Ledger Entry"):
		frappe.db.sql(
			"""
			DELETE FROM "tabPayment Ledger Entry"
			WHERE voucher_type = %s AND voucher_no = %s
			""",
			(doctype, name),
		)
	frappe.db.delete(doctype, {"name": name})


def _delete_portal_users(socio_names: list[str], stats: WipeStats) -> None:
	for user in _portal_users_for_socios(socio_names):
		try:
			if frappe.db.exists("User", user):
				frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		except Exception as exc:  # noqa: BLE001
			stats.errors.append(f"User {user}: {exc}")


def _print_resumen(stats: WipeStats, *, dry_run: bool = True) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "BORRADO EJECUTADO"
	print("\n" + "=" * 72)
	print(f" RESET SOCIOS PRUEBA — {mode}")
	print("=" * 72)
	for label, value in stats.to_dict().items():
		if label == "errors":
			continue
		print(f" {label:20s}: {value}")
	if stats.errors:
		print("-" * 72)
		print(" Errores:")
		for err in stats.errors[:20]:
			print(f"   - {err}")
		if len(stats.errors) > 20:
			print(f"   ... y {len(stats.errors) - 20} más")
	print("=" * 72 + "\n")

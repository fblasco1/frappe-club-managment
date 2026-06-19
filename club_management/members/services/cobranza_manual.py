"""Cobranza manual en Desk (sin gateway de pagos)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, today

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	resolve_item_arancel_inscripcion,
)
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
	reactivar_socio,
)

SOCIO_DOCTYPE = "Socio"
CUSTOMER_DOCTYPE = "Customer"
SALES_INVOICE_DOCTYPE = "Sales Invoice"


def erpnext_cobranza_disponible() -> bool:
	return bool(frappe.db.exists("DocType", SALES_INVOICE_DOCTYPE))


def _campo_socio_en(doctype: str) -> str | None:
	for fieldname in ("socio", "custom_socio"):
		if frappe.get_meta(doctype).has_field(fieldname):
			return fieldname
	return None


def get_club_settings() -> frappe._dict:
	return frappe.get_single("Club Settings")


def resolve_cuota_social(socio_name: str) -> tuple[float, str | None]:
	"""Devuelve `(monto, item_code)` de cuota social según categoría del socio."""
	socio = frappe.get_doc(SOCIO_DOCTYPE, socio_name)
	if socio.categoria == "Vitalicio":
		return 0.0, None

	settings = get_club_settings()
	for row in settings.cuotas_categoria or []:
		if row.categoria == socio.categoria:
			item = row.item or settings.item_cuota_social
			return flt(row.monto), item
	return 0.0, settings.item_cuota_social


def ensure_customer_for_socio(socio_name: str, *, skip_permission_check: bool = False) -> str:
	"""Crea o devuelve el `Customer` ERPNext del socio."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	if not skip_permission_check:
		ensure_secretaria_operacion_access()
	socio = frappe.get_doc(SOCIO_DOCTYPE, socio_name)
	campo = _campo_socio_en(CUSTOMER_DOCTYPE)
	if not campo:
		frappe.throw(_("Falta el campo Socio en Customer (ejecute migrate)."), frappe.ValidationError)

	existing = frappe.db.get_value(CUSTOMER_DOCTYPE, {campo: socio_name}, "name")
	if existing:
		return existing

	customer = frappe.get_doc(
		{
			"doctype": CUSTOMER_DOCTYPE,
			"customer_name": f"{socio.apellido}, {socio.nombre} ({socio.name})",
			"customer_type": "Individual",
			"customer_group": frappe.db.get_single_value("Selling Settings", "customer_group")
			or "Individual",
			"territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
			campo: socio_name,
		}
	)
	customer.insert(ignore_permissions=True)
	return customer.name


def _default_company() -> str:
	settings = get_club_settings()
	if settings.company:
		return settings.company
	company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(_("Configure una Empresa en Club Settings."), frappe.ValidationError)
	return company


def _cargos_extra_items_for_socio(
	socio_name: str,
	*,
	reference_date: str | None = None,
) -> list[dict[str, Any]]:
	"""Cargos recurrentes vigentes (`Cargo Socio`); vacío si el DocType no existe."""
	if not frappe.db.exists("DocType", "Cargo Socio"):
		return []
	from frappe.utils import getdate, today

	hoy = getdate(reference_date or today())
	rows = frappe.get_all(
		"Cargo Socio",
		filters={
			"socio": socio_name,
			"modo_cobro": "Recurrente",
			"estado": "Pendiente",
			"fecha_desde": ["<=", hoy],
		},
		fields=["titulo", "item", "monto", "fecha_hasta"],
	)
	items: list[dict[str, Any]] = []
	for row in rows:
		if row.fecha_hasta and getdate(row.fecha_hasta) < hoy:
			continue
		if not row.item or flt(row.monto) <= 0:
			continue
		items.append(
			{
				"item_code": row.item,
				"qty": 1,
				"rate": flt(row.monto),
				"description": row.titulo or _("Cargo extra"),
			}
		)
	return items


def build_invoice_items_for_socio(
	socio_name: str,
	*,
	incluir_actividades: bool = True,
	incluir_cargos_extra: bool = False,
	reference_date: str | None = None,
) -> list[dict[str, Any]]:
	"""Líneas de factura: cuota social, aranceles activos y cargos extra opcionales."""
	items: list[dict[str, Any]] = []
	monto, item_cuota = resolve_cuota_social(socio_name)
	if monto > 0 and item_cuota:
		items.append(
			{
				"item_code": item_cuota,
				"qty": 1,
				"rate": monto,
				"description": _("Cuota social"),
			}
		)

	if incluir_actividades:
		for ins in frappe.get_all(
			INSCRIPCION_DOCTYPE,
			filters={"socio": socio_name, "estado": "Activa"},
			pluck="name",
		):
			item_code = resolve_item_arancel_inscripcion(ins)
			if not item_code:
				continue
			items.append(
				{
					"item_code": item_code,
					"qty": 1,
					"rate": frappe.db.get_value(
						"Item Price", {"item_code": item_code}, "price_list_rate"
					)
					or frappe.db.get_value("Item", item_code, "standard_rate")
					or 0,
					"description": _("Arancel actividad"),
				}
			)

	if incluir_cargos_extra:
		items.extend(
			_cargos_extra_items_for_socio(socio_name, reference_date=reference_date)
		)
	return items


def generar_cargo_socio(
	socio_name: str,
	*,
	incluir_actividades: bool = True,
) -> str:
	"""Genera y submittea una `Sales Invoice` para el socio."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	customer = ensure_customer_for_socio(socio_name)
	invoice_items = build_invoice_items_for_socio(
		socio_name, incluir_actividades=incluir_actividades
	)
	if not invoice_items:
		frappe.throw(_("No hay conceptos para facturar."), frappe.ValidationError)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Falta el campo Socio en Sales Invoice (ejecute migrate)."), frappe.ValidationError)

	invoice = frappe.get_doc(
		{
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": customer,
			"company": _default_company(),
			"posting_date": today(),
			"due_date": today(),
			campo_socio: socio_name,
			"items": invoice_items,
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	sync_saldo_deuda_socio(socio_name)
	return invoice.name


def sync_saldo_deuda_socio(socio_name: str) -> float:
	"""Actualiza `Socio.saldo_deuda` desde facturas ERPNext pendientes."""
	if not erpnext_cobranza_disponible():
		return 0.0

	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo:
		return flt(frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "saldo_deuda"))

	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo: socio_name, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["outstanding_amount"],
	)
	total = sum(flt(row.outstanding_amount) for row in rows)
	frappe.db.set_value(SOCIO_DOCTYPE, socio_name, "saldo_deuda", total, update_modified=True)
	return total


def list_facturas_pendientes_socio(socio_name: str) -> list[dict[str, Any]]:
	"""Facturas submitteadas con saldo pendiente vinculadas al socio."""
	if not erpnext_cobranza_disponible():
		return []

	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo:
		return []

	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo: socio_name, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "posting_date", "outstanding_amount", "grand_total"],
		order_by="posting_date desc",
	)


def registrar_cobro_manual(socio_name: str, sales_invoice_name: str) -> str:
	"""Registra un `Payment Entry` contra la factura y actualiza deuda/estado."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice_name)
	if campo and invoice.get(campo) != socio_name:
		frappe.throw(_("La factura no pertenece a este socio."), frappe.ValidationError)

	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("La factura no tiene saldo pendiente."), frappe.ValidationError)

	try:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	except ImportError as exc:
		raise frappe.ValidationError(_("ERPNext no está disponible para cobranza.")) from exc

	pe = get_payment_entry(SALES_INVOICE_DOCTYPE, sales_invoice_name)
	# Cobro manual en Secretaría: efectivo en caja (evita exigir referencia bancaria).
	pe.mode_of_payment = "Cash"
	if not pe.reference_no:
		pe.reference_no = sales_invoice_name
	if not pe.reference_date:
		pe.reference_date = today()
	pe.insert(ignore_permissions=True)
	pe.submit()

	saldo = sync_saldo_deuda_socio(socio_name)
	if saldo <= 0 and frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado") == "Moroso":
		reactivar_socio(socio_name, motivo=f"Cobro manual {pe.name}")

	return pe.name


def get_ultima_fecha_pago_socio(socio_name: str) -> str | None:
	"""Última posting_date de Payment Entry submitted contra facturas del socio."""
	if not socio_name or not erpnext_cobranza_disponible():
		return None

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return None

	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_socio: socio_name, "docstatus": 1},
		pluck="name",
	)
	if not invoices:
		return None

	pe_names = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", invoices],
			"parenttype": "Payment Entry",
		},
		pluck="parent",
		distinct=True,
	)
	if not pe_names:
		return None

	last_row = frappe.get_all(
		"Payment Entry",
		filters={"name": ["in", pe_names], "docstatus": 1},
		fields=["posting_date"],
		order_by="posting_date desc",
		limit=1,
	)
	if not last_row:
		return None
	return str(last_row[0].posting_date)

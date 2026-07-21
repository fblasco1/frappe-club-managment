"""Cobranza manual en Desk (sin gateway de pagos)."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	resolve_monto_arancel_inscripcion,
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


def format_periodo_cobro(reference_date: str | date) -> str:
	d = getdate(reference_date)
	return d.strftime("%m/%Y")


def _campo_periodo_cobro() -> str | None:
	for fieldname in ("periodo_cobro", "custom_periodo_cobro"):
		if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field(fieldname):
			return fieldname
	return None


def factura_periodo_existe(socio_name: str, periodo_cobro: str) -> bool:
	"""True si ya hay factura del período mensual para el socio."""
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return False

	filters: dict[str, Any] = {campo_socio: socio_name, "docstatus": ["!=", 2]}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo_cobro
	else:
		filters["remarks"] = ["like", f"%cuota mensual {periodo_cobro}%"]
	return bool(frappe.db.exists(SALES_INVOICE_DOCTYPE, filters))


def item_codes_facturados_en_periodo(socio_name: str, periodo_cobro: str) -> set[str]:
	"""Ítems de cuota/aranceles ya facturados en el período (facturas no canceladas)."""
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return set()

	filters: dict[str, Any] = {campo_socio: socio_name, "docstatus": ["!=", 2]}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo_cobro
	else:
		filters["remarks"] = ["like", f"%cuota mensual {periodo_cobro}%"]

	invoice_names = frappe.get_all(SALES_INVOICE_DOCTYPE, filters=filters, pluck="name")
	codes: set[str] = set()
	for invoice_name in invoice_names:
		for item_code in frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": invoice_name},
			pluck="item_code",
		):
			if item_code:
				codes.add(item_code)
	return codes


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
	solo_aranceles: bool = False,
	reference_date: str | None = None,
	periodo_cobro: str | None = None,
	excluir_ya_facturados: bool = True,
) -> list[dict[str, Any]]:
	"""Líneas de factura: cuota social, aranceles activos y cargos extra opcionales."""
	ref = reference_date or today()
	periodo = periodo_cobro or format_periodo_cobro(ref)
	ya_facturados = (
		item_codes_facturados_en_periodo(socio_name, periodo) if excluir_ya_facturados else set()
	)

	items: list[dict[str, Any]] = []
	seen: set[str] = set()

	def _append_item(item_code: str, rate: float, description: str) -> None:
		if not item_code or flt(rate) <= 0:
			return
		if item_code in ya_facturados or item_code in seen:
			return
		seen.add(item_code)
		items.append(
			{
				"item_code": item_code,
				"qty": 1,
				"rate": flt(rate),
				"description": description,
			}
		)

	beca = None
	try:
		from club_management.members.services.beca_socio import beca_vigente_socio

		beca = beca_vigente_socio(socio_name, reference_date=ref)
	except Exception:
		beca = None
	if not solo_aranceles:
		monto, item_cuota = resolve_cuota_social(socio_name)
		if monto > 0 and item_cuota:
			rate_cuota = beca.rate_cuota(monto) if beca else monto
			_append_item(item_cuota, rate_cuota, _("Cuota social"))

	if incluir_actividades:
		for ins in frappe.get_all(
			INSCRIPCION_DOCTYPE,
			filters={"socio": socio_name, "estado": "Activa"},
			pluck="name",
		):
			item_code, monto = resolve_monto_arancel_inscripcion(ins)
			if item_code:
				if beca and beca.exime_arancel:
					continue
				rate_arancel = beca.rate_arancel(monto) if beca else monto
				_append_item(item_code, rate_arancel, _("Arancel actividad"))

	if incluir_cargos_extra:
		for row in _cargos_extra_items_for_socio(socio_name, reference_date=reference_date):
			_append_item(row["item_code"], row["rate"], row.get("description") or _("Cargo extra"))
	return items


def generar_cargo_socio(
	socio_name: str,
	*,
	incluir_actividades: bool = True,
	incluir_cargos_extra: bool | None = None,
	reference_date: str | date | None = None,
) -> str:
	"""Genera y submittea una `Sales Invoice` mensual para el socio (Secretaría)."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	if factura_periodo_existe(socio_name, periodo):
		frappe.throw(
			_("Ya existe deuda mensual para el período {0}. Use «Registrar cobro» o espere al próximo mes.").format(
				periodo
			),
			frappe.ValidationError,
		)

	settings = get_club_settings()
	if incluir_cargos_extra is None:
		incluir_cargos_extra = bool(settings.incluir_cargos_extra_en_deuda_mensual)
	customer = ensure_customer_for_socio(socio_name)
	invoice_items = build_invoice_items_for_socio(
		socio_name,
		incluir_actividades=incluir_actividades,
		incluir_cargos_extra=incluir_cargos_extra,
		reference_date=str(ref),
		periodo_cobro=periodo,
	)
	if not invoice_items:
		frappe.throw(
			_("No hay conceptos pendientes de facturar para {0} (cuota/aranceles ya cargados este mes).").format(
				periodo
			),
			frappe.ValidationError,
		)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Falta el campo Socio en Sales Invoice (ejecute migrate)."), frappe.ValidationError)

	from club_management.members.services.cobranza_periodica import resolve_fechas_factura_mensual

	posting, due = resolve_fechas_factura_mensual(
		ref,
		int(settings.dia_primer_vencimiento or 10),
	)

	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": customer,
		"company": _default_company(),
		"posting_date": posting,
		"due_date": due,
		campo_socio: socio_name,
		"remarks": _("Cuota mensual {0}").format(periodo),
		"items": invoice_items,
	}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		payload[campo_periodo] = periodo

	invoice = frappe.get_doc(payload)
	apply_patch()
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
	frappe.db.set_value(SOCIO_DOCTYPE, socio_name, "saldo_deuda", total, update_modified=False)
	return total


def _lineas_factura_pendiente(invoice_name: str) -> list[dict[str, Any]]:
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		fields=["item_code", "description", "amount"],
		order_by="`tabSales Invoice Item`.idx asc",
	)
	lineas: list[dict[str, Any]] = []
	for row in rows:
		concepto = (row.description or row.item_code or "").strip()
		lineas.append(
			{
				"concepto": concepto or _("Concepto"),
				"item_code": row.item_code,
				"monto": flt(row.amount),
			}
		)
	return lineas


def _cargos_extra_pendientes_socio(socio_name: str) -> list[dict[str, Any]]:
	"""Cargos extra aún no facturados (únicos pendientes o recurrentes vigentes)."""
	if not frappe.db.exists("DocType", "Cargo Socio"):
		return []

	from frappe.utils import getdate, today

	hoy = getdate(today())
	rows = frappe.get_all(
		"Cargo Socio",
		filters={"socio": socio_name, "estado": "Pendiente"},
		fields=["name", "titulo", "modo_cobro", "monto", "fecha_desde", "fecha_hasta"],
		order_by="fecha_desde asc, modified desc",
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		if row.modo_cobro == "Recurrente":
			if row.fecha_desde and getdate(row.fecha_desde) > hoy:
				continue
			if row.fecha_hasta and getdate(row.fecha_hasta) < hoy:
				continue
		result.append(
			{
				"name": row.name,
				"titulo": row.titulo or _("Cargo extra"),
				"modo_cobro": row.modo_cobro,
				"monto": flt(row.monto),
				"fecha_desde": row.fecha_desde,
				"fecha_hasta": row.fecha_hasta,
			}
		)
	return result


def get_detalle_deuda_socio(socio_name: str) -> dict[str, Any]:
	"""Saldo impago y desglose por facturas / cargos extra pendientes."""
	saldo = sync_saldo_deuda_socio(socio_name)
	facturas: list[dict[str, Any]] = []
	for row in list_facturas_pendientes_socio(socio_name):
		facturas.append(
			{
				**row,
				"lineas": _lineas_factura_pendiente(row["name"]),
			}
		)
	return {
		"saldo_deuda": saldo,
		"facturas": facturas,
		"cargos_pendientes": _cargos_extra_pendientes_socio(socio_name),
	}


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




def list_facturas_impagas_cancelables_socio(socio_name: str) -> list[dict[str, Any]]:
	"""Facturas submitted del socio sin cobros (outstanding = grand_total)."""
	rows = list_facturas_pendientes_socio(socio_name)
	return [
		row
		for row in rows
		if flt(row.get("outstanding_amount")) == flt(row.get("grand_total"))
		and flt(row.get("grand_total")) > 0
	]


def cancelar_factura_venta_impaga(socio_name: str, sales_invoice_name: str) -> dict[str, Any]:
	"""Cancela una Sales Invoice del socio solo si está totalmente impaga."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	if not socio_name or not sales_invoice_name:
		frappe.throw(_("Socio y factura son obligatorios."), frappe.ValidationError)

	if not frappe.db.exists(SALES_INVOICE_DOCTYPE, sales_invoice_name):
		frappe.throw(_("Factura no encontrada."), frappe.DoesNotExistError)

	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice_name)

	if campo and invoice.get(campo) != socio_name:
		frappe.throw(_("La factura no pertenece a este socio."), frappe.ValidationError)

	if invoice.docstatus != 1:
		frappe.throw(_("Solo se pueden cancelar facturas presentadas."), frappe.ValidationError)

	outstanding = flt(invoice.outstanding_amount)
	grand_total = flt(invoice.grand_total)
	if outstanding <= 0 or outstanding != grand_total:
		frappe.throw(
			_("Solo se pueden cancelar facturas totalmente impagas (sin cobros)."),
			frappe.ValidationError,
		)

	invoice.flags.ignore_permissions = True
	invoice.cancel()
	saldo = sync_saldo_deuda_socio(socio_name)
	return {"status": "ok", "sales_invoice": sales_invoice_name, "saldo_deuda": saldo}


def registrar_cobro_manual(
	socio_name: str,
	sales_invoice_name: str,
	*,
	mode_of_payment: str | None = None,
	posting_date: str | date | None = None,
) -> str:
	"""Registra un `Payment Entry` contra la factura y actualiza deuda/estado."""
	from club_management.integrations.payment_ledger_postgres import apply_patch
	from club_management.members.services.modos_pago_desk import validar_modo_pago_desk

	apply_patch()
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

	fecha_cobro = getdate(posting_date or today())
	if fecha_cobro > getdate(today()):
		frappe.throw(_("La fecha de cobro no puede ser posterior a hoy."), frappe.ValidationError)

	pe = get_payment_entry(SALES_INVOICE_DOCTYPE, sales_invoice_name)
	pe.mode_of_payment = validar_modo_pago_desk(mode_of_payment)
	pe.posting_date = fecha_cobro
	if not pe.reference_no:
		pe.reference_no = sales_invoice_name
	pe.reference_date = fecha_cobro
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

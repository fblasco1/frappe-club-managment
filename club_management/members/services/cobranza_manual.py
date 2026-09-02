"""Cobranza manual en Desk (sin gateway de pagos)."""

from __future__ import annotations

import re
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

# Ítems compartidos por varios cargos extra (dedup por título + período, no solo item_code).
ITEMS_CARGO_EXTRA_POR_TITULO = frozenset({"ICDPE-CARGO-VARIOS"})


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


def reference_date_desde_periodo(periodo: str) -> date:
	"""Convierte `MM/YYYY` al día 1 de ese mes."""
	from club_management.members.services.mora_al_cobro import parse_periodo_cobro

	parsed = parse_periodo_cobro(periodo)
	if not parsed:
		frappe.throw(
			_("Período inválido: {0}. Usá MM/YYYY.").format(periodo),
			frappe.ValidationError,
		)
	return parsed


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


def _normalize_cargo_text(text: str) -> str:
	return re.sub(r"\s+", " ", (text or "").strip()).upper()


def item_usa_deduplicacion_por_titulo(item_code: str) -> bool:
	return item_code in ITEMS_CARGO_EXTRA_POR_TITULO


def cargo_extra_linea_facturada_en_periodo(
	socio_name: str,
	periodo_cobro: str,
	titulo: str,
) -> bool:
	"""True si ya hay línea de SI del período para ese título de cargo extra."""
	if not (titulo or "").strip():
		return False

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return False

	filters: dict[str, Any] = {campo_socio: socio_name, "docstatus": ["!=", 2]}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo_cobro
	else:
		filters["remarks"] = ["like", f"%{periodo_cobro}%"]

	from club_management.scripts.informe_concepto_cobranza import (
		cuotas_complementarias_equivalentes,
		es_cuota_complementaria,
	)

	usar_fuzzy_cto = es_cuota_complementaria(titulo)
	titulo_norm = _normalize_cargo_text(titulo)
	sufijo = f"({periodo_cobro})".upper()

	for invoice_name in frappe.get_all(SALES_INVOICE_DOCTYPE, filters=filters, pluck="name"):
		for desc in frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": invoice_name},
			pluck="description",
		):
			if not desc:
				continue
			if usar_fuzzy_cto:
				if cuotas_complementarias_equivalentes(titulo, desc):
					return True
				continue
			desc_norm = _normalize_cargo_text(desc)
			if desc_norm in {f"{titulo_norm} {sufijo}", f"{titulo_norm}{sufijo}"}:
				return True
			if desc_norm.endswith(sufijo) and desc_norm.startswith(titulo_norm):
				return True
			if desc_norm == titulo_norm:
				return True
	return False


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


def resolve_cost_center_item(item_code: str, company: str | None = None) -> str | None:
	"""Centro de costo del ítem según `Item Default.selling_cost_center`.

	Los ingresos por arancel de actividad deben imputar al centro de costo de la
	actividad (definido en el ítem), no al de la empresa. Devuelve `None` si el
	ítem no define un centro de costo (ERPNext resuelve el default).
	"""
	if not item_code:
		return None
	company = company or _default_company()
	return (
		frappe.db.get_value(
			"Item Default",
			{"parent": item_code, "company": company},
			"selling_cost_center",
		)
		or None
	)


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

	company = _default_company()
	items: list[dict[str, Any]] = []
	seen: set[str | tuple[str, str]] = set()

	def _append_item(item_code: str, rate: float, description: str) -> None:
		if not item_code or flt(rate) <= 0:
			return
		if item_code in ya_facturados or item_code in seen:
			return
		seen.add(item_code)
		linea: dict[str, Any] = {
			"item_code": item_code,
			"qty": 1,
			"rate": flt(rate),
			"description": description,
		}
		cost_center = resolve_cost_center_item(item_code, company)
		if cost_center:
			linea["cost_center"] = cost_center
		items.append(linea)

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
			item_code = row["item_code"]
			titulo = row.get("description") or ""
			rate = flt(row["rate"])
			if not item_code or rate <= 0:
				continue
			if excluir_ya_facturados and item_usa_deduplicacion_por_titulo(item_code):
				if cargo_extra_linea_facturada_en_periodo(socio_name, periodo, titulo):
					continue
			elif excluir_ya_facturados and item_code in ya_facturados:
				continue
			seen_key: str | tuple[str, str] = (
				(item_code, _normalize_cargo_text(titulo))
				if item_usa_deduplicacion_por_titulo(item_code)
				else item_code
			)
			if seen_key in seen:
				continue
			seen.add(seen_key)
			linea = {
				"item_code": item_code,
				"qty": 1,
				"rate": rate,
				"description": titulo or _("Cargo extra"),
			}
			cost_center = resolve_cost_center_item(item_code, company)
			if cost_center:
				linea["cost_center"] = cost_center
			items.append(linea)
	return items


def _submit_sales_invoice_concepto(
	*,
	socio_name: str,
	customer: str,
	campo_socio: str,
	periodo: str,
	posting: str | date,
	due: str | date,
	item: dict[str, Any],
) -> str:
	"""Crea y submittea una SI con una sola línea de concepto."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	concepto = (item.get("description") or item.get("item_code") or _("Concepto")).strip()
	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": customer,
		"company": _default_company(),
		"posting_date": posting,
		"due_date": due,
		campo_socio: socio_name,
		"remarks": _("{0} — {1}").format(concepto, periodo),
		"items": [item],
	}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		payload[campo_periodo] = periodo

	invoice = frappe.get_doc(payload)
	apply_patch()
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	return invoice.name


def generar_cargo_socio(
	socio_name: str,
	*,
	incluir_actividades: bool = True,
	incluir_cargos_extra: bool | None = None,
	reference_date: str | date | None = None,
) -> list[str]:
	"""Genera y submittea una `Sales Invoice` por cada concepto pendiente (Secretaría)."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)

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

	created: list[str] = []
	for item in invoice_items:
		created.append(
			_submit_sales_invoice_concepto(
				socio_name=socio_name,
				customer=customer,
				campo_socio=campo_socio,
				periodo=periodo,
				posting=posting,
				due=due,
				item=item,
			)
		)
	sync_saldo_deuda_socio(socio_name)
	return created

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
	"""Líneas aún impagas: descuenta cobros por concepto del comprobante (no prorratea)."""
	from club_management.scripts.informe_concepto_cobranza import _cobros_imputados_por_linea

	lineas: list[dict[str, Any]] = []
	for row in _cobros_imputados_por_linea(invoice_name):
		restante = flt(row.get("restante"), 2)
		if restante <= 0.005:
			continue
		concepto = (row.get("description") or row.get("item_code") or "").strip()
		lineas.append(
			{
				"concepto": concepto or _("Concepto"),
				"item_code": row.get("item_code"),
				"monto": restante,
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

	campo_periodo = _campo_periodo_cobro()
	fields = ["name", "posting_date", "outstanding_amount", "grand_total", "remarks"]
	if campo_periodo:
		fields.append(campo_periodo)

	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo: socio_name, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=fields,
		order_by="posting_date desc, name asc",
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		lineas = _lineas_factura_pendiente(row.name)
		concepto = (lineas[0]["concepto"] if lineas else None) or (row.remarks or row.name)
		periodo = ""
		if campo_periodo:
			periodo = (row.get(campo_periodo) or "").strip()
		result.append(
			{
				"name": row.name,
				"posting_date": row.posting_date,
				"outstanding_amount": flt(row.outstanding_amount),
				"grand_total": flt(row.grand_total),
				"remarks": row.remarks,
				"concepto": concepto,
				"periodo_cobro": periodo,
			}
		)
	from club_management.members.services.mora_al_cobro import _periodo_sort_key

	result.sort(key=lambda r: (_periodo_sort_key(r.get("periodo_cobro")), r.get("name") or ""))
	return result


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


def _reference_no_cobro(invoice_names: list[str], *, max_len: int = 140) -> str:
	"""`reference_no` de Payment Entry es Data(140); no listar todas las SI si no entran."""
	names = [str(n).strip() for n in invoice_names if str(n).strip()]
	if not names:
		return ""
	if len(names) == 1:
		return names[0][:max_len]
	joined = ", ".join(names)
	if len(joined) <= max_len:
		return joined
	# Resumen corto: primera SI + conteo.
	suffix = _(" (+{0} facturas)").format(len(names) - 1)
	budget = max_len - len(suffix)
	head = names[0][: max(0, budget)]
	return f"{head}{suffix}"[:max_len]


def _payment_entry_para_asignaciones(
	asignaciones: list[tuple[str, float]],
	*,
	mode_of_payment: str,
	posting_date: date,
	reference_no: str | None = None,
	auto_submit: bool = True,
) -> str:
	"""Crea un PE (un medio) con una o más referencias a SI."""
	from club_management.members.services.modos_pago_desk import validar_modo_pago_desk

	try:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	except ImportError as exc:
		raise frappe.ValidationError(_("ERPNext no está disponible para cobranza.")) from exc

	if not asignaciones:
		frappe.throw(_("No hay montos para asignar al cobro."), frappe.ValidationError)

	modo = validar_modo_pago_desk(mode_of_payment)
	first_invoice, first_amount = asignaciones[0]
	pe = get_payment_entry(
		SALES_INVOICE_DOCTYPE,
		first_invoice,
		party_amount=flt(first_amount),
	)
	pe.mode_of_payment = modo
	pe.posting_date = posting_date
	pe.reference_date = posting_date
	pe.set("references", [])
	total = 0.0
	invoice_names: list[str] = []
	for invoice_name, amount in asignaciones:
		amt = flt(amount)
		if amt <= 0:
			continue
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
		pe.append(
			"references",
			{
				"reference_doctype": SALES_INVOICE_DOCTYPE,
				"reference_name": invoice_name,
				"due_date": invoice.due_date,
				"total_amount": flt(invoice.grand_total),
				"outstanding_amount": flt(invoice.outstanding_amount),
				"allocated_amount": amt,
			},
		)
		total += amt
		invoice_names.append(invoice_name)
	if total <= 0:
		frappe.throw(_("El monto del cobro debe ser mayor a cero."), frappe.ValidationError)
	pe.paid_amount = total
	pe.received_amount = total
	if reference_no:
		pe.reference_no = str(reference_no).strip()[:140]
	elif not pe.reference_no:
		pe.reference_no = _reference_no_cobro(invoice_names)
	# Detalle completo fuera del campo Data(140).
	detalle = ", ".join(invoice_names)
	if detalle:
		existente = (pe.remarks or "").strip()
		nota = _("Facturas: {0}").format(detalle)
		pe.remarks = f"{existente}\n{nota}".strip() if existente else nota
	pe.insert(ignore_permissions=True)
	if auto_submit:
		pe.submit()
	return pe.name


def registrar_cobro_compuesto(
	socio_name: str,
	sales_invoices: list[str],
	medios: list[dict[str, Any]],
	*,
	posting_date: str | date | None = None,
	reference_no: str | None = None,
	auto_submit: bool = True,
) -> dict[str, Any]:
	"""Cobra una o más SI enteras con uno o varios medios (simple o mixto)."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	if not socio_name:
		frappe.throw(_("Socio es obligatorio."), frappe.ValidationError)

	invoices = [str(name).strip() for name in (sales_invoices or []) if str(name).strip()]
	if not invoices:
		frappe.throw(_("Seleccioná al menos una factura."), frappe.ValidationError)

	fecha_cobro = getdate(posting_date or today())
	if fecha_cobro > getdate(today()):
		frappe.throw(_("La fecha de cobro no puede ser posterior a hoy."), frappe.ValidationError)

	from club_management.members.services.mora_al_cobro import preparar_facturas_cobro_con_mora

	prep = preparar_facturas_cobro_con_mora(
		socio_name,
		invoices,
		posting_date=fecha_cobro,
	)
	invoices = prep["sales_invoices"]

	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	remaining: dict[str, float] = {}
	for invoice_name in invoices:
		if not frappe.db.exists(SALES_INVOICE_DOCTYPE, invoice_name):
			frappe.throw(_("Factura no encontrada: {0}").format(invoice_name), frappe.DoesNotExistError)
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
		if campo and invoice.get(campo) != socio_name:
			frappe.throw(_("La factura {0} no pertenece a este socio.").format(invoice_name), frappe.ValidationError)
		outstanding = flt(invoice.outstanding_amount)
		if outstanding <= 0:
			frappe.throw(_("La factura {0} no tiene saldo pendiente.").format(invoice_name), frappe.ValidationError)
		remaining[invoice_name] = outstanding

	total_facturas = sum(remaining.values())
	parsed_medios: list[dict[str, Any]] = []
	for row in medios or []:
		amount = flt(row.get("amount"))
		if amount <= 0:
			continue
		parsed_medios.append(
			{
				"mode_of_payment": row.get("mode_of_payment"),
				"amount": amount,
			}
		)
	if not parsed_medios:
		frappe.throw(_("Indicá al menos un medio de pago con monto."), frappe.ValidationError)

	total_medios = sum(flt(row["amount"]) for row in parsed_medios)
	if abs(total_medios - total_facturas) > 0.005:
		frappe.throw(
			_("La suma de medios ({0}) debe coincidir con el total a cobrar ({1}).").format(
				total_medios, total_facturas
			),
			frappe.ValidationError,
		)

	payment_entries: list[str] = []
	for row in parsed_medios:
		left = flt(row["amount"])
		asignaciones: list[tuple[str, float]] = []
		for invoice_name in invoices:
			if left <= 0:
				break
			disponible = remaining.get(invoice_name, 0.0)
			if disponible <= 0:
				continue
			take = min(disponible, left)
			asignaciones.append((invoice_name, take))
			remaining[invoice_name] = flt(disponible - take)
			left = flt(left - take)
		if left > 0.005:
			frappe.throw(_("No se pudo asignar el cobro a las facturas."), frappe.ValidationError)
		pe_name = _payment_entry_para_asignaciones(
			asignaciones,
			mode_of_payment=str(row["mode_of_payment"]),
			posting_date=fecha_cobro,
			reference_no=reference_no,
			auto_submit=auto_submit,
		)
		payment_entries.append(pe_name)

	saldo = sync_saldo_deuda_socio(socio_name)
	if saldo <= 0 and frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado") == "Moroso":
		reactivar_socio(socio_name, motivo=f"Cobro manual {', '.join(payment_entries)}")

	return {
		"status": "ok",
		"payment_entries": payment_entries,
		"saldo_deuda": saldo,
	}


def registrar_cobro_parcial_factura(
	socio_name: str,
	sales_invoice: str,
	amount: float,
	*,
	mode_of_payment: str,
	posting_date: str | date | None = None,
	reference_no: str | None = None,
	auto_submit: bool = True,
) -> dict[str, Any]:
	"""Cobra un monto parcial contra una SI (p. ej. una línea del informe por concepto)."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ensure_secretaria_operacion_access()
	monto = flt(amount, 2)
	if monto <= 0:
		frappe.throw(_("El monto debe ser mayor a cero."), frappe.ValidationError)

	fecha_cobro = getdate(posting_date or today())
	if fecha_cobro > getdate(today()):
		frappe.throw(_("La fecha de cobro no puede ser posterior a hoy."), frappe.ValidationError)

	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not frappe.db.exists(SALES_INVOICE_DOCTYPE, sales_invoice):
		frappe.throw(_("Factura no encontrada: {0}").format(sales_invoice), frappe.DoesNotExistError)

	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice)
	if campo and invoice.get(campo) != socio_name:
		frappe.throw(_("La factura {0} no pertenece a este socio.").format(sales_invoice), frappe.ValidationError)

	outstanding = flt(invoice.outstanding_amount)
	if outstanding <= 0:
		frappe.throw(_("La factura {0} no tiene saldo pendiente.").format(sales_invoice), frappe.ValidationError)
	if monto - outstanding > 0.005:
		frappe.throw(
			_("El monto ({0}) supera el saldo pendiente ({1}).").format(monto, outstanding),
			frappe.ValidationError,
		)

	pe_name = _payment_entry_para_asignaciones(
		[(sales_invoice, monto)],
		mode_of_payment=mode_of_payment,
		posting_date=fecha_cobro,
		reference_no=reference_no,
		auto_submit=auto_submit,
	)
	saldo = sync_saldo_deuda_socio(socio_name)
	return {
		"status": "ok",
		"payment_entries": [pe_name],
		"saldo_deuda": saldo,
	}


def registrar_cobro_manual(
	socio_name: str,
	sales_invoice_name: str,
	*,
	mode_of_payment: str | None = None,
	posting_date: str | date | None = None,
) -> str:
	"""Compat: un PE contra una factura (saldo completo) con un medio."""
	from club_management.members.services.mora_al_cobro import preparar_facturas_cobro_con_mora

	prep = preparar_facturas_cobro_con_mora(
		socio_name,
		[sales_invoice_name],
		posting_date=posting_date,
	)
	result = registrar_cobro_compuesto(
		socio_name,
		prep["sales_invoices"],
		[{"mode_of_payment": mode_of_payment or "Cash", "amount": prep["total_exigido"]}],
		posting_date=posting_date,
	)
	return result["payment_entries"][0]


def get_ultima_fecha_pago_socio(socio_name: str) -> str | None:
	"""Última posting_date de Payment Entry submitted contra facturas del socio."""
	rows = list_historial_pagos_socio(socio_name, limit=1)
	if not rows:
		return None
	return str(rows[0]["posting_date"])


def list_historial_pagos_socio(socio_name: str, *, limit: int = 50) -> list[dict[str, Any]]:
	"""Historial de Payment Entry del socio (más recientes primero)."""
	if not socio_name or not erpnext_cobranza_disponible():
		return []

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []

	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_socio: socio_name, "docstatus": ["in", [1, 2]]},
		pluck="name",
	)
	if not invoices:
		return []

	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", invoices],
			"parenttype": "Payment Entry",
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	if not refs:
		return []

	by_pe: dict[str, list[dict[str, Any]]] = {}
	for row in refs:
		by_pe.setdefault(row.parent, []).append(row)

	pe_rows = frappe.get_all(
		"Payment Entry",
		filters={"name": ["in", list(by_pe.keys())], "docstatus": 1},
		fields=["name", "posting_date", "mode_of_payment", "paid_amount", "received_amount"],
		order_by="posting_date desc, creation desc",
		limit=limit,
	)
	result: list[dict[str, Any]] = []
	for pe in pe_rows:
		ref_rows = by_pe.get(pe.name, [])
		si_names = sorted({r.reference_name for r in ref_rows})
		amount = flt(pe.paid_amount or pe.received_amount)
		result.append(
			{
				"payment_entry": pe.name,
				"posting_date": pe.posting_date,
				"mode_of_payment": pe.mode_of_payment,
				"paid_amount": amount,
				"sales_invoices": si_names,
			}
		)
	return result

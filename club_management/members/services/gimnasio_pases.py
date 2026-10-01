"""Quincena y Entrenamiento por hora del gimnasio para No Socios (spec gimnasio_cobro_socios_no_socios.md)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, formatdate, today

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	GYM_ITEM_CODES,
	GYM_PASES_ITEM_SPECS,
	ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO,
	ITEM_GYM_PASE_DIARIO_LEGACY,
	ITEM_GYM_QUINCENA_NO_SOCIO,
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.members.services.practicante_no_socio import es_no_socio
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)

CARGO_DOCTYPE = "Cargo Socio"
TIPO_QUINCENA = "Quincena Gimnasio"
TIPO_ENTRENAMIENTO_HORA = "Entrenamiento por Hora Gimnasio"
TIPO_PASE_DIARIO_LEGACY = "Pase Diario Gimnasio"
ITEM_POR_TIPO: dict[str, str] = {
	TIPO_QUINCENA: ITEM_GYM_QUINCENA_NO_SOCIO,
	TIPO_ENTRENAMIENTO_HORA: ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO,
}
_TITULO_POR_TIPO: dict[str, str] = {
	TIPO_QUINCENA: "Quincena gimnasio",
	TIPO_ENTRENAMIENTO_HORA: "Entrenamiento por hora gimnasio",
}


def ensure_gimnasio_pases_items() -> None:
	"""Crea/actualiza los ítems de Quincena y Entrenamiento por hora."""
	from club_management.activities.services.deporte_icdpe_items import upsert_arancel_item
	from club_management.setup.icdpe_create_service_items import _ensure_uom

	_ensure_uom("Servicio")
	for spec in GYM_PASES_ITEM_SPECS:
		upsert_arancel_item(spec)


def _precios_oficiales_gimnasio() -> dict[str, float]:
	specs = (*OTRAS_ACTIVIDADES_ITEM_SPECS, *GYM_PASES_ITEM_SPECS)
	return {spec.item_code: flt(spec.rate) for spec in specs if spec.item_code in GYM_ITEM_CODES}


def sincronizar_precios_gimnasio() -> dict[str, float]:
	"""Aplica los precios oficiales a `standard_rate`, `Item Price` y `Subscription Plan` de cada ítem."""
	aplicados: dict[str, float] = {}
	for item_code, rate in _precios_oficiales_gimnasio().items():
		if not frappe.db.exists("Item", item_code):
			continue
		frappe.db.set_value("Item", item_code, "standard_rate", rate, update_modified=False)
		for price in frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name"):
			frappe.db.set_value("Item Price", price, "price_list_rate", rate)
		if frappe.db.exists("DocType", "Subscription Plan"):
			for plan in frappe.get_all("Subscription Plan", filters={"item": item_code}, pluck="name"):
				frappe.db.set_value("Subscription Plan", plan, "cost", rate)
		aplicados[item_code] = rate
	return aplicados


def migrar_pase_diario_a_entrenamiento_hora() -> None:
	"""Renombra el ítem y el tipo de cargo del antiguo Pase Diario a Entrenamiento por hora."""
	if frappe.db.exists("Item", ITEM_GYM_PASE_DIARIO_LEGACY):
		if frappe.db.exists("Item", ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO):
			frappe.db.set_value(
				CARGO_DOCTYPE,
				{"item": ITEM_GYM_PASE_DIARIO_LEGACY},
				"item",
				ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO,
				update_modified=False,
			)
			frappe.db.set_value("Item", ITEM_GYM_PASE_DIARIO_LEGACY, "disabled", 1, update_modified=False)
		else:
			frappe.rename_doc(
				"Item",
				ITEM_GYM_PASE_DIARIO_LEGACY,
				ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO,
				force=True,
				show_alert=False,
			)
	frappe.db.set_value(
		CARGO_DOCTYPE,
		{"tipo_cargo": TIPO_PASE_DIARIO_LEGACY},
		"tipo_cargo",
		TIPO_ENTRENAMIENTO_HORA,
		update_modified=False,
	)


def precio_item_gimnasio(item_code: str) -> float:
	return flt(
		frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, "price_list_rate")
		or frappe.db.get_value("Item", item_code, "standard_rate")
		or 0
	)


def precios_gimnasio() -> dict[str, float]:
	return {tipo: precio_item_gimnasio(item) for tipo, item in ITEM_POR_TIPO.items()}


def generar_cargo_gimnasio(
	socio_name: str,
	tipo: str,
	*,
	registrar_pago: bool = False,
	mode_of_payment: str | None = None,
	monto: float | None = None,
) -> dict[str, Any]:
	"""Crea el `Cargo Socio` único (factura al insertarse) y opcionalmente registra el pago."""
	ensure_secretaria_operacion_access()
	if tipo not in ITEM_POR_TIPO:
		frappe.throw(_("Tipo de cargo de gimnasio inválido: {0}").format(tipo), frappe.ValidationError)
	if not frappe.db.exists("Socio", socio_name):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)
	if not es_no_socio(socio_name):
		frappe.throw(_("{0} es solo para practicantes No Socio.").format(tipo), frappe.ValidationError)

	item_code = ITEM_POR_TIPO[tipo]
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Falta el ítem {0} (ejecute migrate).").format(item_code), frappe.ValidationError)
	importe = flt(monto) if monto else precio_item_gimnasio(item_code)
	if importe <= 0:
		frappe.throw(
			_("Configure el precio del ítem {0} o indique un monto.").format(item_code),
			frappe.ValidationError,
		)

	hoy = today()
	cargo = frappe.get_doc(
		{
			"doctype": CARGO_DOCTYPE,
			"socio": socio_name,
			"titulo": f"{_TITULO_POR_TIPO[tipo]} {formatdate(hoy)}",
			"tipo_cargo": tipo,
			"modo_cobro": "Unico",
			"item": item_code,
			"monto": importe,
			"fecha_desde": hoy,
		}
	)
	cargo.insert(ignore_permissions=True)
	cargo.reload()
	sales_invoice = cargo.sales_invoice

	payment_entry = None
	if registrar_pago:
		if not sales_invoice:
			frappe.throw(_("El cargo no generó factura; no se puede registrar el pago."), frappe.ValidationError)
		from club_management.members.services.cobranza_manual import registrar_cobro_manual

		payment_entry = registrar_cobro_manual(
			socio_name,
			sales_invoice,
			mode_of_payment=mode_of_payment or "Cash",
		)

	return {
		"cargo": cargo.name,
		"sales_invoice": sales_invoice,
		"payment_entry": payment_entry,
		"monto": importe,
	}

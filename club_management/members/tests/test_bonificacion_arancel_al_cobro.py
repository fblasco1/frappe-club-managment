"""Tests bonificación de arancel al cobro.

Spec: ``bonificacion_arancel_al_cobro.md``
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.bonificacion_arancel import (
	calcular_bonificacion_factura,
	calcular_monto_bonificacion,
	monto_arancel_en_factura,
)
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	erpnext_cobranza_disponible,
	ensure_customer_for_socio,
	format_periodo_cobro,
	registrar_cobro_compuesto,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.mora_al_cobro import (
	calcular_detalle_mora_factura,
	preparar_facturas_cobro_con_mora,
	previsualizar_cobro_con_mora,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestBonificacionArancelFormula(MembersTestCase):
	def test_tope_no_supera_arancel(self) -> None:
		calc = calcular_monto_bonificacion(
			monto_arancel=10000,
			bonificaciones=[
				{"name": "B1", "tipo_descuento": "Monto fijo", "valor": 50000, "motivo": "x"},
			],
		)
		self.assertAlmostEqual(calc["monto_bonificacion"], 10000.0)

	def test_porcentaje_sobre_arancel(self) -> None:
		calc = calcular_monto_bonificacion(
			monto_arancel=28500,
			bonificaciones=[
				{"name": "B1", "tipo_descuento": "Porcentaje", "valor": 25, "motivo": "clase"},
			],
		)
		self.assertAlmostEqual(calc["monto_bonificacion"], 7125.0)


class TestBonificacionArancelIntegracion(MembersTestCase):
	_ITEM_BONIF = "TEST-ITEM-BONIF-ARANCEL"
	_ITEM_ARANCEL = "TEST-ITEM-ARANCEL-BONIF"
	_ITEM_CUOTA = "TEST-ITEM-CUOTA-BONIF"
	_PERIODO = "08/2026"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		if not frappe.db.exists("DocType", "Bonificacion Arancel"):
			self.skipTest("DocType Bonificacion Arancel no migrado")
		apply_patch()
		sync_cuotas_sociales_club()
		self._secretaria = make_secretaria_user("secretaria.bonif@example.com")
		self._ensure_items_and_settings()

	def _ensure_items_and_settings(self) -> None:
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "Products"
		for code, rate, name in (
			(self._ITEM_BONIF, 0, "Bonificacion test"),
			(self._ITEM_ARANCEL, 28500, "Arancel test"),
			(self._ITEM_CUOTA, 26500, "Cuota test"),
		):
			if not frappe.db.exists("Item", code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": code,
						"item_name": name,
						"item_group": item_group,
						"is_stock_item": 0,
						"is_sales_item": 1,
						"standard_rate": rate,
					}
				).insert(ignore_permissions=True)
			else:
				frappe.db.set_value("Item", code, "standard_rate", rate)
		settings = frappe.get_single("Club Settings")
		settings.item_bonificacion_arancel = self._ITEM_BONIF
		settings.item_cuota_social = self._ITEM_CUOTA
		if not settings.company:
			settings.company = _default_company()
		settings.dia_primer_vencimiento = 10
		settings.dia_segundo_vencimiento = "20"
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.item = self._ITEM_CUOTA
				row.monto = 26500
		settings.save(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test bonif")
		return socio

	def _crear_si(
		self,
		socio_name: str,
		*,
		con_arancel: bool = True,
		con_cuota: bool = True,
		periodo: str | None = None,
	) -> str:
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		posting = today()
		items = []
		if con_cuota:
			items.append(
				{
					"item_code": self._ITEM_CUOTA,
					"qty": 1,
					"rate": 26500,
					"description": "Cuota social",
				}
			)
		if con_arancel:
			items.append(
				{
					"item_code": self._ITEM_ARANCEL,
					"qty": 1,
					"rate": 28500,
					"description": "Arancel actividad",
				}
			)
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio_name),
			"company": _default_company(),
			"posting_date": posting,
			"due_date": posting,
			"set_posting_time": 1,
			campo: socio_name,
			"items": items,
		}
		campo_periodo = _campo_periodo_cobro()
		if campo_periodo:
			payload[campo_periodo] = periodo or self._PERIODO
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _crear_bonif(self, **kwargs) -> str:
		defaults = {
			"doctype": "Bonificacion Arancel",
			"periodo_cobro": self._PERIODO,
			"tipo_descuento": "Porcentaje",
			"valor": 25,
			"motivo": "Profesor ausente — clase no recuperada",
			"estado": "Activa",
		}
		defaults.update(kwargs)
		doc = frappe.get_doc(defaults)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_monto_arancel_excluye_cuota(self) -> None:
		socio = self._socio_activo(dni="88001001", email="bonif.arancel@example.com")
		inv = self._crear_si(socio.name)
		self.assertAlmostEqual(monto_arancel_en_factura(inv, socio.name), 28500.0)

	def test_solo_cuota_bonificacion_cero(self) -> None:
		socio = self._socio_activo(dni="88001002", email="bonif.cuota@example.com")
		inv = self._crear_si(socio.name, con_arancel=False, con_cuota=True)
		self._crear_bonif(socio=socio.name, tipo_descuento="Monto fijo", valor=5000)
		info = calcular_bonificacion_factura(inv, socio.name)
		self.assertAlmostEqual(info["monto_bonificacion"], 0.0)

	def test_individual_matching(self) -> None:
		socio = self._socio_activo(dni="88001003", email="bonif.ind@example.com")
		inv = self._crear_si(socio.name)
		self._crear_bonif(socio=socio.name, tipo_descuento="Monto fijo", valor=5000)
		info = calcular_bonificacion_factura(inv, socio.name)
		self.assertAlmostEqual(info["monto_bonificacion"], 5000.0)

	def test_preview_resta_bonificacion_sin_crear_cn(self) -> None:
		socio = self._socio_activo(dni="88001004", email="bonif.prev@example.com")
		inv = self._crear_si(socio.name)
		self._crear_bonif(socio=socio.name, tipo_descuento="Porcentaje", valor=25)
		antes = frappe.db.count(SALES_INVOICE_DOCTYPE, {"is_return": 1, "docstatus": 1})
		frappe.set_user(self._secretaria)
		try:
			# Día 10 agosto → sin mora
			preview = previsualizar_cobro_con_mora(
				socio.name, [inv], posting_date="2026-08-10"
			)
		finally:
			frappe.set_user("Administrator")
		# 26500+28500 - 7125 = 47875
		self.assertAlmostEqual(preview["total_exigido"], 47875.0, places=2)
		self.assertTrue(preview["aplica_bonificacion"])
		self.assertAlmostEqual(preview["total_bonificacion"], 7125.0, places=2)
		self.assertEqual(
			frappe.db.count(SALES_INVOICE_DOCTYPE, {"is_return": 1, "docstatus": 1}),
			antes,
		)

	def test_preparar_crea_cn_idempotente(self) -> None:
		socio = self._socio_activo(dni="88001005", email="bonif.cn@example.com")
		inv = self._crear_si(socio.name)
		self._crear_bonif(socio=socio.name, tipo_descuento="Monto fijo", valor=5000)
		first = preparar_facturas_cobro_con_mora(
			socio.name, [inv], posting_date="2026-08-10"
		)
		self.assertTrue(first["credit_notes"])
		cn = first["credit_notes"][0]
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, cn, "is_return"), 1)
		second = preparar_facturas_cobro_con_mora(
			socio.name, [inv], posting_date="2026-08-10"
		)
		self.assertEqual(second["credit_notes"], first["credit_notes"])
		# No duplicar CN
		count = frappe.db.count(
			SALES_INVOICE_DOCTYPE,
			{"return_against": inv, "is_return": 1, "docstatus": 1},
		)
		self.assertEqual(count, 1)

	def test_cobro_neto_con_bonificacion(self) -> None:
		socio = self._socio_activo(dni="88001006", email="bonif.cobro@example.com")
		inv = self._crear_si(socio.name, con_cuota=False, con_arancel=True)
		self._crear_bonif(socio=socio.name, tipo_descuento="Monto fijo", valor=5000)
		prep = preparar_facturas_cobro_con_mora(
			socio.name, [inv], posting_date="2026-08-10"
		)
		neto = flt(prep["total_exigido"])
		self.assertAlmostEqual(neto, 23500.0, places=2)
		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro_compuesto(
				socio.name,
				[inv],
				[{"mode_of_payment": "Cash", "amount": neto}],
				posting_date="2026-08-10",
			)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(result["payment_entries"])
		self.assertEqual(flt(sync_saldo_deuda_socio(socio.name)), 0)

	def test_detalle_dia_10_con_bonif(self) -> None:
		socio = self._socio_activo(dni="88001007", email="bonif.det@example.com")
		inv = self._crear_si(socio.name, con_cuota=False)
		self._crear_bonif(socio=socio.name, tipo_descuento="Porcentaje", valor=25)
		det = calcular_detalle_mora_factura(inv, posting_date="2026-08-10")
		self.assertAlmostEqual(det["monto_bonificacion"], 7125.0)
		self.assertAlmostEqual(det["monto_exigido"], 21375.0)

"""Tests mora al cobro: tramos 1.er / 2.º vencimiento (+10% / +15%).

Spec: `club_management/specs/recargos_mora_dos_tramos.md`
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	registrar_cobro_compuesto,
	registrar_cobro_manual,
	resolve_cuota_social,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cobranza_periodica import (
	format_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.mora_al_cobro import (
	MORA_SUFFIX,
	_periodo_sort_key,
	calcular_monto_exigido_mora,
	meses_vencidos_entre,
	parse_periodo_cobro,
	periodo_es_ajuste_mora,
	preparar_facturas_cobro_con_mora,
	previsualizar_cobro_con_mora,
	resolver_tramo_mora,
	texto_composicion_mora,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestMoraValorActualFormula(MembersTestCase):
	"""Cálculo puro (sin depender de SI)."""

	def test_parse_periodo_cobro(self) -> None:
		self.assertEqual(parse_periodo_cobro("03/2026"), date(2026, 3, 1))
		self.assertIsNone(parse_periodo_cobro("03/2026-MORA"))
		self.assertIsNone(parse_periodo_cobro("03/2026-REC"))
		self.assertIsNone(parse_periodo_cobro(""))


	def test_meses_vencidos(self) -> None:
		self.assertEqual(meses_vencidos_entre("03/2026", "2026-04-15"), 1)
		self.assertEqual(meses_vencidos_entre("02/2026", "2026-04-08"), 2)
		self.assertEqual(meses_vencidos_entre("04/2026", "2026-04-15"), 0)

	def test_tramo_mismo_mes_antes_del_10(self) -> None:
		self.assertEqual(resolver_tramo_mora("03/2026", "2026-03-08"), "ninguno")

	def test_tramo_mismo_mes_post_dia_10(self) -> None:
		self.assertEqual(resolver_tramo_mora("03/2026", "2026-03-15"), "post_primer")

	def test_tramo_dia_20_inclusive_sigue_post_primer(self) -> None:
		self.assertEqual(
			resolver_tramo_mora("03/2026", "2026-03-20", dia_segundo_vencimiento="20"),
			"post_primer",
		)

	def test_tramo_dia_21_post_segundo(self) -> None:
		self.assertEqual(
			resolver_tramo_mora("03/2026", "2026-03-21", dia_segundo_vencimiento="20"),
			"post_segundo",
		)

	def test_tramo_post_segundo_vencimiento(self) -> None:
		self.assertEqual(resolver_tramo_mora("03/2026", "2026-04-01"), "post_segundo")
		self.assertEqual(resolver_tramo_mora("03/2026", "2026-04-08"), "post_segundo")
		self.assertEqual(resolver_tramo_mora("03/2026", "2026-07-15"), "post_segundo")

	def test_post_primer_solo_10_pct(self) -> None:
		self.assertEqual(
			calcular_monto_exigido_mora(
				valor_actual=12,
				tramo="post_primer",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			13.2,
		)

	def test_post_segundo_15_pct(self) -> None:
		# cuota mes pago × 1.15
		self.assertEqual(
			calcular_monto_exigido_mora(
				valor_actual=12,
				tramo="post_segundo",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			13.8,
		)
		self.assertEqual(
			calcular_monto_exigido_mora(
				valor_actual=29000,
				tramo="post_segundo",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			33350.0,
		)

	def test_sin_mora_en_termino(self) -> None:
		self.assertEqual(
			calcular_monto_exigido_mora(
				valor_actual=12,
				tramo="ninguno",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			12.0,
		)

	def test_base_mora_no_baja_del_outstanding(self) -> None:
		from club_management.members.services.mora_al_cobro import monto_exigido_con_piso

		# Valor solo 1.ª línea (28,5k) vs SI completa 57k → piso = 57k × 1,10
		self.assertEqual(
			monto_exigido_con_piso(
				valor_actual=28500,
				outstanding_factura=57000,
				tramo="post_primer",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			62700.0,
		)
		self.assertEqual(
			monto_exigido_con_piso(
				valor_actual=60000,
				outstanding_factura=57000,
				tramo="post_primer",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			66000.0,
		)

	def test_post_primer_sobre_base_completa_no_achica(self) -> None:
		"""Día 11: 57k × 1,10 = 62,7k (no 28,5k × 1,10)."""
		from club_management.members.services.mora_al_cobro import monto_exigido_con_piso

		self.assertEqual(
			monto_exigido_con_piso(
				valor_actual=57000,
				outstanding_factura=57000,
				tramo="post_primer",
				pct_post_primer=10,
				pct_extra_segundo=5,
			),
			62700.0,
		)

	def test_periodo_es_ajuste_mora(self) -> None:
		self.assertTrue(periodo_es_ajuste_mora(f"03/2026{MORA_SUFFIX}"))
		self.assertFalse(periodo_es_ajuste_mora("03/2026"))
		self.assertFalse(periodo_es_ajuste_mora("03/2026-REC"))

	def test_periodo_sort_key_cronologico(self) -> None:
		periodos = ["01/2026", "12/2025", "03/2026", "03/2026-MORA", ""]
		ordenado = sorted(periodos, key=_periodo_sort_key)
		self.assertEqual(ordenado[:4], ["12/2025", "01/2026", "03/2026", "03/2026-MORA"])

	def test_texto_composicion_mora(self) -> None:
		txt = texto_composicion_mora(
			valor_actual=12000,
			tramo="post_segundo",
			pct_post_primer=10,
			pct_extra_segundo=5,
			monto_exigido=13800,
		)
		self.assertIn("10%", txt)
		self.assertIn("5%", txt)
		self.assertNotIn("5%×", txt)
		self.assertIn("13.800", txt)

		txt_10 = texto_composicion_mora(
			valor_actual=12000,
			tramo="post_primer",
			pct_post_primer=10,
			pct_extra_segundo=5,
			monto_exigido=13200,
		)
		self.assertIn("10%", txt_10)
		self.assertNotIn("5%", txt_10)



class TestMoraValorActualIntegracion(MembersTestCase):
	_GEN = "2026-03-01"
	_PAGO_ANTES = "2026-04-08"
	_PAGO_DESPUES = "2026-04-15"
	_ITEM_RECARGO = "TEST-ITEM-MORA-AL-COBRO"
	_VALOR_MARZO = 10000.0
	_VALOR_ABRIL = 12000.0

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._ensure_settings()

	def _ensure_settings(self) -> None:
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 10
		settings.dia_segundo_vencimiento = "20"
		settings.recargo_mes_vencido_pct = 5
		settings.recargo_post_vencimiento_pct = 10
		# Preferir empresa ICDPE del sitio (leaf cost centers reales)
		icdpe = frappe.db.get_value(
			"Company",
			{"name": ["like", "%Pedro%"]},
			"name",
		) or frappe.db.get_value("Company", {}, "name")
		if icdpe:
			settings.company = icdpe
		if not frappe.db.exists("Item", self._ITEM_RECARGO):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self._ITEM_RECARGO,
					"item_name": "Mora al cobro test",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 0,
				}
			).insert(ignore_permissions=True)
		settings.item_recargo_mora = self._ITEM_RECARGO
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.monto = self._VALOR_MARZO
		settings.save(ignore_permissions=True)

	def _set_cuota_activo(self, monto: float) -> None:
		settings = frappe.get_single("Club Settings")
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.monto = monto
		settings.save(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test mora al cobro")
		return socio

	def _factura_marzo(self, socio_name: str) -> str:
		self._set_cuota_activo(self._VALOR_MARZO)
		name = generar_deuda_mensual_socio(socio_name, reference_date=self._GEN)
		self.assertTrue(name)
		return name

	def test_preparar_marzo_en_abril_antes_del_10(self) -> None:
		# Abril ya es post 2.º venc. de marzo → 15 % sobre cuota abril
		socio = self._socio_activo(dni="76001001", email="mora.antes@example.com")
		invoice = self._factura_marzo(socio.name)
		self._set_cuota_activo(self._VALOR_ABRIL)

		prep = preparar_facturas_cobro_con_mora(
			socio.name,
			[invoice],
			posting_date=self._PAGO_ANTES,
		)
		self.assertAlmostEqual(prep["total_exigido"], 13800.0, places=2)
		self.assertEqual(len(prep["sales_invoices"]), 2)
		ajuste = frappe.get_doc(SALES_INVOICE_DOCTYPE, prep["ajustes"][0])
		self.assertEqual(ajuste.docstatus, 1)
		self.assertAlmostEqual(flt(ajuste.grand_total), 3800.0, places=2)

	def test_preparar_marzo_en_abril_despues_del_10(self) -> None:
		socio = self._socio_activo(dni="76001002", email="mora.despues@example.com")
		invoice = self._factura_marzo(socio.name)
		self._set_cuota_activo(self._VALOR_ABRIL)

		prep = preparar_facturas_cobro_con_mora(
			socio.name,
			[invoice],
			posting_date=self._PAGO_DESPUES,
		)
		self.assertAlmostEqual(prep["total_exigido"], 13800.0, places=2)
		ajuste = frappe.get_doc(SALES_INVOICE_DOCTYPE, prep["ajustes"][0])
		self.assertAlmostEqual(flt(ajuste.grand_total), 3800.0, places=2)

	def test_cobro_manual_aplica_mora_y_salda(self) -> None:
		socio = self._socio_activo(dni="76001003", email="mora.cobro@example.com")
		invoice = self._factura_marzo(socio.name)
		self._set_cuota_activo(self._VALOR_ABRIL)

		prep = preparar_facturas_cobro_con_mora(
			socio.name,
			[invoice],
			posting_date=self._PAGO_DESPUES,
		)
		pe = registrar_cobro_manual(
			socio.name,
			invoice,
			posting_date=self._PAGO_DESPUES,
		)
		self.assertTrue(pe)
		inv = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice)
		self.assertEqual(flt(inv.outstanding_amount), 0)
		for ajuste_name in prep["ajustes"]:
			ajuste = frappe.get_doc(SALES_INVOICE_DOCTYPE, ajuste_name)
			self.assertEqual(flt(ajuste.outstanding_amount), 0)
		self.assertEqual(flt(sync_saldo_deuda_socio(socio.name)), 0)

	def test_cobro_compuesto_medios_coinciden_con_total_exigido(self) -> None:
		socio = self._socio_activo(dni="76001004", email="mora.mixto@example.com")
		invoice = self._factura_marzo(socio.name)
		self._set_cuota_activo(self._VALOR_ABRIL)

		prep = preparar_facturas_cobro_con_mora(
			socio.name,
			[invoice],
			posting_date=self._PAGO_ANTES,
		)
		total = prep["total_exigido"]
		result = registrar_cobro_compuesto(
			socio.name,
			[invoice],
			[
				{"mode_of_payment": "Cash", "amount": total - 5},
				{"mode_of_payment": "Wire Transfer", "amount": 5},
			],
			posting_date=self._PAGO_ANTES,
		)
		self.assertEqual(len(result["payment_entries"]), 2)
		self.assertEqual(flt(result["saldo_deuda"]), 0)

	def test_idempotencia_mismo_ajuste(self) -> None:
		socio = self._socio_activo(dni="76001005", email="mora.idem@example.com")
		invoice = self._factura_marzo(socio.name)
		self._set_cuota_activo(self._VALOR_ABRIL)

		first = preparar_facturas_cobro_con_mora(
			socio.name, [invoice], posting_date=self._PAGO_ANTES
		)
		second = preparar_facturas_cobro_con_mora(
			socio.name, [invoice], posting_date=self._PAGO_ANTES
		)
		self.assertEqual(first["ajustes"], second["ajustes"])
		self.assertAlmostEqual(first["total_exigido"], second["total_exigido"], places=2)

	def test_sin_ajuste_si_paga_en_termino_mismo_mes(self) -> None:
		socio = self._socio_activo(dni="76001006", email="mora.termino@example.com")
		self._set_cuota_activo(self._VALOR_ABRIL)
		invoice = generar_deuda_mensual_socio(socio.name, reference_date="2026-04-01")
		self.assertTrue(invoice)
		monto, _ = resolve_cuota_social(socio.name)
		prep = preparar_facturas_cobro_con_mora(
			socio.name,
			[invoice],
			posting_date="2026-04-08",
		)
		self.assertEqual(prep["ajustes"], [])
		self.assertAlmostEqual(prep["total_exigido"], flt(monto), places=2)
		self.assertEqual(format_periodo_cobro("2026-04-01"), "04/2026")

	def test_preview_mora_sin_crear_ajuste_y_con_composicion(self) -> None:
		from club_management.members.test_helpers import make_secretaria_user

		secretaria = make_secretaria_user("secretaria.mora.preview@example.com")
		socio = self._socio_activo(dni="76001007", email="mora.preview@example.com")
		invoice = self._factura_marzo(socio.name)
		self._set_cuota_activo(self._VALOR_ABRIL)

		antes = frappe.db.count(SALES_INVOICE_DOCTYPE, {"docstatus": 1})
		frappe.set_user(secretaria)
		try:
			preview = previsualizar_cobro_con_mora(
				socio.name,
				[invoice],
				posting_date=self._PAGO_DESPUES,
			)
		finally:
			frappe.set_user("Administrator")

		self.assertAlmostEqual(preview["total_exigido"], 13800.0, places=2)
		self.assertTrue(preview["aplica_mora"])
		self.assertEqual(len(preview["detalle"]), 1)
		comp = preview["detalle"][0]["composicion"]
		self.assertIn("10%", comp)
		self.assertIn("5%", comp)
		self.assertNotIn("5%×", comp)
		self.assertEqual(frappe.db.count(SALES_INVOICE_DOCTYPE, {"docstatus": 1}), antes)

	def test_preview_factura_multilinea_dia_11_no_achica(self) -> None:
		"""Cuota+arancel en una SI: día 10 = outstanding; día 11 = ×1,10 (no solo 1.ª línea)."""
		from frappe.utils import today

		from club_management.members.services.cobranza_manual import (
			_campo_periodo_cobro,
			_campo_socio_en,
			_default_company,
			ensure_customer_for_socio,
			format_periodo_cobro,
		)
		from club_management.members.services.mora_al_cobro import calcular_detalle_mora_factura

		socio = self._socio_activo(dni="76001008", email="mora.multilinea@example.com")
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		self.assertTrue(campo)
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "Products"
		for code, rate in (("TEST-MORA-CUOTA-ML", 28500), ("TEST-MORA-ARANCEL-ML", 28500)):
			if not frappe.db.exists("Item", code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": code,
						"item_name": code,
						"item_group": item_group,
						"is_stock_item": 0,
						"is_sales_item": 1,
						"standard_rate": rate,
					}
				).insert(ignore_permissions=True)
			else:
				frappe.db.set_value("Item", code, "standard_rate", rate)

		posting = today()
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio.name),
			"company": _default_company(),
			"posting_date": posting,
			"due_date": posting,
			"set_posting_time": 1,
			campo: socio.name,
			"items": [
				{"item_code": "TEST-MORA-CUOTA-ML", "qty": 1, "rate": 28500, "description": "Cuota social"},
				{
					"item_code": "TEST-MORA-ARANCEL-ML",
					"qty": 1,
					"rate": 28500,
					"description": "Arancel actividad",
				},
			],
		}
		campo_periodo = _campo_periodo_cobro()
		if campo_periodo:
			payload[campo_periodo] = format_periodo_cobro("2026-08-01")
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()

		dia10 = calcular_detalle_mora_factura(doc.name, posting_date="2026-08-10")
		dia11 = calcular_detalle_mora_factura(doc.name, posting_date="2026-08-11")
		self.assertEqual(dia10["tramo"], "ninguno")
		self.assertAlmostEqual(dia10["monto_exigido"], 57000.0, places=2)
		self.assertEqual(dia11["tramo"], "post_primer")
		self.assertAlmostEqual(dia11["monto_exigido"], 62700.0, places=2)
		self.assertGreater(dia11["monto_exigido"], dia10["monto_exigido"])

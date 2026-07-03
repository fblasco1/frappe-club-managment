"""Tests liquidación por equipo (spec liquidacion_equipo_deuda_rango.md)."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.exceptions import PermissionError
from frappe.utils import flt, getdate

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.liquidacion_equipo import (
	build_inscripcion_filters,
	calcular_deuda_desglose_en_rango,
	calcular_deuda_en_rango,
	calcular_pagos_arancel_en_rango,
	calcular_pagos_en_rango,
	get_deuda_por_actividad_data,
	get_deuda_por_equipo_data,
	get_facturas_pendientes_socio_en_rango,
	get_pagos_por_equipo_data,
	liquidar_deuda_socio_en_rango,
	registrar_cobro_liquidacion,
	resolve_pct_liquidacion_entrenador,
	validar_filtros_liquidacion,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user

ARANCEL_ITEM_CODE = "LIQ-TEST-ARANCEL"


class TestLiquidacionEquipo(MembersTestCase):
	_MARZO_DESDE = "2026-03-01"
	_MARZO_HASTA = "2026-03-31"
	_ABRIL_DESDE = "2026-04-01"
	_ABRIL_HASTA = "2026-04-30"
	_FROZEN_TODAY = "2026-03-20"

	def setUp(self) -> None:
		super().setUp()
		self._today_patch = patch("frappe.utils.today", return_value=self._FROZEN_TODAY)
		self._today_patch.start()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		self._ensure_cuota_item()
		self._actividad, self._grupo, self._equipo = self._setup_jerarquia()

	def tearDown(self) -> None:
		self._today_patch.stop()
		super().tearDown()

	def _ensure_cuota_item(self) -> None:
		if frappe.db.exists("Item", CUOTA_SOCIAL_ITEM_CODE):
			return
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": CUOTA_SOCIAL_ITEM_CODE,
				"item_name": "Cuota Social Base",
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 10_000,
			}
		).insert(ignore_permissions=True)

	def _setup_jerarquia(self) -> tuple[str, str, str]:
		actividad = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": "Liq Test Basket",
				"habilitada": 1,
				"usa_grupos": 1,
			}
		).insert(ignore_permissions=True)
		grupo = frappe.get_doc(
			{
				"doctype": "Grupo Actividad",
				"actividad": actividad.name,
				"titulo": "Tira Azul Liq",
				"habilitada": 1,
			}
		).insert(ignore_permissions=True)
		equipo = frappe.get_doc(
			{
				"doctype": "Equipo Actividad",
				"grupo_actividad": grupo.name,
				"titulo": "U15 Masculino Liq",
				"habilitada": 1,
			}
		).insert(ignore_permissions=True)
		self._ensure_arancel_item()
		frappe.db.set_value("Equipo Actividad", equipo.name, "item", ARANCEL_ITEM_CODE)
		return actividad.name, grupo.name, equipo.name

	def _ensure_arancel_item(self) -> None:
		if frappe.db.exists("Item", ARANCEL_ITEM_CODE):
			return
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ARANCEL_ITEM_CODE,
				"item_name": "Arancel Liq Test",
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 5000,
			}
		).insert(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test liquidación equipo")
		return socio

	def _inscribir(self, socio_name: str, *, equipo: str | None = None, grupo: str | None = None) -> None:
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio_name,
				"actividad": self._actividad,
				"grupo_actividad": grupo or self._grupo,
				"equipo_actividad": equipo or self._equipo,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)

	def _crear_factura(self, socio_name: str, posting_date: str, amount: float = 5000) -> str:
		"""Crea factura con posting_date explícita (>= hoy simulado del test)."""
		return self._crear_factura_items(
			socio_name,
			posting_date,
			[{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": amount}],
		)

	def _crear_factura_items(
		self,
		socio_name: str,
		posting_date: str,
		items: list[dict],
	) -> str:
		campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
		posting = getdate(posting_date)
		now = getdate(self._FROZEN_TODAY)
		if posting < now:
			posting = now
		invoice = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": posting,
				"due_date": posting,
				campo_socio: socio_name,
				"items": items,
			}
		)
		invoice.set_posting_time = 1
		invoice.insert(ignore_permissions=True)
		invoice.submit()
		return invoice.name

	def _marcar_factura_pagada(self, invoice_name: str) -> None:
		grand_total = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "grand_total"))
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount", 0)
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, invoice_name, "paid_amount", grand_total)

	def _filtros_equipo(self, **overrides):
		base = {
			"equipo_actividad": self._equipo,
			"fecha_desde": self._MARZO_DESDE,
			"fecha_hasta": self._MARZO_HASTA,
			"incluir_saldo_cero": 0,
		}
		base.update(overrides)
		return base

	def test_validar_fechas_invertidas_falla(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			validar_filtros_liquidacion(
				{
					"equipo_actividad": self._equipo,
					"fecha_desde": "2026-05-15",
					"fecha_hasta": "2026-05-01",
				}
			)

	def test_validar_filtro_jerarquico_obligatorio(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			validar_filtros_liquidacion(
				{"fecha_desde": self._MARZO_DESDE, "fecha_hasta": self._MARZO_HASTA}
			)

	def test_consulta_deuda_equipo_marzo(self) -> None:
		socio_a = self._socio_activo(dni="74001001", email="liq.a@example.com")
		socio_b = self._socio_activo(dni="74001002", email="liq.b@example.com")
		socio_c = self._socio_activo(dni="74001003", email="liq.c@example.com")
		for socio in (socio_a, socio_b, socio_c):
			self._inscribir(socio.name)
		self._crear_factura(socio_a.name, "2026-03-20", 8000)
		self._crear_factura(socio_b.name, "2026-03-20", 6000)

		rows = get_deuda_por_equipo_data(self._filtros_equipo())
		by_socio = {row["socio"]: row for row in rows}
		self.assertIn(socio_a.name, by_socio)
		self.assertIn(socio_b.name, by_socio)
		self.assertNotIn(socio_c.name, by_socio)
		self.assertEqual(by_socio[socio_a.name]["deuda_en_rango"], 8000.0)
		self.assertEqual(by_socio[socio_a.name]["equipo_actividad"], self._equipo)
		self.assertEqual(by_socio[socio_a.name]["nombre_apellido"], "Pérez, Ana")

	def test_consulta_pagos_equipo_marzo(self) -> None:
		socio_a = self._socio_activo(dni="74001011", email="pagos.a@example.com", apellido="Lopez", nombre="Juan")
		socio_b = self._socio_activo(dni="74001012", email="pagos.b@example.com")
		for socio in (socio_a, socio_b):
			self._inscribir(socio.name)
		invoice_a = self._crear_factura_items(
			socio_a.name,
			"2026-03-20",
			[{"item_code": ARANCEL_ITEM_CODE, "qty": 1, "rate": 8000}],
		)
		self._crear_factura(socio_b.name, "2026-03-20", 6000)
		self._marcar_factura_pagada(invoice_a)

		rows = get_pagos_por_equipo_data(self._filtros_equipo())
		by_socio = {row["socio"]: row for row in rows}
		self.assertIn(socio_a.name, by_socio)
		self.assertNotIn(socio_b.name, by_socio)
		self.assertEqual(by_socio[socio_a.name]["pagos_en_rango"], 8000.0)
		self.assertEqual(by_socio[socio_a.name]["liquidacion_entrenador"], 6400.0)
		self.assertEqual(by_socio[socio_a.name]["pct_entrenador"], 80.0)
		self.assertEqual(by_socio[socio_a.name]["nombre_apellido"], "Lopez, Juan")

	def test_deuda_desglose_cuota_y_arancel(self) -> None:
		socio = self._socio_activo(dni="74001015", email="desglose@example.com")
		ins = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": self._actividad,
				"grupo_actividad": self._grupo,
				"equipo_actividad": self._equipo,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)
		self._crear_factura_items(
			socio.name,
			"2026-03-20",
			[
				{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": 10000},
				{"item_code": ARANCEL_ITEM_CODE, "qty": 1, "rate": 5000},
			],
		)
		desglose = calcular_deuda_desglose_en_rango(
			socio.name,
			self._MARZO_DESDE,
			self._MARZO_HASTA,
			inscripcion_name=ins.name,
		)
		self.assertEqual(desglose["deuda_cuota_social"], 10000.0)
		self.assertEqual(desglose["deuda_arancel"], 5000.0)
		rows = get_deuda_por_equipo_data(self._filtros_equipo())
		row = next(item for item in rows if item["socio"] == socio.name)
		self.assertEqual(row["deuda_cuota_social"], 10000.0)
		self.assertEqual(row["deuda_arancel"], 5000.0)
		self.assertGreaterEqual(row["cantidad_meses_deuda"], 1)

	def test_pct_liquidacion_configurable_en_equipo(self) -> None:
		frappe.db.set_value("Equipo Actividad", self._equipo, "pct_liquidacion_entrenador", 70)
		self.assertEqual(
			resolve_pct_liquidacion_entrenador(
				equipo_actividad=self._equipo,
				grupo_actividad=self._grupo,
			),
			70.0,
		)
		socio = self._socio_activo(dni="74001016", email="pct.eq@example.com")
		self._inscribir(socio.name)
		invoice = self._crear_factura_items(
			socio.name,
			"2026-03-20",
			[{"item_code": ARANCEL_ITEM_CODE, "qty": 1, "rate": 10000}],
		)
		self._marcar_factura_pagada(invoice)
		rows = get_pagos_por_equipo_data(self._filtros_equipo())
		row = next(item for item in rows if item["socio"] == socio.name)
		self.assertEqual(row["liquidacion_entrenador"], 7000.0)
		self.assertEqual(row["pct_entrenador"], 70.0)

	def test_pagos_varios_equipos_agrega_liquidacion(self) -> None:
		arancel_b = "LIQ-TEST-ARANCEL-B"
		if not frappe.db.exists("Item", arancel_b):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": arancel_b,
					"item_name": "Arancel Liq Test B",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 5000,
				}
			).insert(ignore_permissions=True)
		equipo_b = frappe.get_doc(
			{
				"doctype": "Equipo Actividad",
				"grupo_actividad": self._grupo,
				"titulo": "U17 Liq Pagos",
				"habilitada": 1,
				"item": arancel_b,
				"pct_liquidacion_entrenador": 90,
			}
		).insert(ignore_permissions=True).name
		socio = self._socio_activo(dni="74001017", email="multi.eq@example.com")
		self._inscribir(socio.name, equipo=self._equipo)
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": self._actividad,
				"grupo_actividad": self._grupo,
				"equipo_actividad": equipo_b,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)
		inv_a = self._crear_factura_items(
			socio.name,
			"2026-03-20",
			[{"item_code": ARANCEL_ITEM_CODE, "qty": 1, "rate": 10000}],
		)
		inv_b = self._crear_factura_items(
			socio.name,
			"2026-03-21",
			[{"item_code": arancel_b, "qty": 1, "rate": 5000}],
		)
		self._marcar_factura_pagada(inv_a)
		self._marcar_factura_pagada(inv_b)
		rows = get_pagos_por_equipo_data(
			{
				"equipos_actividad": [self._equipo, equipo_b],
				"fecha_desde": self._MARZO_DESDE,
				"fecha_hasta": self._MARZO_HASTA,
				"incluir_saldo_cero": 0,
			}
		)
		row = next(item for item in rows if item["socio"] == socio.name)
		self.assertEqual(row["pagos_en_rango"], 15000.0)
		self.assertEqual(row["liquidacion_entrenador"], 12500.0)

	def test_deuda_club_por_actividad_totaliza(self) -> None:
		socio = self._socio_activo(dni="74001018", email="club.act@example.com")
		self._inscribir(socio.name)
		self._crear_factura(socio.name, "2026-03-20", 12000)
		rows = get_deuda_por_actividad_data(
			{
				"fecha_desde": self._MARZO_DESDE,
				"fecha_hasta": self._MARZO_HASTA,
			}
		)
		actividad_row = next(item for item in rows if item["actividad"] == self._actividad)
		self.assertGreater(actividad_row["deuda_total"], 0)
		self.assertGreaterEqual(actividad_row["socios_deudores"], 1)
		total_row = rows[-1]
		self.assertEqual(total_row["actividad"], "Total")
		self.assertGreater(total_row["deuda_total"], 0)

	def test_pagos_arancel_proporcional_pago_parcial(self) -> None:
		socio = self._socio_activo(dni="74001014", email="pagos.prop@example.com")
		self._inscribir(socio.name)
		invoice_name = self._crear_factura_items(
			socio.name,
			"2026-03-20",
			[
				{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": 10000},
				{"item_code": ARANCEL_ITEM_CODE, "qty": 1, "rate": 5000},
			],
		)
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount", 7500)
		pagos, count = calcular_pagos_arancel_en_rango(
			socio.name,
			fecha_desde=self._MARZO_DESDE,
			fecha_hasta=self._MARZO_HASTA,
			item_arancel=ARANCEL_ITEM_CODE,
		)
		self.assertEqual(count, 1)
		self.assertEqual(pagos, 2500.0)

	def test_pagos_equipo_excluye_cuota_social(self) -> None:
		socio = self._socio_activo(dni="74001013", email="pagos.cuota@example.com")
		self._inscribir(socio.name)
		invoice = self._crear_factura(socio.name, "2026-03-20", 9000)
		self._marcar_factura_pagada(invoice)
		rows = get_pagos_por_equipo_data(self._filtros_equipo())
		self.assertEqual([row for row in rows if row["socio"] == socio.name], [])

	def test_filtro_grupo_sin_equipo(self) -> None:
		equipo_u13 = frappe.get_doc(
			{
				"doctype": "Equipo Actividad",
				"grupo_actividad": self._grupo,
				"titulo": "U13 Liq",
				"habilitada": 1,
			}
		).insert(ignore_permissions=True).name
		socio_u15 = self._socio_activo(dni="74001004", email="liq.u15@example.com")
		socio_u13 = self._socio_activo(dni="74001005", email="liq.u13@example.com")
		self._inscribir(socio_u15.name, equipo=self._equipo)
		self._inscribir(socio_u13.name, equipo=equipo_u13)
		self._crear_factura(socio_u15.name, "2026-03-20")
		self._crear_factura(socio_u13.name, "2026-03-20")

		rows = get_deuda_por_equipo_data(
			{
				"grupo_actividad": self._grupo,
				"fecha_desde": self._MARZO_DESDE,
				"fecha_hasta": self._MARZO_HASTA,
				"incluir_saldo_cero": 0,
			}
		)
		socios = {row["socio"] for row in rows}
		self.assertEqual(socios, {socio_u15.name, socio_u13.name})

	def test_factura_pagada_no_suma_en_rango(self) -> None:
		socio = self._socio_activo(dni="74001006", email="liq.pagada@example.com")
		self._inscribir(socio.name)
		marzo = self._crear_factura(socio.name, "2026-03-20", 7000)
		abril = self._crear_factura(socio.name, "2026-04-05", 4000)

		from club_management.members.services.cobranza_manual import registrar_cobro_manual

		registrar_cobro_manual(socio.name, marzo)

		deuda_marzo, _count_m = calcular_deuda_en_rango(
			socio.name, self._MARZO_DESDE, self._MARZO_HASTA
		)
		deuda_abril, _count_a = calcular_deuda_en_rango(
			socio.name, self._ABRIL_DESDE, self._ABRIL_HASTA
		)
		self.assertEqual(deuda_marzo, 0.0)
		self.assertEqual(deuda_abril, 4000.0)
		self.assertTrue(frappe.db.get_value(SALES_INVOICE_DOCTYPE, abril, "outstanding_amount"))

	def test_dos_facturas_en_rango_suman_recargo(self) -> None:
		socio = self._socio_activo(dni="74001007", email="liq.rec@example.com")
		self._inscribir(socio.name)
		self._crear_factura(socio.name, "2026-03-20", 5000)
		self._crear_factura(socio.name, "2026-03-28", 500)

		deuda, cantidad = calcular_deuda_en_rango(
			socio.name, self._MARZO_DESDE, self._MARZO_HASTA
		)
		self.assertEqual(cantidad, 2)
		self.assertEqual(deuda, 5500.0)

	def test_incluir_saldo_cero_muestra_socio_sin_deuda(self) -> None:
		socio = self._socio_activo(dni="74001008", email="liq.cero@example.com")
		self._inscribir(socio.name)
		rows = get_deuda_por_equipo_data(self._filtros_equipo(incluir_saldo_cero=1))
		match = [row for row in rows if row["socio"] == socio.name]
		self.assertEqual(len(match), 1)
		self.assertEqual(match[0]["deuda_en_rango"], 0.0)

	def test_build_inscripcion_filters_por_equipo(self) -> None:
		filters = build_inscripcion_filters(
			{
				"equipo_actividad": self._equipo,
				"grupo_actividad": self._grupo,
				"actividad": self._actividad,
				"fecha_desde": self._MARZO_DESDE,
				"fecha_hasta": self._MARZO_HASTA,
			}
		)
		self.assertEqual(filters["equipo_actividad"], self._equipo)
		self.assertEqual(filters["estado"], "Activa")

	def test_reporte_deuda_por_equipo_habilita_fila_totales(self) -> None:
		self.assertEqual(
			frappe.db.get_value("Report", "Deuda por equipo", "add_total_row"),
			1,
		)


class TestLiquidacionEquipoDesk(MembersTestCase):
	_MARZO_DESDE = "2026-03-01"
	_MARZO_HASTA = "2026-03-31"
	_FROZEN_TODAY = "2026-03-20"

	def setUp(self) -> None:
		super().setUp()
		self._today_patch = patch("frappe.utils.today", return_value=self._FROZEN_TODAY)
		self._today_patch.start()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._secretaria = make_secretaria_user("secretaria.liq@example.com")
		sync_cuotas_sociales_club()

	def tearDown(self) -> None:
		self._today_patch.stop()
		super().tearDown()

	def test_guest_no_puede_liquidar(self) -> None:
		from club_management.members.api.liquidacion_equipo_desk import (
			liquidar_deuda_socio_en_rango_desk,
		)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(PermissionError):
				liquidar_deuda_socio_en_rango_desk(
					socio="SOC-TEST",
					fecha_desde=self._MARZO_DESDE,
					fecha_hasta=self._MARZO_HASTA,
				)
		finally:
			frappe.set_user("Administrator")

	def test_liquidar_dos_facturas_en_rango(self) -> None:
		from club_management.members.api.liquidacion_equipo_desk import (
			get_facturas_pendientes_rango,
			liquidar_deuda_socio_en_rango_desk,
		)

		if not frappe.db.exists("Item", CUOTA_SOCIAL_ITEM_CODE):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": CUOTA_SOCIAL_ITEM_CODE,
					"item_name": "Cuota Social Base",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 10_000,
				}
			).insert(ignore_permissions=True)

		socio = insert_socio(dni="74002001", email="liq.desk@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test liquidación desk")
		campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		for posting_date, amount in (("2026-03-20", 3000), ("2026-03-28", 2000)):
			posting = getdate(posting_date)
			now = getdate(self._FROZEN_TODAY)
			if posting < now:
				posting = now
			invoice = frappe.get_doc(
				{
					"doctype": SALES_INVOICE_DOCTYPE,
					"customer": customer,
					"company": _default_company(),
					"posting_date": posting,
					"due_date": posting,
					campo_socio: socio.name,
					"items": [{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": amount}],
				}
			)
			invoice.set_posting_time = 1
			invoice.insert(ignore_permissions=True)
			invoice.submit()

		frappe.set_user(self._secretaria)
		try:
			facturas = get_facturas_pendientes_rango(
				socio.name, self._MARZO_DESDE, self._MARZO_HASTA
			)
			self.assertEqual(len(facturas), 2)

			result = liquidar_deuda_socio_en_rango_desk(
				socio.name, self._MARZO_DESDE, self._MARZO_HASTA
			)
			self.assertEqual(len(result["payment_entries"]), 2)
			self.assertEqual(flt(result["deuda_en_rango"]), 0.0)
		finally:
			frappe.set_user("Administrator")

	def test_no_cobrar_factura_fuera_de_rango(self) -> None:
		socio = insert_socio(dni="74002002", email="liq.fuera@example.com")
		campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		posting = getdate("2026-04-05")
		invoice = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": posting,
				"due_date": posting,
				campo_socio: socio.name,
				"items": [{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": 1000}],
			}
		)
		invoice.set_posting_time = 1
		invoice.insert(ignore_permissions=True)
		invoice.submit()

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				registrar_cobro_liquidacion(
					socio.name,
					invoice.name,
					self._MARZO_DESDE,
					self._MARZO_HASTA,
				)
		finally:
			frappe.set_user("Administrator")

	def test_factura_de_otro_socio_falla(self) -> None:
		socio_a = insert_socio(dni="74002003", email="liq.a2@example.com")
		socio_b = insert_socio(dni="74002004", email="liq.b2@example.com")
		campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		customer = ensure_customer_for_socio(socio_a.name, skip_permission_check=True)
		posting = getdate(self._FROZEN_TODAY)
		invoice = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": posting,
				"due_date": posting,
				campo_socio: socio_a.name,
				"items": [{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": 1000}],
			}
		)
		invoice.set_posting_time = 1
		invoice.insert(ignore_permissions=True)
		invoice.submit()

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				registrar_cobro_liquidacion(
					socio_b.name,
					invoice.name,
					self._MARZO_DESDE,
					self._MARZO_HASTA,
				)
		finally:
			frappe.set_user("Administrator")

"""Tests KPIs panel Secretaría (spec secretaria_workspace_panel_kpis.md)."""

from __future__ import annotations

import frappe

from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
)
from club_management.members.services.cobranza_periodica import format_periodo_cobro
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.secretaria_panel_kpis import (
	count_socios_total,
	get_morosos_deuda_total,
	get_panel_metricas_payload,
	get_recaudacion_mes_payload,
	get_socio_metricas_payload,
)
from club_management.members.services.secretaria_panel_kpis import (
	_cuotas_sociales_kpi_payload,
)
from club_management.members.services.secretaria_workspace_panel import get_panel_lists_payload
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestSecretariaPanelKpis(MembersTestCase):
	_REFERENCE = "2026-06-15"

	def test_cuotas_sociales_kpi_saldo_por_cobrar(self) -> None:
		data = _cuotas_sociales_kpi_payload(emitido=10_000.0, recaudado=6_500.0)
		self.assertEqual(data["saldo_por_cobrar"], 3_500.0)
		self.assertEqual(data["porcentaje"], 65.0)
		self.assertIn("recaudado_label", data)
		self.assertIn("saldo_por_cobrar_label", data)

	def test_socio_metricas_total_y_delta(self) -> None:
		insert_socio(dni="73101001", email="kpi.a@example.com", estado="Activo", saldo_deuda=5000)
		insert_socio(dni="73101002", email="kpi.b@example.com", estado="Moroso")
		insert_socio(dni="73101003", email="kpi.c@example.com", estado="Baja")

		data = get_socio_metricas_payload(reference_date=self._REFERENCE)
		self.assertEqual(data["morosos"], frappe.db.count("Socio", {"estado": "Moroso"}))
		self.assertEqual(data["morosos"], 1)
		self.assertGreaterEqual(data["total"], 2)
		self.assertIn("delta_mes", data)
		self.assertIn("total_mes_anterior", data)
		self.assertIn("morosos_deuda", data)
		self.assertIn("morosos_deuda_label", data)

	def test_morosos_deuda_suma_saldo_deuda(self) -> None:
		insert_socio(dni="73101010", email="mor.d1@example.com", estado="Moroso", saldo_deuda=1500)
		insert_socio(dni="73101011", email="mor.d2@example.com", estado="Moroso", saldo_deuda=500)
		insert_socio(dni="73101012", email="mor.d3@example.com", estado="Activo", saldo_deuda=9999)
		self.assertEqual(get_morosos_deuda_total(), 2000.0)

	def test_count_socios_excluye_baja(self) -> None:
		before = count_socios_total()
		insert_socio(dni="73101004", email="kpi.baja@example.com", estado="Baja")
		self.assertEqual(count_socios_total(), before)

	def test_panel_payload_incluye_metricas_sin_lista_morosos(self) -> None:
		data = get_panel_lists_payload()
		self.assertIn("metricas", data)
		self.assertIn("cuotas_sociales", data["metricas"]["recaudacion"])
		self.assertIn("solicitudes_pendientes", data)
		self.assertNotIn("socios_morosos", data)
		self.assertIn("morosos", data["metricas"]["socios"])
		self.assertIn("recaudacion", data["metricas"])
		self.assertIn("segmentos", data["metricas"]["socios"])

	def test_ver_mas_filters_en_metricas(self) -> None:
		data = get_panel_metricas_payload()
		ver_mas = data["ver_mas"]
		self.assertEqual(ver_mas["socios_morosos_doctype"], "Socio")
		self.assertEqual(ver_mas["socios_total_filters"], [["Socio", "estado", "!=", "Baja"]])


class TestSecretariaPanelRecaudacion(MembersTestCase):
	_REFERENCE = "2099-06-01"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 10
		settings.incluir_aranceles_en_deuda_mensual = 1
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.save(ignore_permissions=True)
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

	def _socio_con_deuda(self, *, dni: str, email: str, actividad: str | None = None):
		socio = insert_socio(dni=dni, email=email, categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test KPI recaudación")
		if actividad:
			if not frappe.db.exists("Actividad", actividad):
				frappe.get_doc(
					{"doctype": "Actividad", "titulo": actividad, "habilitada": 1, "usa_grupos": 0}
				).insert(ignore_permissions=True)
			item_code = f"AR-KPI-{frappe.generate_hash(length=6)}"
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": f"Arancel {actividad}",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 5_000,
				}
			).insert(ignore_permissions=True)
			frappe.db.set_value("Actividad", actividad, "item", item_code)
			inscribir_socio_selecciones(socio.name, [{"actividad": actividad}])
		from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio

		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		return socio

	def test_recaudacion_cuotas_parcial(self) -> None:
		socio = self._socio_con_deuda(dni="73102001", email="rec.cuota@example.com")
		periodo = format_periodo_cobro(self._REFERENCE)
		campo_socio = "socio" if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field("socio") else "custom_socio"
		invoice_name = frappe.db.get_value(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
			"name",
		)
		self.assertTrue(invoice_name)
		registrar_cobro_manual(socio.name, invoice_name)

		data = get_recaudacion_mes_payload(reference_date=self._REFERENCE)
		self.assertTrue(data["disponible"])
		self.assertEqual(data["periodo"], periodo)
		cuotas = data["cuotas_sociales"]
		self.assertGreaterEqual(cuotas["porcentaje"], 100.0)
		self.assertEqual(cuotas["saldo_por_cobrar"], 0.0)
		self.assertIn("recaudado_label", cuotas)
		self.assertIn("saldo_por_cobrar_label", cuotas)

	def test_recaudacion_aranceles_por_actividad(self) -> None:
		from club_management.activities.services.inscripcion_socio import (
			resolve_item_arancel_inscripcion,
		)

		actividad = "KPI Natación"
		socio = self._socio_con_deuda(dni="73102002", email="rec.ar@example.com", actividad=actividad)
		inscripcion = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "actividad": actividad},
			"name",
		)
		self.assertTrue(inscripcion)
		item_code = resolve_item_arancel_inscripcion(inscripcion)
		self.assertTrue(item_code)
		campo_socio = "socio" if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field("socio") else "custom_socio"
		invoice_name = frappe.db.get_value(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
			"name",
		)
		self.assertTrue(invoice_name)
		self.assertTrue(
			frappe.db.exists(
				"Sales Invoice Item",
				{"parent": invoice_name, "item_code": item_code},
			)
		)
		data = get_recaudacion_mes_payload(reference_date=self._REFERENCE)
		self.assertTrue(data["disponible"])
		self.assertGreater(data["aranceles"]["emitido"], 0)
		actividades = {row["actividad"] for row in data["aranceles"]["por_actividad"]}
		self.assertIn(actividad, actividades)
		self.assertIn("total", data)
		self.assertIn("cobrabilidad_vistas", data)

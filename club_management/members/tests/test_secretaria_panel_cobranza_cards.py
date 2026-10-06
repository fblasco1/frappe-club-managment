"""Tests card unificada de cobrabilidad en panel Secretaría (fase 3 rendición).

Spec: `club_management/specs/informe_rendicion_cobranza_secretaria.md`
       `club_management/specs/secretaria_workspace_panel_kpis.md`
"""

from __future__ import annotations

from pathlib import Path

import frappe
from frappe.utils import get_first_day, get_last_day, getdate

from club_management.members.api.secretaria_workspace import get_cobrabilidad
from club_management.members.services.cobranza_periodica import format_periodo_cobro
from club_management.members.services.secretaria_panel_kpis import (
	get_cobrabilidad_payload,
	get_cobranza_panel_links,
	get_panel_metricas_payload,
)
from club_management.members.test_helpers import MembersTestCase, make_secretaria_user


class TestSecretariaPanelCobranzaCards(MembersTestCase):
	_REFERENCE = "2026-08-15"

	def test_cobranza_panel_links_mes_corriente(self) -> None:
		links = get_cobranza_panel_links(reference_date=self._REFERENCE)
		ref = getdate(self._REFERENCE)
		periodo = format_periodo_cobro(ref)
		self.assertEqual(links["periodo"], periodo)
		self.assertEqual(
			links["recaudado_cuotas_report"]["report"],
			"Recaudacion por concepto",
		)
		self.assertEqual(
			links["recaudado_cuotas_report"]["filters"]["fecha_desde"],
			str(get_first_day(ref)),
		)
		self.assertEqual(
			links["recaudado_cuotas_report"]["filters"]["fecha_hasta"],
			str(get_last_day(ref)),
		)
		self.assertEqual(links["recaudado_cuotas_report"]["filters"]["periodo_cobro"], periodo)
		self.assertEqual(links["recaudado_cuotas_report"]["filters"]["solo_cuotas_sociales"], 1)
		self.assertEqual(
			links["recaudado_aranceles_report"]["filters"]["agrupacion"],
			"Arancel",
		)
		self.assertEqual(links["saldo_cuotas_socios_doctype"], "Socio")
		self.assertEqual(
			links["saldo_cuotas_socios_filters"],
			[["Socio", "saldo_deuda", ">", 0]],
		)

	def test_panel_metricas_incluye_cobranza_en_ver_mas(self) -> None:
		data = get_panel_metricas_payload(reference_date=self._REFERENCE)
		cobranza = data["ver_mas"]["cobranza"]
		self.assertIn("recaudado_cuotas_report", cobranza)
		self.assertIn("recaudado_aranceles_report", cobranza)
		self.assertIn("report_by_vista", cobranza)
		self.assertEqual(cobranza["report_by_vista"]["cuota"]["filters"]["solo_cuotas_sociales"], 1)

	def test_recaudacion_incluye_vistas_y_total(self) -> None:
		data = get_panel_metricas_payload(reference_date=self._REFERENCE)
		rec = data["recaudacion"]
		self.assertIn("total", rec)
		self.assertIn("cobrabilidad_vistas", rec)
		self.assertGreaterEqual(len(rec["cobrabilidad_vistas"]), 4)
		self.assertIn("cto_comp", rec)
		self.assertIn("federativa", rec)

	def test_panel_js_cobrabilidad_dropdown(self) -> None:
		js_path = (
			Path(__file__).resolve().parents[2]
			/ "public"
			/ "js"
			/ "secretaria_workspace_panel.js"
		)
		js = js_path.read_text(encoding="utf-8")
		self.assertNotIn("render_cobranza_mes_cards", js)
		self.assertNotIn("club-secretaria-cobranza-section", js)
		self.assertIn("render_cobrabilidad_card", js)
		self.assertIn("club-secretaria-cobrabilidad-vista", js)
		self.assertIn("club-secretaria-cobrabilidad-detalle", js)
		self.assertIn("update_cobrabilidad_card", js)
		self.assertIn("get_cobrabilidad_slice", js)
		self.assertIn("report_by_vista", js)
		self.assertIn("Tasa de cobrabilidad del mes", js)
		self.assertIn("club-secretaria-ver-report", js)

	def test_cobrabilidad_payload_respeta_periodo_elegido(self) -> None:
		data = get_cobrabilidad_payload(reference_date="2026-07-01")
		self.assertEqual(data["periodo"], "07/2026")
		self.assertEqual(data["recaudacion"]["periodo"], "07/2026")
		self.assertIn("cobrabilidad_vistas", data["recaudacion"])
		self.assertEqual(data["cobranza"]["periodo"], "07/2026")
		filtros = data["cobranza"]["report_by_vista"]["total"]["filters"]
		self.assertEqual(filtros["fecha_desde"], "2026-07-01")
		self.assertEqual(filtros["fecha_hasta"], "2026-07-31")
		self.assertEqual(filtros["periodo_cobro"], "07/2026")

	def test_api_cobrabilidad_periodo_secretaria(self) -> None:
		frappe.set_user(make_secretaria_user())
		try:
			data = get_cobrabilidad(cobrabilidad_reference_date="2026-07-01")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(data["periodo"], "07/2026")

	def test_api_cobrabilidad_periodo_rechaza_sin_rol(self) -> None:
		email = "sin.rol.cobrabilidad@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": "Sin rol", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_cobrabilidad(cobrabilidad_reference_date="2026-07-01")
		finally:
			frappe.set_user("Administrator")

	def test_panel_js_cobrabilidad_selector_mes(self) -> None:
		js_path = (
			Path(__file__).resolve().parents[2]
			/ "public"
			/ "js"
			/ "secretaria_workspace_panel.js"
		)
		js = js_path.read_text(encoding="utf-8")
		self.assertIn("club-secretaria-cobrabilidad-month-input", js)
		self.assertIn("club_management.members.api.secretaria_workspace.get_cobrabilidad", js)
		self.assertIn("cobrabilidad_reference_date", js)

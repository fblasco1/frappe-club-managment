"""Tests dashboard Gestión de Socios (spec gestion_socios_dashboard.md)."""

from __future__ import annotations

import frappe

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
)
from club_management.members.services.cobranza_periodica import (
	format_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.secretaria_panel_kpis import (
	count_altas_bajas_mes,
	get_medios_pago_payload,
	get_mora_1_3_meses_payload,
	get_panel_metricas_payload,
	get_recaudacion_tendencia_payload,
	get_socios_por_segmento,
)
from club_management.members.services.secretaria_workspace_panel import (
	get_panel_lists_payload,
	get_solicitudes_pendientes_preview,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	insert_solicitud_asociacion,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	STATE_PENDIENTE,
	STATE_REQUIERE_CORRECCION,
)


class TestGestionSociosDashboardSegmentos(MembersTestCase):
	_REFERENCE = "2026-06-15"

	def test_socios_por_segmento(self) -> None:
		insert_socio(dni="74001001", email="seg.may@example.com", categoria="Activo", estado="Activo")
		insert_socio(dni="74001002", email="seg.men@example.com", categoria="Menor", estado="Activo")
		insert_socio(dni="74001003", email="seg.adh@example.com", categoria="Adherente", estado="Activo")
		insert_socio(dni="74001004", email="seg.jub@example.com", categoria="Jubilado", estado="Activo")
		insert_socio(dni="74001005", email="seg.baja@example.com", categoria="Activo", estado="Baja")

		data = get_socios_por_segmento(reference_date=self._REFERENCE)
		self.assertGreaterEqual(data["total"], 4)
		self.assertGreaterEqual(data["mayores"], 1)
		self.assertGreaterEqual(data["menores"], 1)
		self.assertGreaterEqual(data["adherentes"], 1)
		self.assertGreaterEqual(data["jubilados"], 1)
		self.assertEqual(
			data["mayores"] + data["menores"] + data["adherentes"] + data["jubilados"],
			data["total"],
		)

	def test_altas_bajas_mes(self) -> None:
		socio = insert_socio(dni="74002001", email="alt.baj@example.com", estado="Activo")
		frappe.db.set_value("Socio", socio.name, "fecha_alta", "2026-06-10")
		baja = insert_socio(dni="74002002", email="baja.mes@example.com", estado="Activo")
		cambiar_estado(baja.name, "Baja", motivo="Test dashboard")
		frappe.db.set_value("Socio", baja.name, "ultimo_cambio_estado_en", "2026-06-12 10:00:00")

		data = count_altas_bajas_mes(reference_date=self._REFERENCE)
		self.assertGreaterEqual(data["altas"], 1)
		self.assertGreaterEqual(data["bajas"], 1)

	def test_panel_metricas_incluye_dashboard(self) -> None:
		data = get_panel_metricas_payload(reference_date=self._REFERENCE)
		socios = data["socios"]
		self.assertIn("segmentos", socios)
		self.assertIn("altas_bajas", socios)
		self.assertIn("mora_1_3", socios)
		self.assertIn("tendencia_recaudacion", data)
		self.assertIn("medios_pago", data)


class TestGestionSociosDashboardSolicitudes(MembersTestCase):
	def test_solicitudes_incluye_pendiente_y_correccion(self) -> None:
		insert_solicitud_asociacion(
			dni="74003001",
			email="sol.pend@example.com",
			nombre="Ana",
			workflow_state=STATE_PENDIENTE,
		)
		insert_solicitud_asociacion(
			dni="74003002",
			email="sol.corr@example.com",
			nombre="Luis",
			workflow_state=STATE_REQUIERE_CORRECCION,
		)
		insert_solicitud_asociacion(
			dni="74003003",
			email="sol.val@example.com",
			nombre="María",
			workflow_state="Validada",
		)

		rows = get_solicitudes_pendientes_preview(limit=10)
		dnis = {row["dni"] for row in rows}
		self.assertIn("74003001", dnis)
		self.assertIn("74003002", dnis)
		self.assertNotIn("74003003", dnis)

	def test_panel_lists_incluye_solicitudes(self) -> None:
		data = get_panel_lists_payload()
		self.assertIn("solicitudes_pendientes", data)
		self.assertIn("solicitudes_doctype", data["metricas"]["ver_mas"])


class TestGestionSociosDashboardRecaudacion(MembersTestCase):
	_REFERENCE = "2026-06-01"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()

	def test_tendencia_recaudacion_ultimos_meses(self) -> None:
		data = get_recaudacion_tendencia_payload(
			months=3,
			reference_date=self._REFERENCE,
		)
		self.assertEqual(len(data["meses"]), 3)
		for row in data["meses"]:
			self.assertIn("periodo", row)
			self.assertIn("emitido", row)
			self.assertIn("recaudado", row)

	def test_medios_pago_agrupa_cash(self) -> None:
		from frappe.utils import today

		ref = today()
		socio = insert_socio(dni="74004001", email="med.pago@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test medios pago")
		generar_deuda_mensual_socio(socio.name, reference_date=ref)
		campo_socio = "socio" if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field("socio") else "custom_socio"
		invoice_name = frappe.db.get_value(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
			"name",
		)
		self.assertTrue(invoice_name)
		registrar_cobro_manual(socio.name, invoice_name)

		data = get_medios_pago_payload(reference_date=ref)
		self.assertTrue(data["disponible"])
		self.assertEqual(data["periodo"], format_periodo_cobro(ref))
		self.assertGreater(data["efectivo_pos"], 0)

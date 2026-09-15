"""Tests facturación de meses anteriores (spec facturacion_meses_anteriores.md)."""

from __future__ import annotations

import frappe
from frappe.exceptions import ValidationError
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	format_periodo_cobro,
	generar_cargo_socio,
)
from club_management.members.services.cobranza_periodica import (
	_campo_periodo_cobro,
	generar_deuda_rango_meses,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestFacturacionMesesAnteriores(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 10
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.incluir_cargos_extra_en_deuda_mensual = 0
		icdpe = frappe.db.get_value("Company", {"name": ["like", "%Pedro%"]}, "name")
		if icdpe:
			settings.company = icdpe
		elif not settings.company:
			settings.company = frappe.db.get_value("Company", {}, "name")
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.monto = 5000
		settings.save(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test meses anteriores")
		return socio

	def test_generar_cargo_periodo_pasado(self) -> None:
		socio = self._socio_activo(dni="77001001", email="meses.pasado@example.com")
		invoices = generar_cargo_socio(socio.name, reference_date="2026-03-01")
		self.assertTrue(invoices)
		campo = _campo_periodo_cobro()
		self.assertTrue(campo)
		for name in invoices:
			inv = frappe.get_doc(SALES_INVOICE_DOCTYPE, name)
			self.assertEqual(inv.docstatus, 1)
			self.assertEqual(inv.get(campo), "03/2026")

	def test_idempotencia_mismo_periodo(self) -> None:
		socio = self._socio_activo(dni="77001002", email="meses.idem@example.com")
		first = generar_cargo_socio(socio.name, reference_date="2026-03-01")
		self.assertTrue(first)
		with self.assertRaises(ValidationError):
			generar_cargo_socio(socio.name, reference_date="2026-03-01")

	def test_rango_meses_idempotente(self) -> None:
		socio = self._socio_activo(dni="77001003", email="meses.rango@example.com")
		# Pre-cargar febrero
		generar_cargo_socio(socio.name, reference_date="2026-02-01")
		result = generar_deuda_rango_meses(
			socio.name,
			desde="2026-01-01",
			hasta="2026-03-01",
		)
		self.assertEqual(result["periodos_omitidos"], ["02/2026"])
		self.assertIn("01/2026", result["periodos_creados"])
		self.assertIn("03/2026", result["periodos_creados"])
		self.assertEqual(result["errores"], 0)
		self.assertGreater(flt(result["facturas_creadas"]), 0)

	def test_periodo_string_en_api_helper(self) -> None:
		from club_management.members.services.cobranza_manual import reference_date_desde_periodo

		self.assertEqual(reference_date_desde_periodo("03/2026"), getdate("2026-03-01"))
		self.assertEqual(format_periodo_cobro("2026-03-01"), "03/2026")

"""Tests becas al socio (spec beca_socio.md)."""

from __future__ import annotations

import frappe

from club_management.members.services.beca_socio import beca_vigente_socio
from club_management.members.services.cobranza_manual import build_invoice_items_for_socio
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestBecaSocio(MembersTestCase):
	_REFERENCE = "2026-06-01"

	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Beca Socio"):
			self.skipTest("Ejecutar bench migrate para crear Beca Socio")
		sync_cuotas_sociales_club()

	def _insert_beca(self, socio_name: str, **overrides):
		payload = {
			"doctype": "Beca Socio",
			"socio": socio_name,
			"tipo_beca": "Total",
			"fecha_desde": "2026-06-01",
			"fecha_hasta": "2026-12-31",
			"estado": "Activa",
		}
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def test_beca_total_exime_cuota_y_arancel(self) -> None:
		socio = insert_socio(dni="75003001", email="beca.tot@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test beca")
		self._insert_beca(socio.name, tipo_beca="Total")
		items = build_invoice_items_for_socio(
			socio.name,
			incluir_actividades=False,
			reference_date=self._REFERENCE,
		)
		self.assertEqual(items, [])

	def test_beca_porcentaje_reduce_cuota(self) -> None:
		socio = insert_socio(dni="75003002", email="beca.pct@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test beca")
		self._insert_beca(
			socio.name,
			tipo_beca="Parcial Porcentaje",
			pct_cuota_social=50,
			pct_arancel=0,
		)
		items = build_invoice_items_for_socio(
			socio.name,
			incluir_actividades=False,
			reference_date=self._REFERENCE,
		)
		self.assertEqual(len(items), 1)
		self.assertGreater(items[0]["rate"], 0)

	def test_beca_vigente_fuera_de_rango(self) -> None:
		socio = insert_socio(dni="75003003", email="beca.vig@example.com")
		self._insert_beca(
			socio.name,
			fecha_desde="2026-01-01",
			fecha_hasta="2026-03-31",
		)
		self.assertIsNone(beca_vigente_socio(socio.name, reference_date="2026-06-01"))

	def test_generar_deuda_con_beca_total_sin_lineas(self) -> None:
		from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible

		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		socio = insert_socio(dni="75003004", email="beca.fac@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test beca")
		self._insert_beca(socio.name, tipo_beca="Total")
		name = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertIsNone(name)

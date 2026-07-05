"""Tests becas en formulario Socio (spec beca_socio.md — Desk)."""

from __future__ import annotations

import frappe

from club_management.members.services.beca_socio import list_becas_socio_desk
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestBecaSocioDesk(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Beca Socio"):
			self.skipTest("Ejecutar bench migrate para crear Beca Socio")
		self._secretaria = "secretaria.beca.desk@example.com"
		if not frappe.db.exists("User", self._secretaria):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self._secretaria,
					"first_name": "Secretaria",
					"send_welcome_email": 0,
					"roles": [{"role": "Secretaria"}],
				}
			).insert(ignore_permissions=True)

	def _insert_beca(self, socio_name: str, **overrides):
		payload = {
			"doctype": "Beca Socio",
			"socio": socio_name,
			"tipo_beca": "Total",
			"fecha_desde": "2026-07-01",
			"fecha_hasta": "2026-12-31",
			"estado": "Activa",
		}
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def test_list_becas_socio_desk_incluye_vigencia(self) -> None:
		socio = insert_socio(dni="75004001", email="beca.desk@example.com")
		beca = self._insert_beca(
			socio.name,
			tipo_beca="Parcial Porcentaje",
			pct_cuota_social=50,
			pct_arancel=25,
		)

		frappe.set_user(self._secretaria)
		try:
			rows = list_becas_socio_desk(socio.name, reference_date="2026-08-15")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row["name"], beca.name)
		self.assertEqual(row["tipo_beca"], "Parcial Porcentaje")
		self.assertEqual(row["pct_cuota_social"], 50.0)
		self.assertEqual(row["pct_arancel"], 25.0)
		self.assertEqual(row["vigencia_label"], "Vigente")

	def test_list_becas_vencida_por_fecha(self) -> None:
		socio = insert_socio(dni="75004002", email="beca.venc@example.com")
		self._insert_beca(
			socio.name,
			fecha_desde="2026-01-01",
			fecha_hasta="2026-03-31",
			estado="Activa",
		)

		frappe.set_user(self._secretaria)
		try:
			rows = list_becas_socio_desk(socio.name, reference_date="2026-08-01")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(rows[0]["vigencia_label"], "Vencida")

	def test_list_becas_api_whitelist(self) -> None:
		from club_management.members.api.socio_operaciones_desk import list_becas_socio

		socio = insert_socio(dni="75004003", email="beca.api@example.com")
		self._insert_beca(socio.name)

		frappe.set_user(self._secretaria)
		try:
			rows = list_becas_socio(socio=socio.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(len(rows), 1)

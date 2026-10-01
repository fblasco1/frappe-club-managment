"""Tests Bonificacion Recurrente (spec gimnasio_cobro_socios_no_socios.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.services.inscripcion_socio import resolve_monto_arancel_inscripcion
from club_management.members.services.cobranza_manual import build_invoice_items_for_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)

ACTIVIDAD_GYM = "Gimnasio Fitness"
GRUPO_GYM_SOCIO = f"{ACTIVIDAD_GYM} / Socio"
REF = "2026-10-01"


class TestBonificacionRecurrente(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		seed_estructura_actividades_completa(crear_equipos=False)
		sync_cuotas_sociales_club()

	def _socio_gym(self, dni: str, email: str) -> tuple[str, str]:
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test bonificación recurrente")
		ins = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": ACTIVIDAD_GYM,
				"grupo_actividad": GRUPO_GYM_SOCIO,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)
		return socio.name, ins.name

	def _bonif(self, socio: str, **overrides):
		payload = {
			"doctype": "Bonificacion Recurrente",
			"socio": socio,
			"actividad": ACTIVIDAD_GYM,
			"tipo_descuento": "Porcentaje",
			"valor": 10,
			"fecha_desde": "2026-09-01",
			"estado": "Activa",
			"motivo": "Descuento gimnasio",
		}
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def _linea_gym(self, socio: str, ins: str) -> dict | None:
		item_code, _monto = resolve_monto_arancel_inscripcion(ins)
		items = build_invoice_items_for_socio(socio, reference_date=REF, excluir_ya_facturados=False)
		return next((row for row in items if row["item_code"] == item_code), None)

	def test_aplica_10_por_ciento_al_arancel_gym(self) -> None:
		socio, ins = self._socio_gym("78001001", "bre.ok@example.com")
		_item, monto = resolve_monto_arancel_inscripcion(ins)
		self._bonif(socio)
		linea = self._linea_gym(socio, ins)
		self.assertIsNotNone(linea)
		self.assertAlmostEqual(flt(linea["rate"]), flt(monto) * 0.9, places=2)
		self.assertIn("bonif", linea["description"].lower())

	def test_no_aplica_a_cuota_social(self) -> None:
		socio, _ins = self._socio_gym("78001002", "bre.cuota@example.com")
		sin = {r["item_code"]: r["rate"] for r in build_invoice_items_for_socio(socio, reference_date=REF)}
		self._bonif(socio)
		con = {r["item_code"]: r["rate"] for r in build_invoice_items_for_socio(socio, reference_date=REF)}
		item_cuota = frappe.get_single("Club Settings").item_cuota_social
		self.assertEqual(sin.get(item_cuota), con.get(item_cuota))

	def test_monto_fijo(self) -> None:
		socio, ins = self._socio_gym("78001003", "bre.fijo@example.com")
		_item, monto = resolve_monto_arancel_inscripcion(ins)
		self._bonif(socio, tipo_descuento="Monto fijo", valor=1000)
		linea = self._linea_gym(socio, ins)
		self.assertAlmostEqual(flt(linea["rate"]), flt(monto) - 1000, places=2)

	def test_fuera_de_vigencia_no_aplica(self) -> None:
		socio, ins = self._socio_gym("78001004", "bre.vig@example.com")
		_item, monto = resolve_monto_arancel_inscripcion(ins)
		self._bonif(socio, fecha_desde="2026-01-01", fecha_hasta="2026-08-31")
		self.assertAlmostEqual(flt(self._linea_gym(socio, ins)["rate"]), flt(monto), places=2)

	def test_anulada_no_aplica(self) -> None:
		socio, ins = self._socio_gym("78001005", "bre.anul@example.com")
		_item, monto = resolve_monto_arancel_inscripcion(ins)
		self._bonif(socio, estado="Anulada")
		self.assertAlmostEqual(flt(self._linea_gym(socio, ins)["rate"]), flt(monto), places=2)

	def test_otra_actividad_no_aplica(self) -> None:
		socio, ins = self._socio_gym("78001006", "bre.otra@example.com")
		_item, monto = resolve_monto_arancel_inscripcion(ins)
		otra = frappe.db.get_value("Actividad", {"habilitada": 1, "name": ["!=", ACTIVIDAD_GYM]}, "name")
		self._bonif(socio, actividad=otra)
		self.assertAlmostEqual(flt(self._linea_gym(socio, ins)["rate"]), flt(monto), places=2)

	def test_beca_vigente_ignora_bonificacion(self) -> None:
		if not frappe.db.exists("DocType", "Beca Socio"):
			self.skipTest("Beca Socio no instalado")
		socio, ins = self._socio_gym("78001007", "bre.beca@example.com")
		_item, monto = resolve_monto_arancel_inscripcion(ins)
		frappe.get_doc(
			{
				"doctype": "Beca Socio",
				"socio": socio,
				"tipo_beca": "Parcial Porcentaje",
				"pct_cuota_social": 0,
				"pct_arancel": 50,
				"fecha_desde": "2026-06-01",
				"fecha_hasta": "2026-12-31",
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)
		self._bonif(socio)
		self.assertAlmostEqual(flt(self._linea_gym(socio, ins)["rate"]), flt(monto) * 0.5, places=2)

	def test_solapamiento_rechazado(self) -> None:
		socio, _ins = self._socio_gym("78001008", "bre.solap@example.com")
		self._bonif(socio, fecha_desde="2026-06-01")
		with self.assertRaises(frappe.ValidationError):
			self._bonif(socio, fecha_desde="2026-09-01")

	def test_no_solapa_si_la_anterior_vence(self) -> None:
		socio, _ins = self._socio_gym("78001009", "bre.nosolap@example.com")
		self._bonif(socio, fecha_desde="2026-01-01", fecha_hasta="2026-05-31")
		self.assertTrue(self._bonif(socio, fecha_desde="2026-06-01").name)

	def test_porcentaje_invalido(self) -> None:
		socio, _ins = self._socio_gym("78001010", "bre.pct@example.com")
		with self.assertRaises(frappe.ValidationError):
			self._bonif(socio, valor=150)

	def test_socio_solo_ve_las_propias(self) -> None:
		from club_management.members.services.user_provisioning import provision_user_for_socio

		ensure_role_socio_exists()
		a, _ = self._socio_gym("78001011", "bre.a@example.com")
		b, _ = self._socio_gym("78001012", "bre.b@example.com")
		bon_a = self._bonif(a)
		bon_b = self._bonif(b)
		provision_user_for_socio(a)
		user_a = frappe.db.get_value("Socio", a, "user")
		previous = frappe.session.user
		frappe.set_user(user_a)
		try:
			names = frappe.get_list("Bonificacion Recurrente", pluck="name")
			self.assertIn(bon_a.name, names)
			self.assertNotIn(bon_b.name, names)
			self.assertFalse(frappe.has_permission("Bonificacion Recurrente", "read", doc=bon_b.name))
			self.assertFalse(frappe.has_permission("Bonificacion Recurrente", "create"))
		finally:
			frappe.set_user(previous)

"""Tests API portal de reservas de espacios (SP-3 / SP-7).

Spec: `club_management/specs/reservas_espacio_portal.md`
"""

from __future__ import annotations

import contextlib
import importlib
from types import ModuleType
from typing import Any, Iterator

import frappe
from frappe.utils import flt

from club_management.members.services.user_provisioning import provision_user_for_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)
from club_management.spaces.helpers import insert_espacio


API_MODULE = "club_management.spaces.api.portal_reservas"
ITEM_ALQUILER_SOCIO = "ICDPE-ALQ-ARS-TEMP"


@contextlib.contextmanager
def as_user(user: str) -> Iterator[None]:
	previous = frappe.session.user
	try:
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(previous)


def portal_api() -> ModuleType:
	return importlib.import_module(API_MODULE)


def _activate_socio(socio_name: str, *, numero: int, estado: str = "Activo") -> None:
	frappe.db.set_value(
		"Socio",
		socio_name,
		{"numero_socio": numero, "categoria": "Activo", "estado": estado},
		update_modified=False,
	)


def _ensure_alquiler_item(*, rate: float = 15000.0) -> str:
	if frappe.db.exists("Item", ITEM_ALQUILER_SOCIO):
		frappe.db.set_value("Item", ITEM_ALQUILER_SOCIO, "standard_rate", rate, update_modified=False)
		return ITEM_ALQUILER_SOCIO
	group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": ITEM_ALQUILER_SOCIO,
			"item_name": "Alquiler canchas / espacios (ARS) — Temporal",
			"item_group": group,
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": rate,
		}
	).insert(ignore_permissions=True)
	return ITEM_ALQUILER_SOCIO


class TestPortalReservas(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_socio_exists()
		_ensure_alquiler_item()

		self.espacio = insert_espacio(
			"Cancha Portal Reserva",
			tipo="Cancha",
			alquilable=1,
			habilitado=1,
		)
		self.espacio_no_alq = insert_espacio(
			"Gimnasio No Alquilable Portal",
			tipo="Gimnasio",
			alquilable=0,
			habilitado=1,
		)

		self.socio_a = insert_socio(
			dni="79110001",
			email="reserva.a@example.com",
			nombre="Ana",
			apellido="Reserva",
		)
		provision_user_for_socio(self.socio_a.name)
		self.socio_a.reload()
		_activate_socio(self.socio_a.name, numero=79110001, estado="Activo")
		self.socio_a.reload()

		self.socio_b = insert_socio(
			dni="79110002",
			email="reserva.b@example.com",
			nombre="Bruno",
			apellido="Ajeno",
		)
		provision_user_for_socio(self.socio_b.name)
		self.socio_b.reload()
		_activate_socio(self.socio_b.name, numero=79110002, estado="Activo")
		self.socio_b.reload()

	def _solicitar(
		self,
		*,
		espacio: str | None = None,
		fecha: str = "2026-10-15",
		hora_inicio: str = "18:00:00",
		hora_fin: str = "19:00:00",
	) -> dict[str, Any]:
		return portal_api().solicitar_reserva_espacio(
			espacio=espacio or self.espacio,
			fecha=fecha,
			hora_inicio=hora_inicio,
			hora_fin=hora_fin,
		)

	def test_reserva_exitosa_bloquea_slot_y_genera_cargo(self) -> None:
		with as_user(self.socio_a.user):
			result = self._solicitar()

		self.assertEqual(result["status"], "ok")
		reserva_name = result["reserva"]
		self.assertTrue(frappe.db.exists("Reserva Espacio", reserva_name))
		doc = frappe.get_doc("Reserva Espacio", reserva_name)
		self.assertEqual(doc.tipo, "Alquiler socio")
		self.assertEqual(doc.estado, "Pendiente")
		self.assertEqual(doc.socio, self.socio_a.name)
		self.assertEqual(doc.espacio, self.espacio)
		self.assertEqual(str(doc.fecha), "2026-10-15")
		self.assertTrue(flt(doc.monto_arancel) > 0)
		self.assertTrue(doc.cargo_socio)
		self.assertTrue(frappe.db.exists("Cargo Socio", doc.cargo_socio))
		cargo = frappe.get_doc("Cargo Socio", doc.cargo_socio)
		self.assertEqual(cargo.estado, "Pendiente")
		self.assertEqual(cargo.socio, self.socio_a.name)
		self.assertFalse(cargo.sales_invoice)

		# Segunda solicitud misma franja debe fallar (slot bloqueado)
		with as_user(self.socio_b.user):
			with self.assertRaises(frappe.ValidationError):
				self._solicitar()

	def test_rechazo_por_solapamiento_con_fixture(self) -> None:
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": self.espacio,
				"fecha": "2026-10-15",
				"hora_desde": "18:00:00",
				"hora_hasta": "20:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "FMV Sub 15 vs Rival",
				"origen_fixture": "fmv_voley",
				"id_externo_fixture": "fmv-portal-test-001",
			}
		).insert(ignore_permissions=True)

		with as_user(self.socio_a.user):
			with self.assertRaises(frappe.ValidationError):
				self._solicitar(hora_inicio="18:30:00", hora_fin="19:30:00")

		self.assertFalse(
			frappe.db.exists(
				"Reserva Espacio",
				{"socio": self.socio_a.name, "tipo": "Alquiler socio", "estado": "Pendiente"},
			)
		)

	def test_rechazo_por_socio_no_activo(self) -> None:
		_activate_socio(self.socio_a.name, numero=79110001, estado="Pendiente de Inscripción")
		self.socio_a.reload()

		with as_user(self.socio_a.user):
			with self.assertRaises((frappe.ValidationError, frappe.PermissionError)):
				self._solicitar()

		self.assertFalse(
			frappe.db.exists(
				"Reserva Espacio",
				{"socio": self.socio_a.name, "tipo": "Alquiler socio"},
			)
		)

	def test_aislamiento_usuario_no_expone_reserva_ajena(self) -> None:
		with as_user(self.socio_a.user):
			created = self._solicitar()

		with as_user(self.socio_b.user):
			propias = portal_api().list_reservas_propias()
			nombres = {row["name"] for row in propias}
			self.assertNotIn(created["reserva"], nombres)
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError, TypeError)):
				portal_api().get_reserva_propia(created["reserva"])

	def test_disponibilidad_marca_ocupado_y_filtra_tipo(self) -> None:
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": self.espacio,
				"fecha": "2026-10-16",
				"hora_desde": "10:00:00",
				"hora_hasta": "11:00:00",
				"tipo": "Bloqueo",
				"estado": "Confirmada",
				"motivo": "Mantenimiento",
			}
		).insert(ignore_permissions=True)

		with as_user(self.socio_a.user):
			payload = portal_api().get_espacios_disponibles(
				fecha="2026-10-16",
				tipo_espacio="Cancha",
			)

		espacios = {row["espacio"]: row for row in payload["espacios"]}
		self.assertIn(self.espacio, espacios)
		self.assertNotIn(self.espacio_no_alq, espacios)
		slots = espacios[self.espacio]["slots"]
		ocupado = next(
			s
			for s in slots
			if str(s["hora_inicio"])[:5] == "10:00" and str(s["hora_fin"])[:5] == "11:00"
		)
		self.assertEqual(ocupado["estado"], "ocupado")
		libre = next(
			s
			for s in slots
			if str(s["hora_inicio"])[:5] == "11:00" and str(s["hora_fin"])[:5] == "12:00"
		)
		self.assertEqual(libre["estado"], "libre")

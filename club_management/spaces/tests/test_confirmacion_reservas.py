"""Tests confirmación Coordinación + comprobante (spec reservas_espacio_confirmacion.md)."""

from __future__ import annotations

import importlib
from types import ModuleType

import frappe
from frappe.utils import add_days, today

from club_management.members.services.user_provisioning import provision_user_for_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)
from club_management.spaces.availability import get_occupancy
from club_management.spaces.helpers import insert_espacio, make_coordinacion_user
from club_management.spaces.tests.test_portal_reservas import (
	_activate_socio,
	_ensure_alquiler_item,
	as_user,
	portal_api,
)

CONFIRM_API = "club_management.spaces.api.confirmacion_reservas"


def confirm_api() -> ModuleType:
	return importlib.import_module(CONFIRM_API)


class TestConfirmacionReservas(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_socio_exists()
		_ensure_alquiler_item()
		self.espacio = insert_espacio(
			"Cancha Confirmacion",
			tipo="Cancha",
			alquilable=1,
			habilitado=1,
		)
		self.fecha = add_days(today(), 10)
		self.coord = make_coordinacion_user("coord.confirm@example.com")

		self.socio = insert_socio(
			dni="79220001",
			email="confirm.socio@example.com",
			nombre="Carla",
			apellido="Confirm",
		)
		provision_user_for_socio(self.socio.name)
		self.socio.reload()
		_activate_socio(self.socio.name, numero=79220001, estado="Activo")
		self.user_socio = self.socio.user

		self.otro = insert_socio(
			dni="79220002",
			email="confirm.otro@example.com",
			nombre="Otro",
			apellido="Socio",
		)
		provision_user_for_socio(self.otro.name)
		self.otro.reload()
		_activate_socio(self.otro.name, numero=79220002, estado="Activo")
		self.user_otro = self.otro.user

	def _solicitar(self, user: str, *, hora_inicio: str = "10:00:00", hora_fin: str = "11:00:00") -> str:
		with as_user(user):
			out = portal_api().solicitar_reserva_espacio(
				espacio=self.espacio,
				fecha=str(self.fecha),
				hora_inicio=hora_inicio,
				hora_fin=hora_fin,
			)
		return out["reserva"]

	def test_adjuntar_comprobante_propio(self) -> None:
		reserva = self._solicitar(self.user_socio)
		with as_user(self.user_socio):
			res = portal_api().adjuntar_comprobante_reserva(
				reserva=reserva,
				file_url="/files/comprobante-test.pdf",
			)
		self.assertEqual(res["status"], "ok")
		doc = frappe.get_doc("Reserva Espacio", reserva)
		self.assertEqual(doc.comprobante, "/files/comprobante-test.pdf")
		self.assertTrue(doc.fecha_comprobante)
		self.assertEqual(doc.estado, "Pendiente")

	def test_adjuntar_comprobante_ajeno_falla(self) -> None:
		reserva = self._solicitar(self.user_socio)
		with as_user(self.user_otro), self.assertRaises(frappe.PermissionError):
			portal_api().adjuntar_comprobante_reserva(
				reserva=reserva,
				file_url="/files/otro.pdf",
			)

	def test_coordinacion_confirma(self) -> None:
		reserva = self._solicitar(self.user_socio)
		with as_user(self.coord):
			out = confirm_api().confirmar_reserva_espacio(reserva)
		self.assertEqual(out["estado"], "Confirmada")
		self.assertEqual(frappe.db.get_value("Reserva Espacio", reserva, "estado"), "Confirmada")
		occ = get_occupancy(self.espacio, self.fecha)
		self.assertTrue(any(o.get("name") == reserva for o in occ))

	def test_coordinacion_rechaza_libera_slot(self) -> None:
		reserva = self._solicitar(self.user_socio)
		with as_user(self.coord):
			out = confirm_api().rechazar_reserva_espacio(reserva, motivo="Horario no disponible")
		self.assertEqual(out["estado"], "Cancelada")
		doc = frappe.get_doc("Reserva Espacio", reserva)
		self.assertEqual(doc.estado, "Cancelada")
		self.assertEqual(doc.motivo_rechazo, "Horario no disponible")
		self.assertFalse(doc.slot_key)
		occ = get_occupancy(self.espacio, self.fecha)
		self.assertFalse(any(o.get("name") == reserva for o in occ))

	def test_guest_no_lista_ni_confirma(self) -> None:
		reserva = self._solicitar(self.user_socio)
		with as_user("Guest"), self.assertRaises(frappe.PermissionError):
			confirm_api().list_reservas_pendientes_confirmacion()
		with as_user("Guest"), self.assertRaises(frappe.PermissionError):
			confirm_api().confirmar_reserva_espacio(reserva)

	def test_lista_incluye_pendiente(self) -> None:
		reserva = self._solicitar(self.user_socio)
		with as_user(self.coord):
			rows = confirm_api().list_reservas_pendientes_confirmacion()
		names = {r["name"] for r in rows}
		self.assertIn(reserva, names)

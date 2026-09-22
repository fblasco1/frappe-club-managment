"""Control de activación del canal de alquiler externo (flag Club Settings).

Spec: `club_management/specs/reservas_espacio_externo.md`
API: `club_management.spaces.api.externo_reservas` (alias: `external_booking`).
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

import frappe
from frappe.utils import add_days, today

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import get_occupancy
from club_management.spaces.helpers import insert_espacio
from club_management.spaces.services.externo_reservas import CHANNEL_DISABLED_BODY
from club_management.spaces.tests.test_portal_reservas import (
	_ensure_alquiler_item,
	as_user,
)

API_MODULE = "club_management.spaces.api.externo_reservas"


def externo_api() -> ModuleType:
	return importlib.import_module(API_MODULE)


class TestExternalBookingChannelGate(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		_ensure_alquiler_item(rate=20000.0)
		self.espacio = insert_espacio(
			"Cancha External Booking Gate",
			tipo="Cancha",
			alquilable=1,
			habilitado=1,
		)
		frappe.db.set_value(
			"Espacio",
			self.espacio,
			{"tarifa_externo": 25000.0},
			update_modified=False,
		)
		self.fecha = str(add_days(today(), 21))
		frappe.db.set_single_value("Club Settings", "espacios_reserva_externa_habilitada", 0)

	def _enable_canal(self, enabled: int = 1) -> None:
		frappe.db.set_single_value(
			"Club Settings",
			"espacios_reserva_externa_habilitada",
			enabled,
		)

	def test_flag_off_responde_channel_disabled_sin_crear_reserva(self) -> None:
		self._enable_canal(0)
		with as_user("Guest"), self.assertRaises(frappe.PermissionError) as ctx:
			externo_api().abrir_sesion_reserva_externa()
		exc = ctx.exception
		self.assertEqual(getattr(exc, "http_status_code", 403), 403)
		self.assertIn(CHANNEL_DISABLED_BODY["message"], str(exc))
		self.assertEqual(
			frappe.local.response.get("channel_disabled_body"),
			CHANNEL_DISABLED_BODY,
		)
		self.assertFalse(
			frappe.db.exists(
				"Reserva Espacio",
				{"tipo": "Alquiler externo", "espacio": self.espacio, "fecha": self.fecha},
			)
		)

	def test_flag_on_crea_pendiente_sin_solapamiento(self) -> None:
		self._enable_canal(1)
		with as_user("Guest"):
			sesion = externo_api().abrir_sesion_reserva_externa()
			token = sesion["sesion_token"]
			result: dict[str, Any] = externo_api().solicitar_reserva_externa(
				sesion_token=token,
				espacio=self.espacio,
				fecha=self.fecha,
				hora_inicio="10:00:00",
				hora_fin="11:00:00",
				arrendatario_nombre="Visitante External Booking",
				arrendatario_contacto="booking@example.com",
			)
		self.assertEqual(result["status"], "ok")
		doc = frappe.get_doc("Reserva Espacio", result["reserva"])
		self.assertEqual(doc.estado, "Pendiente")
		self.assertEqual(doc.tipo, "Alquiler externo")
		occ = get_occupancy(self.espacio, self.fecha)
		self.assertTrue(any(o.get("name") == doc.name for o in occ))

		with as_user("Guest"), self.assertRaises(frappe.ValidationError):
			externo_api().solicitar_reserva_externa(
				sesion_token=token,
				espacio=self.espacio,
				fecha=self.fecha,
				hora_inicio="10:00:00",
				hora_fin="11:00:00",
				arrendatario_nombre="Otro Visitante",
				arrendatario_contacto="otro@example.com",
			)

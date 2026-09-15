"""Tests Suspension Reserva Dia — omitir reserva solo una fecha."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import get_occupancy
from club_management.spaces.helpers import insert_espacio, make_coordinacion_user


class TestSuspensionReservaDia(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def _reserva(self, espacio: str) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-05",
				"hora_desde": "14:00:00",
				"hora_hasta": "16:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "Evento test suspensión",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_suspender_reserva_omite_ocupacion(self) -> None:
		espacio = insert_espacio("Salon Suspension Test")
		reserva = self._reserva(espacio)
		from club_management.spaces.services.suspension_reserva import upsert_suspension_reserva_dia

		name = upsert_suspension_reserva_dia(
			fecha="2026-09-05",
			reserva_espacio=reserva,
			motivo="Suspendido por coordinación",
		)
		self.assertTrue(name)

		slots = get_occupancy(espacio, "2026-09-05")
		self.assertFalse(any(s.get("name") == reserva for s in slots))
		self.assertEqual(frappe.db.get_value("Reserva Espacio", reserva, "estado"), "Confirmada")

	def test_anular_suspension_restaura_reserva(self) -> None:
		espacio = insert_espacio("Salon Suspension Restore")
		reserva = self._reserva(espacio)
		from club_management.spaces.services.suspension_reserva import upsert_suspension_reserva_dia

		name = upsert_suspension_reserva_dia(fecha="2026-09-05", reserva_espacio=reserva)
		doc = frappe.get_doc("Suspension Reserva Dia", name)
		doc.estado = "Anulada"
		doc.save(ignore_permissions=True)

		slots = get_occupancy(espacio, "2026-09-05")
		self.assertTrue(any(s.get("name") == reserva for s in slots))

	def test_api_coordinacion_puede_suspender(self) -> None:
		from club_management.spaces.api.suspension_reserva import suspender_reserva_dia

		espacio = insert_espacio("Salon Suspension API")
		reserva = self._reserva(espacio)
		make_coordinacion_user("coord.susp@example.com")
		frappe.set_user("coord.susp@example.com")
		out = suspender_reserva_dia(
			fecha="2026-09-05",
			reserva_espacio=reserva,
			motivo="API test",
		)
		self.assertTrue(out.get("name"))

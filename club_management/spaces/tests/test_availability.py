"""Tests del motor de disponibilidad (grilla vs reservas)."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import (
	assert_no_overlap_with_occupancy,
	dia_semana_de_fecha,
	find_occupancy_conflicts,
	get_occupancy,
	intervals_overlap,
	validate_time_range,
)
from club_management.spaces.services.ocupacion_dashboard import get_ocupacion_dashboard_payload
from club_management.spaces.helpers import insert_espacio


class TestAvailability(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_dia_semana_lunes(self) -> None:
		# 2026-08-31 es lunes
		self.assertEqual(dia_semana_de_fecha("2026-08-31"), "Lunes")

	def test_reserva_conflicto_con_grilla_semanal(self) -> None:
		espacio = insert_espacio(
			"Cancha Grilla Conflicto",
			horarios=[
				{
					"dia_semana": "Lunes",
					"hora_desde": "18:00:00",
					"hora_hasta": "20:00:00",
					"titulo": "Entrenamiento",
				}
			],
		)
		with self.assertRaises(frappe.ValidationError):
			assert_no_overlap_with_occupancy(espacio, "2026-08-31", "18:30:00", "19:30:00")

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Reserva Espacio",
					"espacio": espacio,
					"fecha": "2026-08-31",
					"hora_desde": "18:30:00",
					"hora_hasta": "19:30:00",
					"tipo": "Alquiler socio",
					"estado": "Confirmada",
				}
			).insert(ignore_permissions=True)

	def test_horario_cruza_medianoche_se_guarda(self) -> None:
		espacio = insert_espacio(
			"Salon Madrugada Reserva",
			tipo="Salon",
		)
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-05",
				"hora_desde": "22:00:00",
				"hora_hasta": "01:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "Evento nocturno",
			}
		).insert(ignore_permissions=True)
		slots = get_occupancy(espacio, "2026-09-05")
		self.assertTrue(any(s.get("motivo") == "Evento nocturno" for s in slots))

	def test_intervals_overlap_con_medianoche(self) -> None:
		self.assertTrue(intervals_overlap("22:00:00", "01:00:00", "23:00:00", "23:30:00"))
		self.assertFalse(intervals_overlap("22:00:00", "01:00:00", "10:00:00", "11:00:00"))
		validate_time_range("22:00:00", "01:00:00")

	def test_planilla_muestra_evento_nocturno(self) -> None:
		espacio = insert_espacio("Salon Planilla Noche", tipo="Salon")
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-05",
				"hora_desde": "22:00:00",
				"hora_hasta": "01:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "Cena larga",
			}
		).insert(ignore_permissions=True)
		payload = get_ocupacion_dashboard_payload(fecha="2026-09-05")
		bloques = [b for b in payload["bloques"] if b["espacio"] == espacio]
		self.assertEqual(len(bloques), 1)
		self.assertEqual(bloques[0]["inicio"], "22:00")
		self.assertEqual(bloques[0]["fin"], "01:00")

	def test_reserva_del_dia_anterior_solapa_madrugada(self) -> None:
		espacio = insert_espacio("Salon Cola Nocturna", tipo="Salon")
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-05",
				"hora_desde": "23:30:00",
				"hora_hasta": "01:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "Evento hasta madrugada",
			}
		).insert(ignore_permissions=True)

		conflicts = find_occupancy_conflicts(
			espacio,
			"2026-09-06",
			"00:30:00",
			"00:45:00",
		)
		self.assertEqual(len(conflicts), 1)
		self.assertEqual(conflicts[0]["tipo"], "reserva")
		self.assertTrue(any(s.get("motivo") == "Evento hasta madrugada" for s in get_occupancy(espacio, "2026-09-06")))

	def test_occupancy_incluye_grilla_y_reserva(self) -> None:
		espacio = insert_espacio(
			"Cancha Occupancy",
			horarios=[
				{
					"dia_semana": "Martes",
					"hora_desde": "09:00:00",
					"hora_hasta": "10:00:00",
				}
			],
		)
		# 2026-09-01 = martes
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-01",
				"hora_desde": "15:00:00",
				"hora_hasta": "16:00:00",
				"tipo": "Bloqueo",
				"estado": "Confirmada",
			}
		).insert(ignore_permissions=True)
		slots = get_occupancy(espacio, "2026-09-01")
		sources = {s["source"] for s in slots}
		self.assertIn("horario", sources)
		self.assertIn("reserva", sources)

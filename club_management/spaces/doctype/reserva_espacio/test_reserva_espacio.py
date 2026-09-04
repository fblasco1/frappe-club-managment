"""Tests DocType Reserva Espacio (ocupación + alquiler externo)."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import get_occupancy
from club_management.spaces.helpers import insert_espacio


class TestReservaEspacio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def _reserva(self, espacio: str, **kwargs) -> str:
		payload = {
			"doctype": "Reserva Espacio",
			"espacio": espacio,
			"fecha": "2026-09-01",
			"hora_desde": "15:00:00",
			"hora_hasta": "18:00:00",
			"tipo": "Evento club",
			"estado": "Confirmada",
			"motivo": "Cumpleaños",
		}
		payload.update(kwargs)
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_evento_club_recurrente_ocupa_viernes(self) -> None:
		espacio = insert_espacio("Salon Evento Rec")
		name = self._reserva(
			espacio,
			recurrencia_semanal=1,
			fecha=None,
			fecha_desde="2026-01-01",
			fecha_hasta="2026-12-31",
			hora_desde="20:00:00",
			hora_hasta="22:00:00",
			dias_recurrencia=[{"dia_semana": "Viernes"}],
			motivo="CENA SEMANAL VITALICIOS",
		)
		self.assertTrue(frappe.db.exists("Reserva Espacio", name))
		slots_vie = get_occupancy(espacio, "2026-08-28")
		self.assertTrue(any(s.get("name") == name for s in slots_vie))
		slots_jue = get_occupancy(espacio, "2026-08-27")
		self.assertFalse(any(s.get("name") == name for s in slots_jue))

	def test_reserva_confirmada_bloquea_slot(self) -> None:
		espacio = insert_espacio("Salon Reserva Test")
		self._reserva(espacio)
		with self.assertRaises(frappe.ValidationError):
			self._reserva(
				espacio,
				hora_desde="16:00:00",
				hora_hasta="17:00:00",
				motivo="Otro evento",
			)

	def test_borrador_y_cancelada_no_ocupan(self) -> None:
		espacio = insert_espacio("Salon Borrador Test")
		self._reserva(espacio, estado="Borrador")
		self._reserva(
			espacio,
			estado="Cancelada",
			hora_desde="15:00:00",
			hora_hasta="18:00:00",
			motivo="Cancelado",
		)
		name = self._reserva(espacio, estado="Confirmada", motivo="OK")
		self.assertTrue(frappe.db.exists("Reserva Espacio", name))

	def test_reserva_cruza_medianoche(self) -> None:
		espacio = insert_espacio("Salon Reserva Noche", tipo="Salon")
		name = self._reserva(
			espacio,
			hora_desde="22:00:00",
			hora_hasta="01:00:00",
			motivo="Fiesta",
		)
		doc = frappe.get_doc("Reserva Espacio", name)
		self.assertEqual(str(doc.hora_desde)[:5], "22:00")
		self.assertEqual(str(doc.hora_hasta)[:5], "01:00")

	def test_tipos_internos_validos(self) -> None:
		espacio = insert_espacio("Salon Tipos Test")
		for tipo in ("Alquiler socio", "Evento club", "Bloqueo"):
			self._reserva(
				espacio,
				tipo=tipo,
				estado="Borrador",
				fecha="2026-09-02",
				hora_desde="10:00:00",
				hora_hasta="11:00:00",
				motivo=tipo,
			)

	def test_alquiler_temporal_requiere_alquilable(self) -> None:
		no_alq = insert_espacio("Cancha No Alq", alquilable=0)
		with self.assertRaises(frappe.ValidationError):
			self._reserva(
				no_alq,
				tipo="Alquiler externo",
				modalidad_alquiler="Temporal",
				arrendatario_nombre="Visitante",
				estado="Confirmada",
				fecha="2026-09-10",
				hora_desde="18:00:00",
				hora_hasta="20:00:00",
			)

	def test_alquiler_temporal_ok(self) -> None:
		espacio = insert_espacio("Cancha Alq Temp", alquilable=1)
		name = self._reserva(
			espacio,
			tipo="Alquiler externo",
			modalidad_alquiler="Temporal",
			arrendatario_nombre="Club Visitante",
			estado="Confirmada",
			fecha="2026-09-10",
			hora_desde="18:00:00",
			hora_hasta="20:00:00",
			motivo="Amistoso",
		)
		self.assertTrue(frappe.db.exists("Reserva Espacio", name))

	def test_alquiler_recurrente_ocupa_dias_del_patron(self) -> None:
		espacio = insert_espacio("Cancha Alq Rec", alquilable=1)
		# 2026-09-01 = martes; rango septiembre con Martes y Jueves
		name = self._reserva(
			espacio,
			tipo="Alquiler externo",
			modalidad_alquiler="Recurrente",
			arrendatario_nombre="Escuela Externa",
			estado="Confirmada",
			fecha=None,
			fecha_desde="2026-09-01",
			fecha_hasta="2026-09-30",
			hora_desde="19:00:00",
			hora_hasta="21:00:00",
			dias_recurrencia=[
				{"dia_semana": "Martes"},
				{"dia_semana": "Jueves"},
			],
			motivo="Entrenamiento externo",
		)
		self.assertTrue(frappe.db.exists("Reserva Espacio", name))
		# Martes 1/9 ocupa
		slots_mar = get_occupancy(espacio, "2026-09-01")
		self.assertTrue(any(s.get("source") == "reserva" and s.get("name") == name for s in slots_mar))
		# Miércoles 2/9 no
		slots_mie = get_occupancy(espacio, "2026-09-02")
		self.assertFalse(any(s.get("name") == name for s in slots_mie))
		# Conflicto otro martes
		with self.assertRaises(frappe.ValidationError):
			self._reserva(
				espacio,
				tipo="Evento club",
				estado="Confirmada",
				fecha="2026-09-08",
				hora_desde="19:30:00",
				hora_hasta="20:30:00",
				motivo="Choque",
			)

	def test_alquiler_recurrente_exige_dias(self) -> None:
		espacio = insert_espacio("Cancha Alq Rec Bad", alquilable=1)
		with self.assertRaises(frappe.ValidationError):
			self._reserva(
				espacio,
				tipo="Alquiler externo",
				modalidad_alquiler="Recurrente",
				arrendatario_nombre="Sin dias",
				estado="Borrador",
				fecha=None,
				fecha_desde="2026-09-01",
				fecha_hasta="2026-09-30",
				hora_desde="19:00:00",
				hora_hasta="21:00:00",
				dias_recurrencia=[],
			)

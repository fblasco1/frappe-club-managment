"""Tests Excepcion Horario Dia — reubicación puntual."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import get_occupancy
from club_management.spaces.helpers import insert_espacio, make_coordinacion_user
from club_management.spaces.import_horarios import CANCHA_1, CANCHA_3


class TestExcepcionHorarioDia(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not frappe.db.exists("Espacio", CANCHA_3):
			insert_espacio(
				CANCHA_3,
				tipo="Cancha",
				horarios=[
					{
						"dia_semana": "Martes",
						"hora_desde": "19:00:00",
						"hora_hasta": "21:00:00",
						"tipo_sesion": "Entrenamiento",
						"etiqueta": "U17 AZUL",
					}
				],
			)
		else:
			doc = frappe.get_doc("Espacio", CANCHA_3)
			if not any(
				h.dia_semana == "Martes"
				and str(h.hora_desde).startswith("19:00")
				and (getattr(h, "etiqueta", None) or "") == "U17 AZUL TEST EXC"
				for h in (doc.get("horarios") or [])
			):
				doc.append(
					"horarios",
					{
						"dia_semana": "Martes",
						"hora_desde": "19:00:00",
						"hora_hasta": "21:00:00",
						"tipo_sesion": "Entrenamiento",
						"etiqueta": "U17 AZUL TEST EXC",
					},
				)
				doc.flags.skip_spaces_grid_reserva_check = True
				doc.save(ignore_permissions=True)
		if not frappe.db.exists("Espacio", CANCHA_1):
			insert_espacio(CANCHA_1, tipo="Cancha")

	def _horario_row(self) -> str:
		doc = frappe.get_doc("Espacio", CANCHA_3)
		for h in doc.get("horarios") or []:
			if h.dia_semana == "Martes" and (
				(getattr(h, "etiqueta", None) or "") in {"U17 AZUL", "U17 AZUL TEST EXC"}
			):
				return h.name
		self.fail("No hay horario de prueba en Cancha 3")

	def test_reubicar_omite_grilla_origen_y_ocupa_destino(self) -> None:
		# 2026-10-20 = martes
		row = self._horario_row()
		from club_management.spaces.services.excepcion_horario import upsert_excepcion_horario_dia

		exc = upsert_excepcion_horario_dia(
			fecha="2026-10-20",
			espacio_origen=CANCHA_3,
			horario_row=row,
			espacio_destino=CANCHA_1,
			hora_desde="18:00:00",
			hora_hasta="19:00:00",
			motivo="Partido local",
		)
		self.assertTrue(exc)

		occ_origen = get_occupancy(CANCHA_3, "2026-10-20")
		grilla_origen = [
			s
			for s in occ_origen
			if s.get("source") == "horario" and s.get("row_name") == row
		]
		self.assertEqual(grilla_origen, [])

		occ_dest = get_occupancy(CANCHA_1, "2026-10-20")
		exc_slots = [s for s in occ_dest if s.get("source") == "excepcion"]
		self.assertEqual(len(exc_slots), 1)
		self.assertEqual(str(exc_slots[0]["hora_desde"]), "18:00:00")
		self.assertEqual(str(exc_slots[0]["hora_hasta"]), "19:00:00")

	def test_anular_restaura_grilla(self) -> None:
		row = self._horario_row()
		from club_management.spaces.services.excepcion_horario import upsert_excepcion_horario_dia

		name = upsert_excepcion_horario_dia(
			fecha="2026-10-27",
			espacio_origen=CANCHA_3,
			horario_row=row,
			espacio_destino=CANCHA_3,
			hora_desde="19:00:00",
			hora_hasta="20:00:00",
		)
		doc = frappe.get_doc("Excepcion Horario Dia", name)
		doc.estado = "Anulada"
		doc.save(ignore_permissions=True)

		occ = get_occupancy(CANCHA_3, "2026-10-27")
		grilla = [s for s in occ if s.get("source") == "horario" and s.get("row_name") == row]
		self.assertEqual(len(grilla), 1)
		self.assertTrue(str(grilla[0]["hora_hasta"]).startswith("21:00"))

	def test_api_coordinacion_puede_reubicar(self) -> None:
		from club_management.spaces.api.excepcion_horario import reubicar_horario_dia

		make_coordinacion_user("coord.exc@example.com")
		row = self._horario_row()
		frappe.set_user("coord.exc@example.com")
		out = reubicar_horario_dia(
			fecha="2026-11-03",
			espacio_origen=CANCHA_3,
			horario_row=row,
			espacio_destino=CANCHA_1,
			hora_desde="17:00:00",
			hora_hasta="18:30:00",
			motivo="Ajuste puntual",
		)
		self.assertTrue(out.get("name"))

	def test_suspender_omite_grilla_sin_destino(self) -> None:
		row = self._horario_row()
		from club_management.spaces.services.excepcion_horario import suspender_horario_dia

		exc = suspender_horario_dia(
			fecha="2026-11-10",
			espacio_origen=CANCHA_3,
			horario_row=row,
			motivo="Feriado / partido",
		)
		self.assertTrue(exc)
		doc = frappe.get_doc("Excepcion Horario Dia", exc)
		self.assertEqual(doc.accion, "Suspender")

		occ_origen = get_occupancy(CANCHA_3, "2026-11-10")
		grilla = [
			s for s in occ_origen if s.get("source") == "horario" and s.get("row_name") == row
		]
		self.assertEqual(grilla, [])
		self.assertFalse(any(s.get("source") == "excepcion" for s in occ_origen))
		self.assertFalse(any(s.get("source") == "excepcion" for s in get_occupancy(CANCHA_1, "2026-11-10")))

"""Tests eventos sociales → Reserva Evento club (import CSV)."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import get_occupancy
from club_management.spaces.import_horarios import (
	is_evento_club_social,
	load_csv_rows,
	parse_csv_row,
)


class TestEventoClubSocialParser(MembersTestCase):
	def test_detecta_cena_vitalicios(self) -> None:
		self.assertTrue(is_evento_club_social("CENA SEMANAL VITALICIOS"))
		self.assertTrue(is_evento_club_social("CENA VITALICIOS"))

	def test_detecta_centro_jubilados(self) -> None:
		self.assertTrue(is_evento_club_social("CENTRO DE JUBILADOS"))

	def test_no_marca_entrenamiento_ni_alquiler(self) -> None:
		self.assertFalse(is_evento_club_social("BASQUET U11"))
		self.assertFalse(is_evento_club_social("ALQ. CLUB VISITANTE"))

	def test_parse_fila_cena_vitalicios(self) -> None:
		row = parse_csv_row(
			{
				"Dia": "VIERNES",
				"Espacio": "SALA ALBAMONTE",
				"Horario": "DESDE 20.00",
				"Actividad": "CENA SEMANAL VITALICIOS",
				"Profesor": "",
			}
		)
		self.assertNotIsInstance(row, str)
		assert not isinstance(row, str)
		self.assertTrue(row.es_evento_club)
		self.assertEqual(row.motivo_evento, "CENA SEMANAL VITALICIOS")
		self.assertEqual(row.hora_desde, "20:00:00")
		self.assertEqual(row.hora_hasta, "22:00:00")


class TestEventoClubSocialImport(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_import_crea_reserva_evento_club_no_grilla(self) -> None:
		from club_management.spaces.import_horarios import import_horarios_csv

		if not frappe.db.exists("Espacio", "SALA ALBAMONTE"):
			frappe.get_doc(
				{
					"doctype": "Espacio",
					"titulo": "SALA ALBAMONTE",
					"tipo": "Salon",
					"habilitado": 1,
				}
			).insert(ignore_permissions=True)
		for name in frappe.get_all(
			"Reserva Espacio",
			filters={
				"espacio": "SALA ALBAMONTE",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "CENA SEMANAL VITALICIOS",
			},
			pluck="name",
		):
			frappe.delete_doc("Reserva Espacio", name, force=True, ignore_permissions=True)

		# Solo viernes para acotar
		import csv
		from pathlib import Path
		from tempfile import NamedTemporaryFile

		with NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
			writer = csv.DictWriter(
				fh,
				fieldnames=["Dia", "Espacio", "Horario", "Actividad", "Profesor"],
				delimiter=";",
			)
			writer.writeheader()
			writer.writerow(
				{
					"Dia": "VIERNES",
					"Espacio": "SALA ALBAMONTE",
					"Horario": "DESDE 20.00",
					"Actividad": "CENA SEMANAL VITALICIOS",
					"Profesor": "",
				}
			)
			tmp = Path(fh.name)

		try:
			result = import_horarios_csv(tmp, replace_weekdays=False, replace_days={"Viernes"})
			self.assertGreaterEqual(result.get("eventos_club_creados", 0), 1)
		finally:
			tmp.unlink(missing_ok=True)

		reservas = frappe.get_all(
			"Reserva Espacio",
			filters={
				"espacio": "SALA ALBAMONTE",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "CENA SEMANAL VITALICIOS",
			},
			fields=["name", "recurrencia_semanal", "hora_desde", "hora_hasta"],
		)
		self.assertEqual(len(reservas), 1)
		self.assertTrue(reservas[0].recurrencia_semanal)

		espacio = frappe.get_doc("Espacio", "SALA ALBAMONTE")
		viernes = [h for h in espacio.horarios if h.dia_semana == "Viernes"]
		titulos = " ".join((h.titulo or h.etiqueta or "") for h in viernes).upper()
		self.assertNotIn("CENA", titulos)

		# 2026-08-28 = viernes
		slots = get_occupancy("SALA ALBAMONTE", "2026-08-28")
		self.assertTrue(
			any(
				s.get("source") == "reserva"
				and s.get("tipo") == "Evento club"
				and "CENA" in (s.get("motivo") or "").upper()
				for s in slots
			)
		)

	def test_fixture_csv_tiene_cena_vitalicios(self) -> None:
		rows = load_csv_rows(
			__import__(
				"club_management.spaces.import_horarios", fromlist=["default_horarios_csv_path"]
			).default_horarios_csv_path()
		)
		eventos = [r for r in rows if not isinstance(r, str) and r.es_evento_club]
		motivos = {r.motivo_evento for r in eventos}
		self.assertIn("CENA SEMANAL VITALICIOS", motivos)

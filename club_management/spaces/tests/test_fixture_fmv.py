"""Tests importación fixtures FMV Vóley."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.fixtures.contract import ORIGIN_FMV_VOLEY
from club_management.spaces.fixtures.espacio_map import resolve_espacio
from club_management.spaces.fixtures.parse import normalize_partido
from club_management.spaces.fixtures.sources.fmv_voley import (
	FMV_VOLEY_JSON_URL,
	default_fixture_json_path,
	get_fixture_json_url,
	import_fmv_voley_json,
	sync_fmv_voley_from_url,
	validate_fixture_envelope,
)
from club_management.spaces.fixtures.upsert import find_reserva_by_fixture
from club_management.spaces.helpers import insert_espacio, make_coordinacion_user
from club_management.spaces.import_horarios import CANCHA_1, CANCHA_2
from club_management.spaces.fixtures.contract import FixturePartido, LOCALIA_LOCAL

_SAMPLE_ENVELOPE = {
	"version": 1,
	"source": ORIGIN_FMV_VOLEY,
	"generated_at": "2026-08-28T20:00:00-03:00",
	"club": "PEDRO ECHAGUE",
	"club_id_fmv": 420,
	"partidos": [
		{
			"source": ORIGIN_FMV_VOLEY,
			"external_id": "fmv-local-001",
			"fecha": "2026-11-20",
			"hora": "21:00",
			"categoria": "Sub 15",
			"equipo": "SUB 15 ECHAGÜE",
			"rival": "Rival",
			"localia": "Local",
		},
		{
			"source": ORIGIN_FMV_VOLEY,
			"external_id": "fmv-vis-002",
			"fecha": "2026-11-21",
			"hora": "18:00",
			"categoria": "Sub 13",
			"localia": "Visitante",
		},
	],
}


class TestFmvParseAndMap(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		for name in (CANCHA_1, CANCHA_2):
			if not frappe.db.exists("Espacio", name):
				insert_espacio(name, tipo="Cancha")

	def test_url_canonica_default(self) -> None:
		self.assertIn("fmv_voley_ges", get_fixture_json_url())
		self.assertEqual(get_fixture_json_url(), FMV_VOLEY_JSON_URL)

	def test_validate_envelope_version(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			validate_fixture_envelope({"version": 2, "partidos": []})

	def test_validate_envelope_rechaza_otro_club_e_ids_duplicados(self) -> None:
		other_club = {**_SAMPLE_ENVELOPE, "club_id_fmv": 999}
		with self.assertRaises(frappe.ValidationError):
			validate_fixture_envelope(other_club)

		duplicated = {
			**_SAMPLE_ENVELOPE,
			"partidos": [_SAMPLE_ENVELOPE["partidos"][0], _SAMPLE_ENVELOPE["partidos"][0]],
		}
		with self.assertRaises(frappe.ValidationError):
			validate_fixture_envelope(duplicated)

	def test_ventana_formativa_90(self) -> None:
		result = normalize_partido(
			{
				"source": ORIGIN_FMV_VOLEY,
				"external_id": "v1",
				"fecha": "2026-08-28",
				"hora": "21:00",
				"categoria": "Sub 15",
				"localia": "Local",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		self.assertEqual(result.hora_desde, "21:00:00")
		self.assertEqual(result.hora_hasta, "22:30:00")

	def test_ventana_superior_warmup_30(self) -> None:
		result = normalize_partido(
			{
				"source": ORIGIN_FMV_VOLEY,
				"external_id": "v2",
				"fecha": "2026-08-28",
				"hora": "21:00",
				"categoria": "Superior",
				"equipo": "SUPERIOR ECHAGÜE",
				"localia": "Local",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		self.assertEqual(result.hora_desde, "20:30:00")
		self.assertEqual(result.hora_hasta, "22:30:00")

	def test_espacio_superior_a_cancha_1(self) -> None:
		partido = FixturePartido(
			source=ORIGIN_FMV_VOLEY,
			external_id="e1",
			fecha="2026-08-28",
			hora_desde="21:00:00",
			hora_hasta="22:30:00",
			equipo="SUPERIOR ECHAGUE",
			localia=LOCALIA_LOCAL,
		)
		self.assertEqual(resolve_espacio(partido), CANCHA_1)

	def test_espacio_superior_b_y_default_cancha_2(self) -> None:
		b = FixturePartido(
			source=ORIGIN_FMV_VOLEY,
			external_id="e2",
			fecha="2026-08-28",
			hora_desde="21:00:00",
			hora_hasta="22:30:00",
			equipo="SUPERIOR ECHAGÜE B",
			localia=LOCALIA_LOCAL,
		)
		rest = FixturePartido(
			source=ORIGIN_FMV_VOLEY,
			external_id="e3",
			fecha="2026-08-28",
			hora_desde="21:00:00",
			hora_hasta="22:30:00",
			equipo="SUB 15 ECHAGÜE",
			localia=LOCALIA_LOCAL,
		)
		self.assertEqual(resolve_espacio(b), CANCHA_2)
		self.assertEqual(resolve_espacio(rest), CANCHA_2)


class TestFmvImport(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		for name in (CANCHA_1, CANCHA_2):
			if not frappe.db.exists("Espacio", name):
				insert_espacio(name, tipo="Cancha")

	@patch("club_management.spaces.fixtures.sources.fmv_voley.fetch_fixture_json")
	def test_sync_local_omite_visitante(self, mock_fetch) -> None:
		mock_fetch.return_value = _SAMPLE_ENVELOPE
		result = sync_fmv_voley_from_url("https://example.test/fmv.json")
		self.assertEqual(result["creados"], 1)
		self.assertTrue(find_reserva_by_fixture(ORIGIN_FMV_VOLEY, "fmv-local-001"))
		self.assertFalse(find_reserva_by_fixture(ORIGIN_FMV_VOLEY, "fmv-vis-002"))

	def test_import_sample_idempotente(self) -> None:
		path = default_fixture_json_path()
		first = import_fmv_voley_json(path)
		second = import_fmv_voley_json(path)
		self.assertGreaterEqual(first["creados"] + first["actualizados"], 1)
		self.assertEqual(second["creados"], 0)
		self.assertGreaterEqual(second["actualizados"], 1)

	def test_local_que_pasa_a_visitante_se_cancela(self) -> None:
		local = {**_SAMPLE_ENVELOPE, "partidos": [_SAMPLE_ENVELOPE["partidos"][0]]}
		import_fmv_voley_json_data = import_fmv_voley_json
		with patch(
			"club_management.spaces.fixtures.sources.fmv_voley.load_json_file",
			return_value=local,
		):
			import_fmv_voley_json_data(cancel_missing=True)

		visitor_row = {**_SAMPLE_ENVELOPE["partidos"][0], "localia": "Visitante"}
		visitor = {**_SAMPLE_ENVELOPE, "partidos": [visitor_row]}
		with patch(
			"club_management.spaces.fixtures.sources.fmv_voley.load_json_file",
			return_value=visitor,
		):
			import_fmv_voley_json_data(cancel_missing=True)

		name = find_reserva_by_fixture(ORIGIN_FMV_VOLEY, "fmv-local-001")
		self.assertEqual(frappe.db.get_value("Reserva Espacio", name, "estado"), "Cancelada")

	def test_feed_vacio_cancela_reservas_futuras(self) -> None:
		local = {**_SAMPLE_ENVELOPE, "partidos": [_SAMPLE_ENVELOPE["partidos"][0]]}
		with patch(
			"club_management.spaces.fixtures.sources.fmv_voley.load_json_file",
			return_value=local,
		):
			import_fmv_voley_json(cancel_missing=True)

		empty = {**_SAMPLE_ENVELOPE, "partidos": []}
		with patch(
			"club_management.spaces.fixtures.sources.fmv_voley.load_json_file",
			return_value=empty,
		):
			result = import_fmv_voley_json(cancel_missing=True)

		name = find_reserva_by_fixture(ORIGIN_FMV_VOLEY, "fmv-local-001")
		self.assertEqual(result["cancelados"], 1)
		self.assertEqual(frappe.db.get_value("Reserva Espacio", name, "estado"), "Cancelada")

	def test_whitelist_coordinacion(self) -> None:
		from club_management.spaces.api.fixtures_desk import sync_fixtures_fmv

		user = make_coordinacion_user("coord.fmv@example.com")
		frappe.set_user(user)
		try:
			with patch(
				"club_management.spaces.fixtures.sources.fmv_voley.fetch_fixture_json",
				return_value=_SAMPLE_ENVELOPE,
			):
				result = sync_fixtures_fmv(cancel_missing=0)
			self.assertIn("creados", result)
		finally:
			frappe.set_user("Administrator")

	def test_coordinacion_no_puede_reemplazar_url_o_ruta_local(self) -> None:
		from club_management.spaces.api.fixtures_desk import sync_fixtures_fmv

		user = make_coordinacion_user("coord.fmv.security@example.com")
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				sync_fixtures_fmv(url="https://127.0.0.1/internal.json")
			with self.assertRaises(frappe.PermissionError):
				sync_fixtures_fmv(file_path="/etc/passwd")
		finally:
			frappe.set_user("Administrator")

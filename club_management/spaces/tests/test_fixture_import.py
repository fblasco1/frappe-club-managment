"""Tests importación fixtures / partidos FeBAMBA GES."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.fixtures.contract import ORIGIN_FEBAMBA_GES
from club_management.spaces.fixtures.parse import normalize_partido, parse_fecha_iso, parse_hora_desde
from club_management.spaces.fixtures.sources.febamba_ges import (
	FEBAMBA_GES_JSON_URL,
	default_fixture_json_path,
	fetch_fixture_json,
	get_fixture_json_url,
	import_febamba_ges_json,
	sync_febamba_ges_from_url,
	validate_fixture_envelope,
)
from club_management.spaces.fixtures.upsert import find_reserva_by_fixture, import_fixture_payload
from club_management.spaces.helpers import insert_espacio, make_coordinacion_user
from club_management.spaces.import_horarios import CANCHA_3
from club_management.spaces.services.ocupacion_dashboard import get_ocupacion_dashboard_payload

_SAMPLE_ENVELOPE = {
	"version": 1,
	"source": ORIGIN_FEBAMBA_GES,
	"generated_at": "2026-08-26T20:00:00-03:00",
	"club": "PEDRO ECHAGUE",
	"partidos": [
		{
			"source": ORIGIN_FEBAMBA_GES,
			"external_id": "url-sync-local-001",
			"fecha": "2026-11-10",
			"hora": "20:00",
			"categoria": "U17",
			"tira": "AZUL",
			"rival": "Rival URL",
			"localia": "Local",
			"espacio": None,
		},
		{
			"source": ORIGIN_FEBAMBA_GES,
			"external_id": "url-sync-vis-002",
			"fecha": "2026-11-11",
			"hora": "18:00",
			"categoria": "U15",
			"rival": "Fuera",
			"localia": "Visitante",
			"espacio": None,
		},
	],
}


class TestFixtureParse(MembersTestCase):
	def test_parse_fecha_ddmmyyyy_e_iso(self) -> None:
		self.assertEqual(parse_fecha_iso("06/09/2026"), "2026-09-06")
		self.assertEqual(parse_fecha_iso("2026-09-06"), "2026-09-06")

	def test_parse_hora_ges(self) -> None:
		self.assertEqual(parse_hora_desde("20:00"), "20:00:00")
		self.assertEqual(parse_hora_desde("20 A 22"), "20:00:00")

	def test_normalize_visitante(self) -> None:
		result = normalize_partido(
			{
				"source": "febamba_ges",
				"external_id": "x1",
				"fecha": "06/09/2026",
				"hora": "18:00",
				"localia": "Visitante",
				"categoria": "U15",
				"rival": "Rival",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		self.assertEqual(result.localia, "visitante")

	def test_validate_envelope_version(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			validate_fixture_envelope({"version": 2, "partidos": []})

	def test_url_canonica_default(self) -> None:
		self.assertIn("formativas_ges", get_fixture_json_url())
		self.assertEqual(get_fixture_json_url(), FEBAMBA_GES_JSON_URL)


class TestFixtureUrlSync(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not frappe.db.exists("Espacio", CANCHA_3):
			insert_espacio(CANCHA_3, tipo="Cancha")

	@patch("club_management.spaces.fixtures.sources.febamba_ges.fetch_fixture_json")
	def test_sync_desde_url_importa_local_omite_visitante(self, mock_fetch) -> None:
		mock_fetch.return_value = _SAMPLE_ENVELOPE
		result = sync_febamba_ges_from_url("https://example.test/fixture.json")
		mock_fetch.assert_called_once_with("https://example.test/fixture.json")
		self.assertEqual(result["creados"], 1)
		self.assertIn("source_url", result)
		self.assertTrue(find_reserva_by_fixture(ORIGIN_FEBAMBA_GES, "url-sync-local-001"))
		self.assertFalse(find_reserva_by_fixture(ORIGIN_FEBAMBA_GES, "url-sync-vis-002"))

	@patch("club_management.spaces.fixtures.sources.febamba_ges.requests.get")
	def test_fetch_fixture_json_valida_version(self, mock_get) -> None:
		mock_get.return_value.raise_for_status = lambda: None
		mock_get.return_value.json.return_value = {"version": 2, "partidos": []}
		with self.assertRaises(frappe.ValidationError):
			fetch_fixture_json("https://example.test/bad.json")


class TestFixtureEspacioMap(MembersTestCase):
	def test_basquet_default_cancha_3(self) -> None:
		from club_management.spaces.fixtures.espacio_map import BASQUET_ESPACIO_DEFAULT, resolve_espacio
		from club_management.spaces.fixtures.contract import FixturePartido, LOCALIA_LOCAL

		if not frappe.db.exists("Espacio", CANCHA_3):
			insert_espacio(CANCHA_3, tipo="Cancha")
		partido = FixturePartido(
			source=ORIGIN_FEBAMBA_GES,
			external_id="map-001",
			fecha="2026-09-01",
			hora_desde="20:00:00",
			hora_hasta="22:00:00",
			categoria="U17",
			localia=LOCALIA_LOCAL,
		)
		self.assertEqual(resolve_espacio(partido), BASQUET_ESPACIO_DEFAULT)
		self.assertEqual(BASQUET_ESPACIO_DEFAULT, CANCHA_3)


class TestFixtureUpsert(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not frappe.db.exists("Espacio", CANCHA_3):
			insert_espacio(CANCHA_3, tipo="Cancha")

	def test_upsert_local_crea_reserva_confirmada(self) -> None:
		result = import_fixture_payload(
			{
				"source": ORIGIN_FEBAMBA_GES,
				"partidos": [
					{
						"external_id": "test-upsert-001",
						"fecha": "2026-10-15",
						"hora": "20:00",
						"categoria": "U17",
						"tira": "AZUL",
						"rival": "Rival Test",
						"localia": "Local",
					}
				],
			}
		)
		self.assertEqual(result["creados"], 1)
		name = find_reserva_by_fixture(ORIGIN_FEBAMBA_GES, "test-upsert-001")
		self.assertTrue(name)
		doc = frappe.get_doc("Reserva Espacio", name)
		self.assertEqual(doc.estado, "Confirmada")
		self.assertEqual(doc.tipo, "Evento club")
		self.assertEqual(doc.espacio, CANCHA_3)
		self.assertIn("U17", doc.motivo)
		self.assertIn("Rival Test", doc.motivo)

	def test_idempotencia_no_duplica(self) -> None:
		payload = {
			"source": ORIGIN_FEBAMBA_GES,
			"partidos": [
				{
					"external_id": "test-idem-002",
					"fecha": "2026-10-16",
					"hora": "19:00",
					"categoria": "U15",
					"rival": "Otro",
					"localia": "Local",
				}
			],
		}
		r1 = import_fixture_payload(payload)
		r2 = import_fixture_payload(payload)
		self.assertEqual(r1["creados"], 1)
		self.assertEqual(r2["creados"], 0)
		self.assertEqual(r2["actualizados"], 1)
		count = frappe.db.count(
			"Reserva Espacio",
			{"origen_fixture": ORIGIN_FEBAMBA_GES, "id_externo_fixture": "test-idem-002"},
		)
		self.assertEqual(count, 1)

	def test_visitante_no_crea_reserva(self) -> None:
		result = import_fixture_payload(
			{
				"source": ORIGIN_FEBAMBA_GES,
				"partidos": [
					{
						"external_id": "test-vis-003",
						"fecha": "2026-10-17",
						"hora": "18:00",
						"categoria": "U13",
						"rival": "Fuera",
						"localia": "Visitante",
					}
				],
			}
		)
		self.assertEqual(result["creados"], 0)
		self.assertGreaterEqual(len(result["omitidos"]), 1)
		self.assertFalse(find_reserva_by_fixture(ORIGIN_FEBAMBA_GES, "test-vis-003"))

	def test_cancel_missing_futuros(self) -> None:
		import_fixture_payload(
			{
				"source": ORIGIN_FEBAMBA_GES,
				"partidos": [
					{
						"external_id": "test-cancel-a",
						"fecha": "2026-12-01",
						"hora": "20:00",
						"categoria": "U17",
						"rival": "A",
						"localia": "Local",
					},
					{
						"external_id": "test-cancel-b",
						"fecha": "2026-12-02",
						"hora": "20:00",
						"categoria": "U17",
						"rival": "B",
						"localia": "Local",
					},
				],
			}
		)
		result = import_fixture_payload(
			{
				"source": ORIGIN_FEBAMBA_GES,
				"partidos": [
					{
						"external_id": "test-cancel-a",
						"fecha": "2026-12-01",
						"hora": "20:00",
						"categoria": "U17",
						"rival": "A",
						"localia": "Local",
					}
				],
			},
			cancel_missing=True,
		)
		self.assertGreaterEqual(result["cancelados"], 1)
		estado_b = frappe.db.get_value(
			"Reserva Espacio",
			{"id_externo_fixture": "test-cancel-b"},
			"estado",
		)
		self.assertEqual(estado_b, "Cancelada")
		estado_a = frappe.db.get_value(
			"Reserva Espacio",
			{"id_externo_fixture": "test-cancel-a"},
			"estado",
		)
		self.assertEqual(estado_a, "Confirmada")

	def test_superposicion_con_grilla_no_bloquea_import(self) -> None:
		# 2026-10-20 = martes
		if frappe.db.exists("Espacio", CANCHA_3):
			espacio = frappe.get_doc("Espacio", CANCHA_3)
			espacio.append(
				"horarios",
				{
					"dia_semana": "Martes",
					"hora_desde": "19:00:00",
					"hora_hasta": "21:00:00",
					"tipo_sesion": "Entrenamiento",
					"etiqueta": "Basquet U17",
				},
			)
			espacio.flags.skip_spaces_grid_reserva_check = True
			espacio.save(ignore_permissions=True)
		result = import_fixture_payload(
			{
				"source": ORIGIN_FEBAMBA_GES,
				"partidos": [
					{
						"external_id": "test-super-001",
						"fecha": "2026-10-20",
						"hora": "20:00",
						"categoria": "U17",
						"rival": "Solape Test",
						"localia": "Local",
					}
				],
			}
		)
		self.assertEqual(result["creados"], 1)
		self.assertGreaterEqual(len(result["superposiciones"]), 1)
		name = find_reserva_by_fixture(ORIGIN_FEBAMBA_GES, "test-super-001")
		self.assertEqual(frappe.db.get_value("Reserva Espacio", name, "superposicion_detectada"), 1)
		payload = get_ocupacion_dashboard_payload(fecha="2026-10-20")
		self.assertGreaterEqual(len(payload["superposiciones"]), 1)
		self.assertTrue(any(b.get("superposicion") for b in payload["bloques"]))

	def test_sample_json_fixture(self) -> None:
		path = default_fixture_json_path()
		self.assertTrue(path.exists())
		result = import_febamba_ges_json(path)
		self.assertGreaterEqual(result["creados"] + result["actualizados"], 1)


class TestFixturesDeskApi(MembersTestCase):
	def test_api_requiere_permiso(self) -> None:
		from club_management.spaces.api.fixtures_desk import import_fixtures_json

		make_coordinacion_user("coord.fixtures@example.com")
		if not frappe.db.exists("Espacio", CANCHA_3):
			insert_espacio(CANCHA_3, tipo="Cancha")
		frappe.set_user("coord.fixtures@example.com")
		out = import_fixtures_json(
			{
				"source": ORIGIN_FEBAMBA_GES,
				"partidos": [
					{
						"external_id": "api-test-001",
						"fecha": "2026-11-01",
						"hora": "21:00",
						"categoria": "U17",
						"rival": "API",
						"localia": "Local",
					}
				],
			}
		)
		self.assertEqual(out["creados"], 1)

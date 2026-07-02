"""Tests dashboard Gestión de Actividades (spec gestion_actividades_dashboard.md)."""

from __future__ import annotations

import frappe

from club_management.activities.api.gestion_actividades_workspace import get_dashboard
from club_management.activities.services.gestion_actividades_dashboard import (
	get_actividad_mas_socios_payload,
	get_asistencia_semanal_payload,
	get_crecimiento_actividad_payload,
	get_dashboard_payload,
	get_lista_espera_top_payload,
	get_ocupacion_general_payload,
	get_ocupacion_por_deporte_payload,
	count_inscripciones_activas,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestGestionActividadesDashboardKpis(MembersTestCase):
	_REFERENCE = "2026-06-15"

	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def _actividad_sin_grupos(self, titulo: str, capacidad: int = 0) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": titulo,
				"habilitada": 1,
				"usa_grupos": 0,
				"capacidad": capacidad,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _inscribir(
		self,
		socio_name: str,
		actividad: str,
		*,
		grupo: str | None = None,
		equipo: str | None = None,
		fecha: str = "2026-06-10",
	) -> None:
		doc = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio_name,
				"actividad": actividad,
				"grupo_actividad": grupo,
				"equipo_actividad": equipo,
				"estado": "Activa",
				"fecha_inscripcion": fecha,
			}
		)
		doc.insert(ignore_permissions=True)

	def test_inscripciones_activas_cuenta_filas_no_socios_unicos(self) -> None:
		before = count_inscripciones_activas()
		actividad = self._actividad_sin_grupos("Dash Test Natación")
		socio = insert_socio(dni="76010001", email="dash.nat@example.com", estado="Activo")
		self._inscribir(socio.name, actividad)
		otra = self._actividad_sin_grupos("Dash Test Gimnasio")
		self._inscribir(socio.name, otra)
		self.assertEqual(count_inscripciones_activas(), before + 2)

	def test_ocupacion_general_con_capacidad(self) -> None:
		actividad = self._actividad_sin_grupos("Dash Test Cupos", capacidad=10)
		for idx in range(3):
			socio = insert_socio(dni=f"7601001{idx}", email=f"dash.cup{idx}@example.com", estado="Activo")
			self._inscribir(socio.name, actividad)
		data = get_ocupacion_general_payload(actividad=actividad)
		self.assertEqual(data["inscriptos"], 3)
		self.assertEqual(data["capacidad"], 10)
		self.assertEqual(data["porcentaje"], 30.0)
		self.assertTrue(data["datos_completos"])

	def test_crecimiento_actividad_mes(self) -> None:
		futbol = self._actividad_sin_grupos("Dash Test Fútbol")
		basquet = self._actividad_sin_grupos("Dash Test Básquet")
		s1 = insert_socio(dni="76010020", email="dash.fut1@example.com", estado="Activo")
		s2 = insert_socio(dni="76010021", email="dash.fut2@example.com", estado="Activo")
		s3 = insert_socio(dni="76010022", email="dash.bas@example.com", estado="Activo")
		self._inscribir(s1.name, futbol, fecha="2026-06-05")
		self._inscribir(s2.name, futbol, fecha="2026-06-12")
		self._inscribir(s3.name, basquet, fecha="2026-06-08")
		data = get_crecimiento_actividad_payload(reference_date=self._REFERENCE)
		self.assertEqual(data["actividad"], futbol)
		self.assertEqual(data["altas_mes"], 2)

	def test_actividad_mas_socios_inscriptos(self) -> None:
		futbol = self._actividad_sin_grupos("Dash Test Fútbol Socios")
		basquet = self._actividad_sin_grupos("Dash Test Básquet Socios")
		s1 = insert_socio(dni="76010060", email="dash.fut.s1@example.com", estado="Activo")
		s2 = insert_socio(dni="76010061", email="dash.fut.s2@example.com", estado="Activo")
		s3 = insert_socio(dni="76010062", email="dash.bas.s1@example.com", estado="Activo")
		self._inscribir(s1.name, futbol)
		self._inscribir(s2.name, futbol)
		self._inscribir(s3.name, basquet)
		data = get_actividad_mas_socios_payload()
		self.assertEqual(data["actividad"], futbol)
		self.assertEqual(data["socios"], 2)

	def test_dashboard_kpis_sin_aptos_ni_ocupacion_card(self) -> None:
		payload = get_dashboard_payload(reference_date=self._REFERENCE)
		kpis = payload["kpis"]
		self.assertIn("inscripciones_activas", kpis)
		self.assertIn("crecimiento", kpis)
		self.assertIn("mas_socios", kpis)
		self.assertNotIn("aptos_vencidos", kpis)
		self.assertNotIn("ocupacion", kpis)
		self.assertNotIn("aptos_filters", payload.get("ver_mas", {}))

	def test_ocupacion_por_deporte_segmenta_grupos(self) -> None:
		actividad = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": "Dash Test Básquet Colores",
				"habilitada": 1,
				"usa_grupos": 1,
			}
		).insert(ignore_permissions=True)
		azul = frappe.get_doc(
			{
				"doctype": "Grupo Actividad",
				"actividad": actividad.name,
				"titulo": "Azul",
				"habilitada": 1,
			}
		).insert(ignore_permissions=True)
		amarillo = frappe.get_doc(
			{
				"doctype": "Grupo Actividad",
				"actividad": actividad.name,
				"titulo": "Amarillo",
				"habilitada": 1,
			}
		).insert(ignore_permissions=True)
		s1 = insert_socio(dni="76010040", email="dash.azul@example.com", estado="Activo")
		s2 = insert_socio(dni="76010041", email="dash.amar@example.com", estado="Activo")
		self._inscribir(s1.name, actividad.name, grupo=azul.name)
		self._inscribir(s2.name, actividad.name, grupo=amarillo.name)
		data = get_ocupacion_por_deporte_payload(actividad=actividad.name)
		self.assertTrue(data["disponible"])
		self.assertIn(actividad.name, data["labels"])
		self.assertEqual(len(data["datasets"]), 2)

	def test_lista_espera_top_agrupa(self) -> None:
		actividad = self._actividad_sin_grupos("Dash Test Espera", capacidad=1)
		s1 = insert_socio(dni="76010050", email="dash.es1@example.com", estado="Activo")
		s2 = insert_socio(dni="76010051", email="dash.es2@example.com", estado="Activo")
		for socio, fecha in ((s1, "2026-06-01"), (s2, "2026-06-05")):
			frappe.get_doc(
				{
					"doctype": "Lista Espera Actividad",
					"socio": socio.name,
					"actividad": actividad,
					"fecha_solicitud": fecha,
					"estado": "En espera",
				}
			).insert(ignore_permissions=True)
		data = get_lista_espera_top_payload()
		self.assertTrue(data["disponible"])
		self.assertEqual(len(data["filas"]), 1)
		self.assertEqual(data["filas"][0]["cantidad"], 2)

	def test_asistencia_semanal_promedio(self) -> None:
		actividad = self._actividad_sin_grupos("Dash Test Asistencia")
		frappe.get_doc(
			{
				"doctype": "Asistencia Sesion",
				"fecha": "2026-06-10",
				"actividad": actividad,
				"inscriptos": 10,
				"presentes": 8,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Asistencia Sesion",
				"fecha": "2026-06-12",
				"actividad": actividad,
				"inscriptos": 10,
				"presentes": 6,
			}
		).insert(ignore_permissions=True)
		data = get_asistencia_semanal_payload(reference_date=self._REFERENCE, actividad=actividad)
		self.assertTrue(data["disponible"])
		self.assertEqual(len(data["series"]), 1)
		self.assertGreater(max(data["series"][0]["values"]), 0)


class TestGestionActividadesDashboardApi(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		super().tearDown()

	def test_api_permiso_secretaria(self) -> None:
		user = make_secretaria_user("dash.sec@example.com")
		frappe.set_user(user)
		data = get_dashboard()
		self.assertIn("kpis", data)
		frappe.set_user("Administrator")

	def test_api_denegado_usuario_sin_rol(self) -> None:
		email = "dash.norol@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Sin",
					"last_name": "Rol",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		with self.assertRaises(frappe.PermissionError):
			get_dashboard()
		frappe.set_user("Administrator")

"""Tests del panel de listas del workspace Secretaría."""

from __future__ import annotations

import frappe
from frappe.exceptions import PermissionError

from club_management.members.api.secretaria_workspace import (
	get_cuotas_sociales,
	get_panel_lists,
	save_cuotas_sociales,
)
from club_management.members.services.secretaria_workspace_panel import (
	LIST_LIMIT,
	get_socios_morosos_preview,
	get_solicitudes_pendientes_preview,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import STATE_PENDIENTE


class TestSecretariaWorkspacePanelService(MembersTestCase):
	def test_solicitudes_pendientes_orden_creacion_asc_y_limite(self) -> None:
		for i in range(6):
			insert_solicitud_asociacion(
				dni=f"7099{i:04d}",
				email=f"pend.panel.{i}@example.com",
				nombre=f"Solicitante {i}",
				workflow_state=STATE_PENDIENTE,
			)

		rows = get_solicitudes_pendientes_preview(limit=LIST_LIMIT)
		self.assertEqual(len(rows), LIST_LIMIT)
		creations = [r["creation"] for r in rows]
		self.assertEqual(creations, sorted(creations))

	def test_socios_morosos_orden_saldo_deuda_desc(self) -> None:
		s1 = insert_socio(dni="70881001", email="m1@example.com", estado="Moroso", saldo_deuda=100)
		s2 = insert_socio(dni="70881002", email="m2@example.com", estado="Moroso", saldo_deuda=500)
		s3 = insert_socio(dni="70881003", email="m3@example.com", estado="Moroso", saldo_deuda=250)
		created = {s1.name, s2.name, s3.name}

		rows = get_socios_morosos_preview(limit=LIST_LIMIT)
		deudas = [r["saldo_deuda"] for r in rows if r["name"] in created]
		self.assertEqual(deudas, [500.0, 250.0, 100.0])

	def test_socios_morosos_muestra_identificador_categoria_estado_actividad(self) -> None:
		actividad = "Panel Test Moroso Act"
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"titulo": actividad,
					"habilitada": 1,
					"usa_grupos": 0,
				}
			).insert(ignore_permissions=True)
		socio = insert_socio(
			dni="70882901",
			email="mor.detalle@example.com",
			nombre="Luis",
			apellido="García",
			estado="Moroso",
			categoria="Activo",
			saldo_deuda=1200,
		)
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": actividad,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)
		rows = get_socios_morosos_preview(limit=1)
		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertTrue(row["identificador"].startswith("SOC-"))
		self.assertEqual(row["nombre_apellido"], "Luis García")
		self.assertEqual(row["categoria"], "Activo")
		self.assertEqual(row["estado"], "Moroso")
		self.assertEqual(row["actividad"], actividad)
		self.assertEqual(row["actividad_label"], actividad)

	def test_socios_morosos_actividad_desde_solicitud_si_socio_vacio(self) -> None:
		sol = insert_solicitud_asociacion(
			dni="70882002",
			email="mor.sol@example.com",
			actividad_interes="Fútbol, Tenis",
		)
		frappe.db.set_value("Solicitud Asociacion", sol.name, "workflow_state", "Validada")
		insert_socio(
			dni="70882002",
			email="mor.sol@example.com",
			estado="Moroso",
			solicitud_origen=sol.name,
			saldo_deuda=50,
		)
		rows = get_socios_morosos_preview(limit=5)
		match = [r for r in rows if r["identificador"].startswith("SOC-") and "Fútbol" in r["actividad"]]
		self.assertEqual(len(match), 1)

	def test_get_panel_lists_metricas_sin_cuotas_inline(self) -> None:
		data = get_panel_lists()
		self.assertIn("metricas", data)
		self.assertIn("socios", data["metricas"])
		self.assertIn("recaudacion", data["metricas"])
		self.assertNotIn("cuotas_sociales", data)
		self.assertIn("solicitudes_pendientes", data)
		self.assertIn("morosos", data["metricas"]["socios"])
		ver_mas = data["metricas"]["ver_mas"]
		self.assertEqual(ver_mas["socios_morosos_doctype"], "Socio")
		self.assertIn("solicitudes_doctype", ver_mas)

	def test_save_cuotas_sociales_inline(self) -> None:
		user = make_secretaria_user("sec.cuotas@example.com")
		frappe.set_user(user)
		result = save_cuotas_sociales(
			[
				{"categoria": "Activo", "monto": 15000},
				{"categoria": "Menor", "monto": 12000},
			]
		)
		self.assertEqual(len(result["cuotas"]), 6)
		activo = next(row for row in result["cuotas"] if row["categoria"] == "Activo")
		self.assertEqual(activo["monto"], 15000.0)
		frappe.set_user("Administrator")


class TestSecretariaWorkspacePanelPermissions(MembersTestCase):
	def test_guest_no_puede_consultar_panel(self) -> None:
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			get_panel_lists()
		frappe.set_user("Administrator")

	def test_secretaria_puede_consultar_panel(self) -> None:
		user = make_secretaria_user()
		frappe.set_user(user)
		data = get_panel_lists()
		self.assertIn("metricas", data)
		self.assertIn("socios", data["metricas"])
		self.assertIn("solicitudes_pendientes", data)
		frappe.set_user("Administrator")

	def test_guest_no_puede_guardar_cuotas(self) -> None:
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			save_cuotas_sociales([{"categoria": "Activo", "monto": 1000}])
		frappe.set_user("Administrator")

	def test_secretaria_puede_leer_cuotas(self) -> None:
		user = make_secretaria_user("sec.cuotas.read@example.com")
		frappe.set_user(user)
		data = get_cuotas_sociales()
		self.assertIn("cuotas", data)
		self.assertGreaterEqual(len(data["cuotas"]), 1)
		frappe.set_user("Administrator")

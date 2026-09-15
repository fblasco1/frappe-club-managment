"""Tests dashboard Desk Espacios (spec espacios_desk_dashboard.md)."""

from __future__ import annotations

import frappe
from frappe.utils import today

from club_management.members.setup.siclub_desktop_icon import (
	SICLUB_APP_LABEL,
	SIDEBAR_ESPACIOS,
	ensure_siclub_desktop_icons,
	siclub_child_labels,
)
from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.helpers import insert_espacio, make_coordinacion_user, make_socio_portal_user
from club_management.spaces.setup.espacios_workspace_sidebar import (
	GESTION_ESPACIOS_WORKSPACE_NAME,
	WORKSPACE_SEQUENCE_ID,
	ensure_espacios_desk_dashboard,
)
from club_management.spaces.api.espacios_desk_dashboard import get_espacios_desk_dashboard


class TestEspaciosDeskDashboard(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_workspace_nav_title_and_sequence(self) -> None:
		ensure_espacios_desk_dashboard()
		self.assertTrue(frappe.db.exists("Workspace", GESTION_ESPACIOS_WORKSPACE_NAME))
		ws = frappe.get_doc("Workspace", GESTION_ESPACIOS_WORKSPACE_NAME)
		self.assertEqual(ws.title, GESTION_ESPACIOS_WORKSPACE_NAME)
		self.assertEqual(float(ws.sequence_id), WORKSPACE_SEQUENCE_ID)
		self.assertEqual(int(ws.public or 0), 1)
		roles = {r.role for r in ws.roles}
		self.assertTrue({"Coordinacion", "Secretaria", "Tesoreria", "System Manager"} <= roles)

	def test_page_espacios_exists(self) -> None:
		ensure_espacios_desk_dashboard()
		self.assertTrue(frappe.db.exists("Page", "espacios"))
		page = frappe.get_doc("Page", "espacios")
		self.assertIn("Espacios", page.title)

	def test_coordinacion_home_page_desk_espacios(self) -> None:
		ensure_espacios_desk_dashboard()
		home = frappe.db.get_value("Role", "Coordinacion", "home_page")
		self.assertEqual(home, "/desk/espacios")

	def test_api_pendientes_y_actividades_filtrables(self) -> None:
		espacio_a = insert_espacio(
			"Cancha Desk Dash A",
			alquilable=1,
			horarios=[
				{
					"dia_semana": "Lunes",
					"hora_desde": "10:00:00",
					"hora_hasta": "11:00:00",
					"tipo_sesion": "Entrenamiento",
					"titulo": "Entrenamiento A",
				}
			],
		)
		espacio_b = insert_espacio(
			"Cancha Desk Dash B",
			horarios=[
				{
					"dia_semana": "Lunes",
					"hora_desde": "09:00:00",
					"hora_hasta": "10:00:00",
					"tipo_sesion": "Entrenamiento",
					"titulo": "Entrenamiento B",
				}
			],
		)
		# Forzar día de hoy = Lunes en payload vía fecha fija (ver servicio con fecha)
		fecha = "2026-09-07"  # lunes
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio_a,
				"fecha": fecha,
				"hora_desde": "15:00:00",
				"hora_hasta": "16:00:00",
				"tipo": "Evento club",
				"estado": "Pendiente",
				"motivo": "Solicitud pendiente test",
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio_a,
				"fecha": fecha,
				"hora_desde": "17:00:00",
				"hora_hasta": "18:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "No pendiente",
			}
		).insert(ignore_permissions=True)

		user = make_coordinacion_user("coord.espacios.dash@example.com")
		frappe.set_user(user)
		payload = get_espacios_desk_dashboard(fecha=fecha)
		pendientes = payload["pendientes"]
		self.assertTrue(any(p.get("motivo") == "Solicitud pendiente test" for p in pendientes))
		self.assertFalse(any(p.get("motivo") == "No pendiente" for p in pendientes))

		agenda = payload["actividades_dia"]
		horas = [a["hora_desde"][:5] for a in agenda]
		self.assertEqual(horas, sorted(horas))
		self.assertTrue(any(a["espacio"] == espacio_a for a in agenda))
		self.assertTrue(any(a["espacio"] == espacio_b for a in agenda))

		filtrado = get_espacios_desk_dashboard(fecha=fecha, espacio=espacio_a)
		self.assertTrue(all(a["espacio"] == espacio_a for a in filtrado["actividades_dia"]))

	def test_api_sin_permiso_falla(self) -> None:
		socio = make_socio_portal_user("socio.espacios.dash@example.com")
		frappe.set_user(socio)
		with self.assertRaises(frappe.PermissionError):
			get_espacios_desk_dashboard(fecha=today())


class TestSiclubEspaciosChild(MembersTestCase):
	def test_siclub_incluye_espacios(self) -> None:
		ensure_siclub_desktop_icons()
		labels = siclub_child_labels()
		self.assertIn(SIDEBAR_ESPACIOS, labels)
		self.assertEqual(
			labels,
			["Socios", "Actividades", "Espacios", "Configuración de Sistema"],
		)
		child = frappe.get_all(
			"Desktop Icon",
			filters={"label": SIDEBAR_ESPACIOS, "parent_icon": SICLUB_APP_LABEL, "icon_type": "Link"},
			fields=["link_type", "link_to", "hidden"],
			limit=1,
		)
		self.assertTrue(child)
		self.assertEqual(child[0].link_type, "Workspace Sidebar")
		self.assertEqual(child[0].link_to, SIDEBAR_ESPACIOS)
		self.assertEqual(int(child[0].hidden or 0), 0)
		self.assertTrue(frappe.db.exists("Workspace Sidebar", SIDEBAR_ESPACIOS))


class TestEspaciosDesktopLanding(MembersTestCase):
	def test_coordinacion_ve_solo_icono_espacios(self) -> None:
		from club_management.boot import extend_bootinfo
		from club_management.spaces.setup.espacios_desktop_landing import (
			user_sees_espacios_desktop_landing,
		)

		user = make_coordinacion_user("coord.landing.espacios@example.com")
		self.assertTrue(user_sees_espacios_desktop_landing(user))

		frappe.set_user(user)
		bootinfo: dict = {
			"user": {"name": user, "roles": ["Coordinacion"]},
			"desktop_icons": [
				{"label": "Framework", "icon_type": "App"},
				{"label": "SICLUB", "icon_type": "App"},
				{"label": "Calidad", "icon_type": "App"},
			],
			"apps_data": {},
			"workspace_sidebar_item": {},
		}
		extend_bootinfo(bootinfo)
		self.assertTrue(bootinfo.get("club_management_espacios_desktop_landing"))
		labels = [i["label"] for i in bootinfo["desktop_icons"]]
		self.assertEqual(labels, ["Espacios"])
		self.assertIn("espacios", bootinfo["workspace_sidebar_item"])
		self.assertTrue(bootinfo["workspace_sidebar_item"]["espacios"]["items"])
		frappe.set_user("Administrator")

	def test_administrator_no_ve_landing_espacios(self) -> None:
		from club_management.spaces.setup.espacios_desktop_landing import (
			user_sees_espacios_desktop_landing,
		)

		self.assertFalse(user_sees_espacios_desktop_landing("Administrator"))

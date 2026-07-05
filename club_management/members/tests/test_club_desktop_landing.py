"""Tests landing Desk Secretaría (Socios, Actividades, Configuración)."""

from __future__ import annotations

from club_management.boot import extend_bootinfo
from club_management.members.setup.club_desktop_landing import (
	CLUB_DESK_LANDING_ICONS,
	apply_club_desktop_landing_sidebar_aliases,
	apply_club_desktop_landing_to_boot,
	club_desktop_landing_icons,
	user_sees_club_desktop_landing,
)
from club_management.members.setup.inicio_workspace import GESTION_ACTIVIDADES_WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME as SECRETARIA_WORKSPACE_NAME
from club_management.members.test_helpers import MembersTestCase, make_secretaria_user


class TestClubDesktopLanding(MembersTestCase):
	def test_secretaria_ve_landing_del_club(self) -> None:
		user = make_secretaria_user("sec.landing@example.com")
		self.assertTrue(user_sees_club_desktop_landing(user))

	def test_administrator_no_ve_landing_filtrado(self) -> None:
		self.assertFalse(user_sees_club_desktop_landing("Administrator"))

	def test_landing_tiene_tres_iconos(self) -> None:
		icons = club_desktop_landing_icons()
		self.assertEqual(len(icons), 3)
		labels = [icon["label"] for icon in icons]
		self.assertEqual(
			labels,
			["Socios", "Actividades", "Configuración de Sistema"],
		)

	def test_apply_boot_reemplaza_desktop_icons(self) -> None:
		import frappe

		user = make_secretaria_user("sec.boot.landing@example.com")
		bootinfo = {
			"user": {"name": user, "roles": ["Secretaria"]},
			"desktop_icons": [{"label": "Framework", "icon_type": "App"}],
			"apps_data": {},
		}
		frappe.set_user(user)
		apply_club_desktop_landing_to_boot(bootinfo)
		self.assertTrue(bootinfo.get("club_management_desktop_landing"))
		self.assertEqual(len(bootinfo["desktop_icons"]), 3)
		self.assertEqual(bootinfo["desktop_icons"][0]["label"], "Socios")
		frappe.set_user("Administrator")

	def test_landing_iconos_usan_workspace_sidebar_interno(self) -> None:
		for icon in CLUB_DESK_LANDING_ICONS:
			self.assertEqual(icon["link_type"], "Workspace Sidebar")
			self.assertNotIn("link", icon)

	def test_landing_sidebar_aliases_para_iconos_desktop(self) -> None:
		import frappe

		user = make_secretaria_user("sec.landing.sidebar@example.com")
		bootinfo: dict = {
			"user": {"name": user, "roles": ["Secretaria"]},
			"desktop_icons": [],
			"apps_data": {},
			"workspace_sidebar_item": {},
		}
		frappe.set_user(user)
		extend_bootinfo(bootinfo)
		sidebars = bootinfo["workspace_sidebar_item"]
		self.assertIn("socios", sidebars)
		self.assertIn("actividades", sidebars)
		self.assertIn("configuración de sistema", sidebars)
		self.assertEqual(
			sidebars["socios"]["items"][0]["link_to"],
			SECRETARIA_WORKSPACE_NAME,
		)
		self.assertEqual(
			sidebars["actividades"]["items"][0]["link_to"],
			GESTION_ACTIVIDADES_WORKSPACE_NAME,
		)
		self.assertEqual(
			sidebars["configuración de sistema"]["items"][0]["link_to"],
			"Club Settings",
		)
		frappe.set_user("Administrator")

	def test_sidebar_aliases_sin_landing_no_op(self) -> None:
		bootinfo = {"user": {"name": "Administrator"}, "workspace_sidebar_item": {}}
		apply_club_desktop_landing_sidebar_aliases(bootinfo)
		self.assertNotIn("socios", bootinfo["workspace_sidebar_item"])

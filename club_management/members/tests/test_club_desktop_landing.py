"""Tests landing Desk Secretaría (Socios, Actividades, Configuración)."""

from __future__ import annotations

from club_management.members.setup.club_desktop_landing import (
	CLUB_DESK_LANDING_ICONS,
	apply_club_desktop_landing_to_boot,
	club_desktop_landing_icons,
	user_sees_club_desktop_landing,
)
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

	def test_rutas_landing_apuntan_a_workspaces_y_settings(self) -> None:
		by_label = {icon["label"]: icon for icon in CLUB_DESK_LANDING_ICONS}
		self.assertIn("secretaría", by_label["Socios"]["link"])
		self.assertIn("gestión-de-actividades", by_label["Actividades"]["link"])
		self.assertIn("club-settings", by_label["Configuración de Sistema"]["link"])

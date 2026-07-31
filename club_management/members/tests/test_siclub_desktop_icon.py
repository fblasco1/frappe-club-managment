"""Tests ícono Desk App SICLUB (spec siclub_desktop_app.md)."""

from __future__ import annotations

import frappe

from club_management.members.setup.siclub_desktop_icon import (
	SICLUB_APP_LABEL,
	SIDEBAR_ACTIVIDADES,
	SIDEBAR_CONFIG,
	SIDEBAR_SOCIOS,
	ensure_siclub_desktop_icons,
	siclub_child_labels,
)
from club_management.members.test_helpers import MembersTestCase


class TestSiclubDesktopIcon(MembersTestCase):
	def test_ensure_crea_app_siclub_y_hijos(self) -> None:
		ensure_siclub_desktop_icons()

		app = frappe.get_all(
			"Desktop Icon",
			filters={"label": SICLUB_APP_LABEL, "icon_type": "App"},
			fields=["name", "hidden", "app", "link", "link_type"],
			limit=1,
		)
		self.assertTrue(app)
		self.assertEqual(app[0].app, "club_management")
		self.assertEqual(int(app[0].hidden or 0), 0)
		self.assertEqual(app[0].link_type, "External")
		self.assertTrue(str(app[0].link or "").startswith("/desk/"))

		children = frappe.get_all(
			"Desktop Icon",
			filters={"parent_icon": SICLUB_APP_LABEL, "icon_type": "Link"},
			fields=["label", "link_type", "link_to", "hidden"],
			order_by="idx asc",
		)
		labels = [row.label for row in children]
		self.assertEqual(labels, siclub_child_labels())
		for row in children:
			self.assertEqual(row.link_type, "Workspace Sidebar")
			self.assertEqual(int(row.hidden or 0), 0)

	def test_ensure_crea_sidebars_landing(self) -> None:
		ensure_siclub_desktop_icons()
		for name in (SIDEBAR_SOCIOS, SIDEBAR_ACTIVIDADES, SIDEBAR_CONFIG):
			self.assertTrue(frappe.db.exists("Workspace Sidebar", name), name)
			items = frappe.get_all(
				"Workspace Sidebar Item",
				filters={"parent": name},
				pluck="label",
			)
			self.assertTrue(items, f"sidebar {name} sin ítems")

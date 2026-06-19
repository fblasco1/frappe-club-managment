"""Tests enlaces jerárquicos Actividad > Grupo Actividad > Equipo Actividad."""

from __future__ import annotations

import json
import os

import frappe

from club_management.members.test_helpers import MembersTestCase


def _gestion_actividades_json_path() -> str:
	return os.path.join(
		frappe.get_app_path("club_management"),
		"activities",
		"workspace",
		"gestion_actividades",
		"gestion_actividades.json",
	)


class TestActivitiesJerarquiaAdminLinks(MembersTestCase):
	def test_actividad_dashboard_links_to_grupos(self) -> None:
		meta = frappe.get_meta("Actividad")
		link = next(row for row in meta.links if row.link_doctype == "Grupo Actividad")
		self.assertEqual(link.link_fieldname, "actividad")
		self.assertEqual(link.group, "Grupos / tiras")

	def test_grupo_dashboard_links_to_equipos(self) -> None:
		meta = frappe.get_meta("Grupo Actividad")
		link = next(row for row in meta.links if row.link_doctype == "Equipo Actividad")
		self.assertEqual(link.link_fieldname, "grupo_actividad")
		self.assertEqual(link.group, "Equipos / categorías")

	def test_gestion_actividades_workspace_fixture_has_hierarchy_links(self) -> None:
		with open(_gestion_actividades_json_path(), encoding="utf-8") as handle:
			data = json.load(handle)
		links = [row for row in data.get("links") or [] if row.get("type") == "Link"]
		labels = {row["label"]: row["link_to"] for row in links}
		self.assertEqual(labels.get("Actividades"), "Actividad")
		self.assertEqual(labels.get("Grupos / tiras"), "Grupo Actividad")
		self.assertEqual(labels.get("Equipos / categorías"), "Equipo Actividad")
		card_breaks = [row for row in data.get("links") or [] if row.get("type") == "Card Break"]
		self.assertTrue(any(row.get("label") == "Estructura jerárquica" for row in card_breaks))

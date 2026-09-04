"""Tests navegación Desk y workspaces del club."""

from __future__ import annotations

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from club_management.members.setup.inicio_workspace import (
	CLUB_DESK_NAV_TABS,
	CLUB_DESK_REPORTS,
	GESTION_ACTIVIDADES_WORKSPACE_NAME,
	INICIO_WORKSPACE_NAME,
	SECRETARIA_WORKSPACE_NAME,
	set_secretaria_default_workspace,
)
from club_management.members.test_helpers import ensure_role_secretaria_exists


def _inicio_json_path() -> str:
	return os.path.join(
		frappe.get_app_path("club_management"),
		"members",
		"workspace",
		"inicio",
		"inicio.json",
	)


def _gestion_actividades_json_path() -> str:
	return os.path.join(
		frappe.get_app_path("club_management"),
		"activities",
		"workspace",
		"gestion_actividades",
		"gestion_actividades.json",
	)


class TestInicioWorkspace(FrappeTestCase):
	def test_inicio_fixture_esta_oculto_y_vacio(self) -> None:
		with open(_inicio_json_path(), encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(data.get("name"), INICIO_WORKSPACE_NAME)
		self.assertEqual(data.get("is_hidden"), 1)
		self.assertEqual(json.loads(data.get("content") or "[]"), [])
		self.assertEqual(data.get("shortcuts") or [], [])

	def test_gestion_actividades_fixture_sin_widgets_estaticos(self) -> None:
		with open(_gestion_actividades_json_path(), encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(data.get("name"), GESTION_ACTIVIDADES_WORKSPACE_NAME)
		self.assertEqual(json.loads(data.get("content") or "[]"), [])
		self.assertEqual(data.get("shortcuts") or [], [])

	def test_secretaria_fixture_sin_parent_inicio(self) -> None:
		path = os.path.join(
			frappe.get_app_path("club_management"),
			"members",
			"workspace",
			"secretaria",
			"secretaria.json",
		)
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(data.get("parent_page"), "")

	def test_navegacion_club_tiene_dos_secciones(self) -> None:
		self.assertEqual(len(CLUB_DESK_NAV_TABS), 2)
		labels = [label for label, _workspace in CLUB_DESK_NAV_TABS]
		self.assertEqual(labels, ["Gestión de Socios", "Gestión de Actividades"])
		workspaces = {workspace for _label, workspace in CLUB_DESK_NAV_TABS}
		self.assertEqual(
			workspaces,
			{SECRETARIA_WORKSPACE_NAME, GESTION_ACTIVIDADES_WORKSPACE_NAME},
		)

	def test_informes_club_no_estan_en_pestanas_superiores(self) -> None:
		self.assertEqual(len(CLUB_DESK_REPORTS), 3)
		self.assertEqual(
			list(CLUB_DESK_REPORTS),
			["Cobranza por fechas", "Pagos por equipo", "Deuda por actividad"],
		)
		self.assertNotIn("Pagos del dia", CLUB_DESK_REPORTS)
		self.assertNotIn("Recaudacion por concepto", CLUB_DESK_REPORTS)
		self.assertNotIn("Deuda por equipo", CLUB_DESK_REPORTS)
		nav_workspaces = {workspace for _label, workspace in CLUB_DESK_NAV_TABS}
		for report_name in CLUB_DESK_REPORTS:
			self.assertNotIn(report_name, nav_workspaces)


	def test_default_workspace_secretaria_es_secretaria(self) -> None:
		ensure_role_secretaria_exists()
		email = "secretaria.inicio@example.com"
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=1)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Sec",
				"enabled": 1,
				"send_welcome_email": 0,
				"roles": [{"role": "Secretaria"}],
			}
		).insert(ignore_permissions=True)
		if not frappe.db.exists("Workspace", SECRETARIA_WORKSPACE_NAME):
			self.skipTest("Ejecutar bench migrate para sincronizar workspaces")
		set_secretaria_default_workspace(only_if_empty=False)
		self.assertEqual(
			frappe.db.get_value("User", email, "default_workspace"),
			SECRETARIA_WORKSPACE_NAME,
		)
		frappe.delete_doc("User", email, force=1)

"""Tests inyección sidebar Secretaría en bootinfo."""

from __future__ import annotations

from club_management.members.setup.secretaria_sidebar_boot import (
	apply_secretaria_sidebar_to_boot,
	build_secretaria_sidebar_boot_items,
)
from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME
from club_management.members.test_helpers import MembersTestCase, make_secretaria_user


class TestSecretariaSidebarBoot(MembersTestCase):
	def test_build_sidebar_boot_items_incluye_cuotas(self) -> None:
		labels = [row["label"] for row in build_secretaria_sidebar_boot_items()]
		self.assertIn("Valores de Cuota Social", labels)
		self.assertIn("Socio", labels)

	def test_build_sidebar_boot_items_incluye_metadata_reportes(self) -> None:
		items = {row["label"]: row for row in build_secretaria_sidebar_boot_items()}
		cobranza = items["Cobranza por fechas"].get("report") or {}
		self.assertEqual(cobranza.get("report_type"), "Script Report")
		self.assertEqual(cobranza.get("ref_doctype"), "Payment Entry")
		pagos = items["Pagos por equipo"].get("report") or {}
		self.assertEqual(pagos.get("report_type"), "Script Report")
		self.assertEqual(pagos.get("ref_doctype"), "Inscripcion Actividad")
		club_report = items["Deuda por actividad"].get("report") or {}
		self.assertEqual(club_report.get("ref_doctype"), "Actividad")
		self.assertNotIn("Deuda por equipo", items)
		self.assertNotIn("Pagos del dia", items)
		self.assertNotIn("Recaudacion por concepto", items)


	def test_apply_boot_inyecta_sidebar_para_secretaria(self) -> None:
		user = make_secretaria_user("sec.sidebar.boot@example.com")
		bootinfo: dict = {"user": {"name": user, "roles": [{"role": "Secretaria"}]}}
		apply_secretaria_sidebar_to_boot(bootinfo)
		key = WORKSPACE_NAME.lower()
		self.assertIn(key, bootinfo.get("workspace_sidebar_item", {}))
		items = bootinfo["workspace_sidebar_item"][key]["items"]
		labels = [row["label"] for row in items]
		self.assertIn("Secretaría", labels)
		self.assertIn("Valores de Cuota Social", labels)

	def test_apply_boot_no_inyecta_para_guest(self) -> None:
		bootinfo: dict = {"user": {"name": "Guest", "roles": []}}
		apply_secretaria_sidebar_to_boot(bootinfo)
		self.assertNotIn(WORKSPACE_NAME.lower(), bootinfo.get("workspace_sidebar_item", {}))

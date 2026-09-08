"""Tests verificación y purga básquet legacy."""

from __future__ import annotations

import frappe

from club_management.activities.setup.verify_and_purge_basquet_legacy import (
	CONFIRM_PURGE_TOKEN,
	purge_basquet_legacy_disabled,
	run,
	verify_basquet_legacy_cleanup,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio
from club_management.setup.basquet_cost_center import BASQUET_COST_CENTER_PARENT
from club_management.setup.consolidate_basquet_cost_centers import ensure_basquet_unified_cost_center
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestVerifyAndPurgeBasquetLegacy(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		if not frappe.db.exists("Cost Center", BASQUET_COST_CENTER_PARENT):
			self.skipTest("Falta CC padre Deportes - ICDPE")
		ensure_basquet_unified_cost_center()

	def _ensure_legacy_actividad(self, titulo: str) -> str:
		if frappe.db.exists("Actividad", titulo):
			frappe.db.set_value("Actividad", titulo, {"habilitada": 0, "usa_grupos": 1}, update_modified=False)
			return titulo
		doc = frappe.get_doc(
			{
				"doctype": "Actividad",
				"name": titulo,
				"titulo": titulo,
				"habilitada": 0,
				"usa_grupos": 1,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def test_verify_falla_con_inscripcion_legacy(self) -> None:
		legacy = self._ensure_legacy_actividad("Basquet Masculino")
		socio = insert_socio(dni="88001001", email="legacy-ins@example.com", estado="Activo")
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": legacy,
				"estado": "Baja",
			}
		).insert(ignore_permissions=True)

		report = verify_basquet_legacy_cleanup()
		self.assertFalse(report.ok)
		self.assertTrue(report.inscripciones_legacy)

	def test_purge_elimina_actividad_legacy_deshabilitada(self) -> None:
		legacy = self._ensure_legacy_actividad("Basquet Femenino")
		self.assertTrue(frappe.db.exists("Actividad", legacy))

		report = verify_basquet_legacy_cleanup()
		if not report.ok:
			self.skipTest(f"Sitio no listo para purga: {report.errores}")

		stats = purge_basquet_legacy_disabled()
		self.assertIn(legacy, stats.actividades)
		self.assertFalse(frappe.db.exists("Actividad", legacy))

	def test_run_exige_confirm_para_purga(self) -> None:
		report = verify_basquet_legacy_cleanup()
		if not report.ok:
			self.skipTest("Sitio con referencias legacy; no se prueba purga real")

		with self.assertRaises(frappe.ValidationError):
			run(dry_run=False, purge=True, confirm="MAL")

		run(dry_run=False, purge=True, confirm=CONFIRM_PURGE_TOKEN)

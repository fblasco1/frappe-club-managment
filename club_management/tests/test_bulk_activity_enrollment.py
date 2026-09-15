"""Tests de vinculación masiva a actividades.

Spec: `club_management/specs/vinculacion_masiva_actividades.md`
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import frappe

from club_management.activities.services.inscripcion_socio import INSCRIPCION_DOCTYPE
from club_management.members.test_helpers import MembersTestCase, insert_socio
from club_management.scripts.bulk_activity_enrollment import run as run_bulk_enroll


def _write_csv(header: str, *lines: str) -> str:
	handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
	handle.write(header + "\n")
	for line in lines:
		handle.write(line + "\n")
	handle.close()
	return handle.name


class TestBulkActivityEnrollment(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self.actividad = "Tenis Bulk Test"
		if not frappe.db.exists("Actividad", self.actividad):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": self.actividad, "habilitada": 1, "usa_grupos": 0}
			).insert(ignore_permissions=True)

	def test_dry_run_no_crea_inscripcion(self) -> None:
		socio = insert_socio(dni="88994001", email="bulk.enr.dry@example.com", estado="Activo")
		path = _write_csv(
			"nro_socio,actividad,grupo_actividad,equipo_actividad,fecha_desde",
			f"{socio.name},{self.actividad},,,2026-08-01",
		)
		try:
			result = run_bulk_enroll(csv_path=path, dry_run=True)
		finally:
			Path(path).unlink(missing_ok=True)
		self.assertEqual(result["simuladas"], 1)
		self.assertEqual(result["altas"], 0)
		self.assertFalse(
			frappe.db.exists(
				INSCRIPCION_DOCTYPE,
				{"socio": socio.name, "actividad": self.actividad, "estado": "Activa"},
			)
		)

	def test_socio_no_activo(self) -> None:
		from club_management.members.services.socio_transitions import cambiar_estado

		socio = insert_socio(dni="88994002", email="bulk.enr.baja@example.com", estado="Activo")
		cambiar_estado(socio.name, "Baja", motivo="Test bulk enroll")
		path = _write_csv(
			"nro_socio,actividad,grupo_actividad,equipo_actividad,fecha_desde",
			f"{socio.name},{self.actividad},,,2026-08-01",
		)
		try:
			result = run_bulk_enroll(csv_path=path, dry_run=True)
		finally:
			Path(path).unlink(missing_ok=True)
		self.assertEqual(result["errores"][0]["codigo"], "socio_no_activo")

	def test_actividad_inexistente(self) -> None:
		socio = insert_socio(dni="88994003", email="bulk.enr.act@example.com", estado="Activo")
		path = _write_csv(
			"nro_socio,actividad,grupo_actividad,equipo_actividad,fecha_desde",
			f"{socio.name},NoExisteXYZ,,,2026-08-01",
		)
		try:
			result = run_bulk_enroll(csv_path=path, dry_run=True)
		finally:
			Path(path).unlink(missing_ok=True)
		self.assertEqual(result["errores"][0]["codigo"], "actividad_no_encontrada")

	def test_apply_crea_y_no_duplica(self) -> None:
		socio = insert_socio(dni="88994004", email="bulk.enr.apply@example.com", estado="Activo")
		path = _write_csv(
			"nro_socio,actividad,grupo_actividad,equipo_actividad,fecha_desde",
			f"{socio.name},{self.actividad},,,2026-08-12",
		)
		try:
			created = run_bulk_enroll(csv_path=path, dry_run=False)
			again = run_bulk_enroll(csv_path=path, dry_run=False)
		finally:
			Path(path).unlink(missing_ok=True)

		self.assertEqual(created["altas"], 1)
		self.assertEqual(again["ya_inscrito"], 1)
		ins = frappe.get_all(
			INSCRIPCION_DOCTYPE,
			filters={"socio": socio.name, "actividad": self.actividad, "estado": "Activa"},
			fields=["name", "fecha_inscripcion"],
		)
		self.assertEqual(len(ins), 1)
		self.assertEqual(str(ins[0].fecha_inscripcion), "2026-08-12")

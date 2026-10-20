"""Tests informe Bajas de socios (spec informe_bajas_socios.md)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.utils import getdate, today

from club_management.members.services.informe_bajas_socios import (
	get_bajas_socios,
	get_report_columns,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)

PKG = Path(__file__).resolve().parents[2]


class TestInformeBajasSocios(MembersTestCase):
	def _dar_baja_en(self, socio_name: str, fecha: str) -> None:
		cambiar_estado(socio_name, "Baja", motivo="Test informe bajas", fecha_baja=fecha)
		frappe.db.set_value(
			"Socio",
			socio_name,
			"ultimo_cambio_estado_en",
			f"{fecha} 10:00:00",
			update_modified=False,
		)

	def _socio(self, dni: str, **kwargs):
		return insert_socio(
			dni=dni,
			email=f"bajas.{dni}@example.com",
			estado="Activo",
			**kwargs,
		)

	def _actividad(self, titulo: str) -> str:
		if frappe.db.exists("Actividad", titulo):
			return titulo
		return (
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": titulo, "habilitada": 1, "usa_grupos": 0}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _inscribir(self, socio: str, actividad: str) -> None:
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio,
				"actividad": actividad,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)

	def _run(self, **filters):
		return get_bajas_socios(filters)

	def test_columnas_incluyen_identidad_fecha_actividad_y_deuda(self) -> None:
		fieldnames = [col["fieldname"] for col in get_report_columns()]
		self.assertEqual(
			fieldnames,
			[
				"nro_socio",
				"apellido",
				"nombre",
				"fecha_baja",
				"actividades",
				"tiene_deuda_pendiente",
				"saldo_deuda",
			],
		)

	def test_rango_incluye_solo_bajas_del_periodo(self) -> None:
		marzo = self._socio("88110001", nombre="Ana", apellido="García")
		mayo = self._socio("88110002", nombre="Luis", apellido="Pérez")
		activo = self._socio("88110003", nombre="Marta", apellido="López")
		self._dar_baja_en(marzo.name, "2026-03-15")
		self._dar_baja_en(mayo.name, "2026-05-01")

		rows = self._run(fecha_desde="2026-03-01", fecha_hasta="2026-03-31")
		nombres = {row["nro_socio"] for row in rows}
		self.assertIn(marzo.name, nombres)
		self.assertNotIn(mayo.name, nombres)
		self.assertNotIn(activo.name, nombres)

		fila = next(row for row in rows if row["nro_socio"] == marzo.name)
		self.assertEqual(fila["apellido"], "García")
		self.assertEqual(fila["nombre"], "Ana")
		self.assertEqual(getdate(fila["fecha_baja"]), getdate("2026-03-15"))

	def test_rango_usa_fecha_baja_de_negocio_no_la_de_carga(self) -> None:
		socio = self._socio("88110004", nombre="Rita", apellido="Molina")
		cambiar_estado(socio.name, "Baja", motivo="Migración", fecha_baja="2024-08-20")

		en_agosto = self._run(fecha_desde="2024-08-01", fecha_hasta="2024-08-31")
		self.assertIn(socio.name, {row["nro_socio"] for row in en_agosto})
		hoy = today()
		en_hoy = self._run(fecha_desde=hoy, fecha_hasta=hoy)
		self.assertNotIn(socio.name, {row["nro_socio"] for row in en_hoy})

	def test_filtro_actividad_usa_inscripciones_historicas(self) -> None:
		basquet = self._actividad("Bajas Test Basquet")
		patin = self._actividad("Bajas Test Patin")
		con_basquet = self._socio("88110011", nombre="Eva", apellido="Ruiz")
		solo_patin = self._socio("88110012", nombre="Tomi", apellido="Díaz")
		self._inscribir(con_basquet.name, basquet)
		self._inscribir(solo_patin.name, patin)
		self._dar_baja_en(con_basquet.name, "2026-04-10")
		self._dar_baja_en(solo_patin.name, "2026-04-12")

		rows = self._run(
			fecha_desde="2026-04-01",
			fecha_hasta="2026-04-30",
			actividad=basquet,
		)
		nombres = {row["nro_socio"] for row in rows}
		self.assertEqual(nombres, {con_basquet.name})
		fila = rows[0]
		self.assertIn(basquet, fila["actividades"])
		self.assertNotIn(patin, fila["actividades"])

	def test_deuda_pendiente_si_no_segun_saldo(self) -> None:
		con_deuda = self._socio("88110021", nombre="Nora", apellido="Sosa")
		sin_deuda = self._socio("88110022", nombre="Pablo", apellido="Nieto")
		self._dar_baja_en(con_deuda.name, "2026-06-02")
		self._dar_baja_en(sin_deuda.name, "2026-06-03")
		frappe.db.set_value("Socio", con_deuda.name, "saldo_deuda", 15000, update_modified=False)
		frappe.db.set_value("Socio", sin_deuda.name, "saldo_deuda", 0, update_modified=False)

		with patch(
			"club_management.members.services.informe_bajas_socios.erpnext_cobranza_disponible",
			return_value=False,
		):
			rows = {
				row["nro_socio"]: row
				for row in self._run(fecha_desde="2026-06-01", fecha_hasta="2026-06-30")
			}
			self.assertEqual(rows[con_deuda.name]["tiene_deuda_pendiente"], "Sí")
			self.assertEqual(rows[con_deuda.name]["saldo_deuda"], 15000)
			self.assertEqual(rows[sin_deuda.name]["tiene_deuda_pendiente"], "No")
			self.assertEqual(rows[sin_deuda.name]["saldo_deuda"], 0)

			solo_deuda = self._run(
				fecha_desde="2026-06-01",
				fecha_hasta="2026-06-30",
				tiene_deuda="Con deuda",
			)
		self.assertEqual({row["nro_socio"] for row in solo_deuda}, {con_deuda.name})

	def test_rango_invalido_lanza_validation_error(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			self._run(fecha_desde="2026-04-30", fecha_hasta="2026-04-01")
		with self.assertRaises(frappe.ValidationError):
			self._run(fecha_hasta="2026-04-01")

	def test_usuario_sin_rol_recibe_permission_error(self) -> None:
		ensure_role_socio_exists()
		email = "socio.informe.bajas@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				self._run(fecha_desde=today(), fecha_hasta=today())
		finally:
			frappe.set_user("Administrator")

	def test_artefactos_report_y_menu(self) -> None:
		from club_management.activities.setup.actividades_workspace_sidebar import (
			SIDEBAR_ITEMS as ACTIVIDADES_ITEMS,
		)
		from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS
		from club_management.members.setup.secretaria_workspace_sidebar import SIDEBAR_ITEMS

		folder = PKG / "members" / "report" / "bajas_de_socios"
		meta = json.loads((folder / "bajas_de_socios.json").read_text(encoding="utf-8"))
		self.assertEqual(meta["name"], "Bajas de socios")
		self.assertEqual(meta["ref_doctype"], "Socio")
		self.assertEqual({row["role"] for row in meta["roles"]}, {"Secretaria", "System Manager"})
		js = (folder / "bajas_de_socios.js").read_text(encoding="utf-8")
		for fieldname in ("fecha_desde", "fecha_hasta", "actividad", "tiene_deuda"):
			self.assertIn(f'fieldname: "{fieldname}"', js)

		self.assertIn("Bajas de socios", CLUB_DESK_REPORTS)
		for items in (SIDEBAR_ITEMS, ACTIVIDADES_ITEMS):
			self.assertIn("Bajas de socios", {row.get("link_to") for row in items})
		for js_name in ("secretaria_sidebar_boot.js", "actividades_sidebar_boot.js"):
			boot_js = (PKG / "public" / "js" / js_name).read_text(encoding="utf-8")
			self.assertIn('link_to: "Bajas de socios"', boot_js)

"""Tests gestión de inscripciones desde formulario Socio (Desk Secretaría)."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.activities.services.inscripcion_socio import (
	baja_inscripcion_desk,
	inscribir_actividades_desk,
	inscribir_socio_selecciones,
	list_inscripciones_socio_desk,
)
from club_management.members.services.socio_operaciones_secretaria import activar_socio_manual, dar_baja_socio
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestInscripcionGestionDesk(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = "secretaria_gestion_insc@example.com"
		if not frappe.db.exists("User", self._secretaria):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self._secretaria,
					"first_name": "Secretaria",
					"send_welcome_email": 0,
					"roles": [{"role": "Secretaria"}],
				}
			).insert(ignore_permissions=True)

	def _ensure_actividad(self, titulo: str) -> str:
		if frappe.db.exists("Actividad", titulo):
			return titulo
		doc = frappe.get_doc(
			{
				"doctype": "Actividad",
				"name": titulo,
				"titulo": titulo,
				"habilitada": 1,
				"usa_grupos": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _ensure_zumba(self) -> str:
		return self._ensure_actividad("Zumba")

	def _inscribir(self, socio_name: str, actividad: str) -> str:
		inscribir_socio_selecciones(socio_name, [{"actividad": actividad}], activar=False)
		return frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio_name, "actividad": actividad, "estado": "Activa"},
			"name",
		)

	def _inscribir_zumba(self, socio_name: str) -> str:
		return self._inscribir(socio_name, self._ensure_zumba())

	def test_list_inscripciones_activas_por_defecto(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		ins_name = self._inscribir_zumba(socio.name)
		frappe.db.set_value("Inscripcion Actividad", ins_name, "estado", "Baja")

		frappe.set_user(self._secretaria)
		try:
			rows = list_inscripciones_socio_desk(socio.name)
			rows_con_bajas = list_inscripciones_socio_desk(socio.name, incluir_bajas=True)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(rows, [])
		self.assertEqual(len(rows_con_bajas), 1)
		self.assertEqual(rows_con_bajas[0]["name"], ins_name)
		self.assertEqual(rows_con_bajas[0]["estado"], "Baja")

	def test_get_grupos_y_equipos_desk_por_actividad(self) -> None:
		from club_management.members.api.socio_operaciones_desk import (
			get_equipos_grupo_desk,
			get_grupos_actividad_desk,
		)

		actividad = "Basquet Inscripcion Test"
		grupo = f"{actividad} / Tira Test"
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"name": actividad,
					"titulo": actividad,
					"habilitada": 1,
					"usa_grupos": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Grupo Actividad", grupo):
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": grupo,
					"actividad": actividad,
					"titulo": "Tira Test",
					"habilitada": 1,
					"orden": 10,
				}
			).insert(ignore_permissions=True)
		equipo = f"{grupo} / U13 Test"
		if not frappe.db.exists("Equipo Actividad", equipo):
			frappe.get_doc(
				{
					"doctype": "Equipo Actividad",
					"name": equipo,
					"grupo_actividad": grupo,
					"titulo": "U13 Test",
					"habilitada": 1,
					"orden": 10,
				}
			).insert(ignore_permissions=True)

		frappe.set_user(self._secretaria)
		try:
			grupos = get_grupos_actividad_desk(actividad)
			self.assertTrue(any(row["value"] == grupo for row in grupos))
			equipos = get_equipos_grupo_desk(grupo)
			self.assertTrue(any(row["value"] == equipo for row in equipos))
		finally:
			frappe.set_user("Administrator")

	def test_list_inscripciones_incluye_arancel_y_monto(self) -> None:
		zumba = self._ensure_zumba()
		item_code = "ICDPE-ARANCEL-ZUMBA-TEST"
		if not frappe.db.exists("Item", item_code):
			if not frappe.db.exists("UOM", "Nos"):
				frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": "Arancel Zumba Test",
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 8500,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Actividad", zumba, "item", item_code)

		socio = insert_socio(dni="72001001", email="list.insc@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test")
		ins_name = self._inscribir_zumba(socio.name)

		frappe.set_user(self._secretaria)
		try:
			rows = list_inscripciones_socio_desk(socio.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row["name"], ins_name)
		self.assertEqual(row["actividad"], zumba)
		self.assertEqual(row["item_arancel"], item_code)
		self.assertEqual(row["monto"], 8500.0)
		self.assertTrue(row["fecha_inscripcion"])

	def test_baja_inscripcion_sincroniza_resumen_sin_cambiar_estado_socio(self) -> None:
		socio = insert_socio(dni="72001002", email="baja.insc@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test")
		ins_name = self._inscribir_zumba(socio.name)
		socio.reload()
		self.assertIn("Zumba", socio.actividad or "")

		frappe.set_user(self._secretaria)
		try:
			result = baja_inscripcion_desk(ins_name, motivo="Renuncia actividad")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(result["status"], "ok")
		self.assertEqual(frappe.db.get_value("Inscripcion Actividad", ins_name, "estado"), "Baja")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(socio.actividad or "", "")
		self.assertEqual(result["actividad_resumen"], "")

	def test_dar_baja_socio_pasa_inscripciones_activas_a_baja(self) -> None:
		socio = insert_socio(dni="72001007", email="baja.cascada@example.com")
		otro = insert_socio(dni="72001008", email="otro.cascada@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test")
		cambiar_estado(otro.name, "Activo", motivo="Test")
		zumba = self._ensure_zumba()
		natacion = self._ensure_actividad("Natacion Baja Cascada")
		ins_a = self._inscribir(socio.name, zumba)
		ins_b = self._inscribir(socio.name, natacion)
		ins_otro = self._inscribir(otro.name, zumba)

		frappe.set_user(self._secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Socio", socio.name, "estado"), "Baja")
		self.assertEqual(frappe.db.get_value("Inscripcion Actividad", ins_a, "estado"), "Baja")
		self.assertEqual(frappe.db.get_value("Inscripcion Actividad", ins_b, "estado"), "Baja")
		self.assertEqual(frappe.db.get_value("Inscripcion Actividad", ins_otro, "estado"), "Activa")
		socio.reload()
		self.assertEqual(socio.actividad or "", "")

	def test_no_duplicar_inscripcion_activa_equivalente(self) -> None:
		socio = insert_socio(dni="72001003", email="dup.insc@example.com")
		cambiar_estado(socio.name, ESTADO_SOCIO_PENDIENTE_INSCRIPCION, motivo="Test")
		zumba = self._ensure_zumba()

		frappe.set_user(self._secretaria)
		try:
			inscribir_actividades_desk(socio.name, [{"actividad": zumba}])
			inscribir_actividades_desk(socio.name, [{"actividad": zumba}])
		finally:
			frappe.set_user("Administrator")

		count = frappe.db.count(
			"Inscripcion Actividad",
			{"socio": socio.name, "actividad": zumba, "estado": "Activa"},
		)
		self.assertEqual(count, 1)

	def test_activar_socio_sin_inscripciones_permanece_permitido(self) -> None:
		socio = insert_socio(dni="72001004", email="activar.sin.insc@example.com")
		cambiar_estado(socio.name, ESTADO_SOCIO_PENDIENTE_INSCRIPCION, motivo="Test")

		frappe.set_user(self._secretaria)
		try:
			activar_socio_manual(socio.name)
		finally:
			frappe.set_user("Administrator")

		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": socio.name, "estado": "Activa"}),
			0,
		)

	def test_inscribir_desk_requiere_grupo_si_usa_grupos(self) -> None:
		actividad = "Basquet Inscripcion Req Grupo"
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"name": actividad,
					"titulo": actividad,
					"habilitada": 1,
					"usa_grupos": 1,
				}
			).insert(ignore_permissions=True)
		socio = insert_socio(dni="72001006", email="req.grupo.insc@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test")

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				inscribir_actividades_desk(socio.name, [{"actividad": actividad}])
		finally:
			frappe.set_user("Administrator")

	def test_usuario_sin_rol_no_puede_listar_ni_dar_baja(self) -> None:
		socio = insert_socio(dni="72001005", email="perm.insc@example.com")
		ins_name = self._inscribir_zumba(socio.name)
		email = f"socio_{socio.dni}@example.com"
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
				list_inscripciones_socio_desk(socio.name)
			with self.assertRaises(frappe.PermissionError):
				baja_inscripcion_desk(ins_name)
		finally:
			frappe.set_user("Administrator")

"""Tests panel catálogo Gestión de Actividades."""

from __future__ import annotations

import frappe
from frappe.exceptions import PermissionError

from frappe.exceptions import ValidationError

from club_management.activities.api.gestion_actividades_workspace import (
	create_actividad_desk,
	create_equipo_desk,
	create_grupo_desk,
	get_catalog,
	set_arancel_desk,
	update_actividad_desk,
	update_equipo_desk,
	update_grupo_desk,
)
from club_management.activities.services.gestion_actividades_panel import (
	create_actividad,
	create_arancel_item,
	create_equipo,
	create_grupo,
	get_catalog_payload,
	set_arancel,
	update_actividad,
	update_equipo,
	update_grupo,
)
from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


def _existing_seed_item() -> str:
	code = frappe.db.get_value(
		"Item",
		{"item_group": ["like", "%ICDPE%"], "is_stock_item": 0},
		"name",
	)
	if code:
		return code
	item_group = (
		frappe.db.get_value("Item Group", {"name": ["like", "ICDPE%"]}, "name")
		or frappe.db.get_value("Item Group", {}, "name")
		or "All Item Groups"
	)
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": "TEST-SEED-ITEM",
			"item_name": "TEST-SEED-ITEM",
			"item_group": item_group,
			"is_stock_item": 0,
			"standard_rate": 1000,
		}
	).insert(ignore_permissions=True)
	return "TEST-SEED-ITEM"


class TestGestionActividadesPanelService(MembersTestCase):
	def _ensure_item(self, code: str, rate: float = 1000.0) -> str:
		if frappe.db.exists("Item", code):
			frappe.db.set_value("Item", code, "standard_rate", rate)
			return code
		item_group = (
			frappe.db.get_value("Item Group", {"name": ["like", "ICDPE%"]}, "name")
			or frappe.db.get_value("Item Group", {}, "name")
			or "All Item Groups"
		)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": item_group,
				"is_stock_item": 0,
				"standard_rate": rate,
			}
		).insert(ignore_permissions=True)
		return code

	def _ensure_actividad(self, titulo: str, *, item: str = "", usa_grupos: int = 1) -> str:
		name = frappe.db.get_value("Actividad", {"titulo": titulo}, "name")
		if name:
			return name
		doc = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": titulo,
				"habilitada": 1,
				"usa_grupos": usa_grupos,
				"item": item,
				"orden": 1,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def test_create_actividad_desde_panel(self) -> None:
		result = create_actividad(titulo="Panel Nueva Actividad", usa_grupos=0)
		self.assertEqual(result["name"], "Panel Nueva Actividad")
		self.assertTrue(frappe.db.exists("Actividad", result["name"]))

	def test_get_catalog_devuelve_jerarquia(self) -> None:
		item = self._ensure_item("TEST-ACT-ITEM", 1500)
		actividad = self._ensure_actividad("Panel Test Actividad", item=item)
		grupo = create_grupo(actividad=actividad, titulo="Tira Panel")
		equipo = create_equipo(grupo_actividad=grupo["name"], titulo="U11 Panel")

		data = get_catalog_payload()
		match = next(a for a in data["actividades"] if a["name"] == actividad)
		self.assertEqual(match["item"], item)
		self.assertEqual(match["rate"], 1500.0)
		self.assertEqual(len(match["grupos"]), 1)
		self.assertEqual(match["grupos"][0]["name"], grupo["name"])
		self.assertEqual(match["grupos"][0]["equipos"][0]["name"], equipo["name"])

	def test_equipo_catalog_arancel_efectivo_hereda_grupo(self) -> None:
		from club_management.activities.services.gestion_actividades_panel import (
			resolve_arancel_efectivo_equipo,
		)

		item_grupo = self._ensure_item("TEST-EQ-HEREDA-GRUPO", 4100)
		actividad = self._ensure_actividad("Panel Hereda Grupo Act", usa_grupos=1)
		grupo = create_grupo(actividad=actividad, titulo="Tira Hereda")["name"]
		set_arancel(doctype="Grupo Actividad", name=grupo, item=item_grupo, rate=4100)
		equipo = create_equipo(grupo_actividad=grupo, titulo="Cat Sin Item")["name"]

		resumen = resolve_arancel_efectivo_equipo(equipo)
		self.assertEqual(resumen["item"], item_grupo)
		self.assertEqual(resumen["rate"], 4100.0)
		self.assertEqual(resumen["origen"], "Grupo")

		data = get_catalog_payload()
		act = next(a for a in data["actividades"] if a["name"] == actividad)
		eq = act["grupos"][0]["equipos"][0]
		self.assertEqual(eq["arancel"]["item"], item_grupo)
		self.assertEqual(eq["arancel"]["origen"], "Grupo")
		self.assertEqual(eq["arancel"]["rate"], 4100.0)

	def test_equipo_catalog_arancel_efectivo_propio(self) -> None:
		from club_management.activities.services.gestion_actividades_panel import (
			resolve_arancel_efectivo_equipo,
		)

		item_grupo = self._ensure_item("TEST-EQ-GRUPO-OWN", 2000)
		item_eq = self._ensure_item("TEST-EQ-OWN", 5500)
		actividad = self._ensure_actividad("Panel Equipo Own Act", usa_grupos=1)
		grupo = create_grupo(actividad=actividad, titulo="Tira Own")["name"]
		set_arancel(doctype="Grupo Actividad", name=grupo, item=item_grupo, rate=2000)
		equipo = create_equipo(grupo_actividad=grupo, titulo="Cat Own Item")["name"]
		set_arancel(doctype="Equipo Actividad", name=equipo, item=item_eq, rate=5500)

		resumen = resolve_arancel_efectivo_equipo(equipo)
		self.assertEqual(resumen["item"], item_eq)
		self.assertEqual(resumen["origen"], "Equipo")
		self.assertEqual(resumen["rate"], 5500.0)

	def test_set_arancel_actualiza_item_y_rate(self) -> None:
		actividad = self._ensure_actividad("Panel Arancel Act")
		item_a = self._ensure_item("TEST-AR-A", 800)
		item_b = self._ensure_item("TEST-AR-B", 1200)

		result = set_arancel(doctype="Actividad", name=actividad, item=item_b, rate=2200)
		self.assertEqual(result["item"], item_b)
		self.assertEqual(result["rate"], 2200.0)
		self.assertEqual(frappe.db.get_value("Actividad", actividad, "item"), item_b)
		self.assertEqual(frappe.db.get_value("Item", item_b, "standard_rate"), 2200.0)
		self.assertEqual(frappe.db.get_value("Item", item_a, "standard_rate"), 800.0)

	def test_set_arancel_grupo_actualiza_item_y_rate(self) -> None:
		actividad = self._ensure_actividad("Panel Grupo Arancel Act", usa_grupos=1)
		grupo = create_grupo(actividad=actividad, titulo="Tira Rate Panel")["name"]
		item = self._ensure_item("TEST-GR-AR-PANEL", 900)

		result = set_arancel(doctype="Grupo Actividad", name=grupo, item=item, rate=1750)

		self.assertEqual(result["item"], item)
		self.assertEqual(result["rate"], 1750.0)
		self.assertEqual(frappe.db.get_value("Grupo Actividad", grupo, "item"), item)
		self.assertEqual(frappe.db.get_value("Item", item, "standard_rate"), 1750.0)

	def test_set_arancel_solo_rate_usa_item_existente(self) -> None:
		actividad = self._ensure_actividad("Panel Rate Only Act", usa_grupos=1)
		grupo = create_grupo(actividad=actividad, titulo="Tira Rate Only")["name"]
		item = self._ensure_item("TEST-RATE-ONLY", 1000)
		set_arancel(doctype="Grupo Actividad", name=grupo, item=item, rate=1000)

		result = set_arancel(doctype="Grupo Actividad", name=grupo, item="", rate=2500)

		self.assertEqual(result["item"], item)
		self.assertEqual(result["rate"], 2500.0)
		self.assertEqual(frappe.db.get_value("Item", item, "standard_rate"), 2500.0)

	def test_set_arancel_nuevo_item_sin_rate_usa_tarifa_item(self) -> None:
		actividad = self._ensure_actividad("Panel Auto Rate Act")
		item = self._ensure_item("TEST-AUTO-RATE-PANEL", 3333)

		result = set_arancel(doctype="Actividad", name=actividad, item=item, rate=0)

		self.assertEqual(result["item"], item)
		self.assertEqual(result["rate"], 3333.0)

	def test_create_arancel_item_desde_panel(self) -> None:
		result = create_arancel_item(
			item_code="TEST-NUEVO-AR-PANEL",
			item_name="Arancel panel test",
			standard_rate=999,
		)
		self.assertEqual(result["item"], "TEST-NUEVO-AR-PANEL")
		self.assertEqual(result["rate"], 999.0)
		self.assertTrue(frappe.db.exists("Item", "TEST-NUEVO-AR-PANEL"))


class TestGestionActividadesEdicionPanel(MembersTestCase):
	def test_update_actividad_persiste_metadatos(self) -> None:
		actividad = create_actividad(titulo="Edit Act Panel", usa_grupos=0)["name"]

		result = update_actividad(
			name=actividad,
			titulo="Edit Act Renombrada",
			usa_grupos=1,
			orden=7,
			descripcion="Descripción panel",
		)

		self.assertEqual(result["name"], "Edit Act Renombrada")
		self.assertEqual(frappe.db.get_value("Actividad", result["name"], "usa_grupos"), 1)
		self.assertEqual(frappe.db.get_value("Actividad", result["name"], "orden"), 7)
		self.assertEqual(
			frappe.db.get_value("Actividad", result["name"], "descripcion"),
			"Descripción panel",
		)

	def test_update_actividad_usa_grupos_1_a_0_con_inscripcion_grupo_falla(self) -> None:
		actividad = create_actividad(titulo="Act Usa Grupos Panel", usa_grupos=1)["name"]
		grupo = create_grupo(actividad=actividad, titulo="Tira Panel Edit")["name"]
		socio = insert_socio(dni="71001001", email="act.grupo.edit@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test")
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": actividad, "grupo_actividad": grupo}],
			activar=False,
		)

		with self.assertRaises(ValidationError):
			update_actividad(name=actividad, usa_grupos=0)

	def test_deshabilitar_actividad_sin_inscripciones_excluye_de_catalogo(self) -> None:
		actividad = create_actividad(titulo="Act Deshab Panel", usa_grupos=0)["name"]

		update_actividad(name=actividad, habilitada=0)

		self.assertEqual(frappe.db.get_value("Actividad", actividad, "habilitada"), 0)
		self.assertTrue(frappe.db.exists("Actividad", actividad))
		names = [row["name"] for row in get_catalog_payload()["actividades"]]
		self.assertNotIn(actividad, names)

	def test_deshabilitar_actividad_con_inscripciones_activas_falla(self) -> None:
		actividad = create_actividad(titulo="Act Block Disable", usa_grupos=0)["name"]
		socio = insert_socio(dni="71001002", email="act.disable@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test")
		inscribir_socio_selecciones(socio.name, [{"actividad": actividad}], activar=False)

		with self.assertRaises(ValidationError):
			update_actividad(name=actividad, habilitada=0)

	def test_update_grupo_renombra_si_cambia_titulo(self) -> None:
		actividad = create_actividad(titulo="Act Grupo Rename", usa_grupos=1)["name"]
		grupo = create_grupo(actividad=actividad, titulo="Tira Original")["name"]

		result = update_grupo(name=grupo, titulo="Tira Azul", orden=3)

		expected_name = f"{actividad} / Tira Azul"
		self.assertEqual(result["name"], expected_name)
		self.assertEqual(frappe.db.get_value("Grupo Actividad", expected_name, "orden"), 3)
		self.assertFalse(frappe.db.exists("Grupo Actividad", grupo))

	def test_update_equipo_renombra_si_cambia_titulo(self) -> None:
		actividad = create_actividad(titulo="Act Equipo Rename", usa_grupos=1)["name"]
		grupo = create_grupo(actividad=actividad, titulo="Tira Equipo")["name"]
		equipo = create_equipo(grupo_actividad=grupo, titulo="U11 Original")["name"]

		result = update_equipo(name=equipo, titulo="U11 Panel", habilitada=1)

		expected_name = f"{grupo} / U11 Panel"
		self.assertEqual(result["name"], expected_name)
		self.assertFalse(frappe.db.exists("Equipo Actividad", equipo))

	def test_deshabilitar_grupo_excluye_de_catalogo(self) -> None:
		actividad = create_actividad(titulo="Act Grupo Disable", usa_grupos=1)["name"]
		grupo = create_grupo(actividad=actividad, titulo="Tira Disable")["name"]

		update_grupo(name=grupo, habilitada=0)

		catalog = get_catalog_payload()
		match = next(a for a in catalog["actividades"] if a["name"] == actividad)
		self.assertEqual(match["grupos"], [])


class TestGestionActividadesPanelPermissions(MembersTestCase):
	def test_guest_no_puede_consultar_catalogo(self) -> None:
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			get_catalog()
		frappe.set_user("Administrator")

	def test_secretaria_puede_crear_actividad(self) -> None:
		user = make_secretaria_user("sec.act.create@example.com")
		frappe.set_user(user)
		result = create_actividad_desk(titulo="API Actividad Panel", usa_grupos=0)
		self.assertEqual(result["titulo"], "API Actividad Panel")
		frappe.set_user("Administrator")

	def test_secretaria_puede_crear_grupo_y_equipo(self) -> None:
		user = make_secretaria_user("sec.act.panel@example.com")
		actividad = frappe.db.get_value("Actividad", {"habilitada": 1}, "name")
		if not actividad:
			self.skipTest("Sin actividades seed")
		frappe.set_user(user)
		grupo = create_grupo_desk(actividad=actividad, titulo="Grupo API Test")
		grupo_name = grupo["name"]
		equipo = create_equipo_desk(grupo_actividad=grupo_name, titulo="Equipo API Test")
		self.assertTrue(frappe.db.exists("Equipo Actividad", equipo["name"]))
		frappe.set_user("Administrator")

	def test_secretaria_puede_set_arancel(self) -> None:
		user = make_secretaria_user("sec.arancel@example.com")
		actividad = frappe.db.get_value("Actividad", {"habilitada": 1}, "name")
		if not actividad:
			self.skipTest("Sin actividades seed")
		item_code = _existing_seed_item()
		frappe.set_user(user)
		result = set_arancel_desk(
			doctype="Actividad",
			name=actividad,
			item=item_code,
			rate=3333,
		)
		self.assertEqual(result["rate"], 3333.0)
		frappe.set_user("Administrator")

	def test_secretaria_puede_editar_actividad(self) -> None:
		user = make_secretaria_user("sec.act.edit@example.com")
		actividad = create_actividad(titulo="API Edit Act", usa_grupos=0)["name"]
		frappe.set_user(user)
		result = update_actividad_desk(name=actividad, titulo="API Edit Act 2", orden=2)
		self.assertEqual(result["name"], "API Edit Act 2")
		frappe.set_user("Administrator")

	def test_secretaria_puede_crear_arancel_item(self) -> None:
		from club_management.activities.api.gestion_actividades_workspace import create_arancel_item_desk

		user = make_secretaria_user("sec.arancel.create@example.com")
		frappe.set_user(user)
		result = create_arancel_item_desk(
			item_code="TEST-SEC-AR-PANEL",
			item_name="Arancel Secretaria Panel",
			standard_rate=750,
		)
		self.assertEqual(result["item"], "TEST-SEC-AR-PANEL")
		self.assertEqual(result["rate"], 750.0)
		self.assertTrue(frappe.db.exists("Item", "TEST-SEC-AR-PANEL"))
		self.assertEqual(
			frappe.db.get_value("Item", "TEST-SEC-AR-PANEL", "standard_rate"),
			750.0,
		)
		frappe.set_user("Administrator")

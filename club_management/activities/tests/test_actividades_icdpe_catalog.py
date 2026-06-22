"""Tests del catálogo ICDPE de actividades."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_icdpe_catalog import (
	ACTIVIDADES_CATALOGO_ICDPE,
	_resolve_actividad_docname,
	resolve_item_name,
	sync_actividades_catalogo_icdpe,
	upsert_actividad_catalog_entry,
)
from club_management.members.test_helpers import MembersTestCase


class TestActividadesIcdpeCatalog(MembersTestCase):
	def test_catalogo_oficial_tiene_dieciocho_actividades(self) -> None:
		self.assertEqual(len(ACTIVIDADES_CATALOGO_ICDPE), 18)
		titulos = [e.titulo for e in ACTIVIDADES_CATALOGO_ICDPE]
		self.assertIn("Basquet Masculino", titulos)
		self.assertIn("Boxeo", titulos)
		self.assertIn("Yoga", titulos)
		self.assertIn("Taekwondo", titulos)
		self.assertIn("Zumba", titulos)
		self.assertIn("Ritmos Latinos", titulos)
		self.assertIn("Gimnasio Fitness", titulos)

	def test_sync_crea_actividades_habilitadas(self) -> None:
		sync_actividades_catalogo_icdpe(deshabilitar_legacy=True)
		habilitadas = frappe.get_all(
			"Actividad",
			filters={"habilitada": 1},
			pluck="titulo",
			order_by="orden asc",
		)
		self.assertEqual(len(habilitadas), 18)
		self.assertEqual(set(habilitadas), {e.titulo for e in ACTIVIDADES_CATALOGO_ICDPE})
		if frappe.db.exists("Actividad", "Natación"):
			self.assertFalse(frappe.db.get_value("Actividad", "Natación", "habilitada"))

	def test_sync_vincula_item_si_existe(self) -> None:
		entry = next(e for e in ACTIVIDADES_CATALOGO_ICDPE if e.titulo == "Futbol")
		if not frappe.db.exists("Item", entry.item_code):
			if not frappe.db.exists("UOM", "Nos"):
				frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": entry.item_code,
					"item_name": f"Arancel mensual actividad — {entry.titulo}",
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Item", entry.item_code))

		item_link = resolve_item_name(entry.item_code)
		self.assertEqual(item_link, entry.item_code)

		upsert_actividad_catalog_entry(entry)
		futbol_name = _resolve_actividad_docname("Futbol")
		self.assertTrue(futbol_name)
		self.assertEqual(frappe.db.get_value("Actividad", futbol_name, "item"), item_link)

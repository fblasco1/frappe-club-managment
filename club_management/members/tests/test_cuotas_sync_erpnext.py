"""Tests sincronización cuotas sociales → ERPNext (spec cuotas_sync_erpnext.md)."""

from __future__ import annotations

import frappe
from frappe.exceptions import ValidationError

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.secretaria_workspace_panel import (
	CUOTAS_CATEGORIAS,
	save_cuotas_sociales_payload,
)
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.suscripciones_cobro_mensual import (
	PRICE_LIST_NAME,
	erpnext_subscriptions_disponible,
)


class TestCuotasSyncErpnext(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_subscriptions_disponible():
			self.skipTest("ERPNext Subscriptions no instalado")

	def _all_cuota_rows(self) -> list[dict[str, float | str]]:
		return [
			{"categoria": categoria, "monto": 10_000 + idx * 500}
			for idx, categoria in enumerate(CUOTAS_CATEGORIAS)
		]

	def test_save_cuotas_actualiza_item_standard_rate_y_precio_referencia(self) -> None:
		rows = self._all_cuota_rows()
		activo_monto = 31_500.0
		rows[0]["monto"] = activo_monto

		save_cuotas_sociales_payload(rows)

		self.assertEqual(
			float(frappe.db.get_value("Item", CUOTA_SOCIAL_ITEM_CODE, "standard_rate") or 0),
			activo_monto,
		)
		price_rate = frappe.db.get_value(
			"Item Price",
			{"item_code": CUOTA_SOCIAL_ITEM_CODE, "price_list": PRICE_LIST_NAME},
			"price_list_rate",
		)
		self.assertEqual(float(price_rate or 0), activo_monto)

	def test_save_cuotas_asigna_item_unico_y_item_cuota_social(self) -> None:
		save_cuotas_sociales_payload(self._all_cuota_rows())

		settings = frappe.get_single("Club Settings")
		self.assertEqual(settings.item_cuota_social, CUOTA_SOCIAL_ITEM_CODE)
		for row in settings.cuotas_categoria or []:
			self.assertEqual(row.item, CUOTA_SOCIAL_ITEM_CODE)

	def test_save_cuotas_rechaza_monto_invalido_sin_persistir(self) -> None:
		settings = frappe.get_single("Club Settings")
		original = {
			row.categoria: float(row.monto)
			for row in (settings.cuotas_categoria or [])
		}

		with self.assertRaises(ValidationError):
			save_cuotas_sociales_payload(
				[{"categoria": "Menor", "monto": 0}, {"categoria": "Activo", "monto": 29_000}]
			)

		settings.reload()
		by_cat = {row.categoria: float(row.monto) for row in (settings.cuotas_categoria or [])}
		for categoria, monto in original.items():
			self.assertEqual(by_cat.get(categoria), monto)

	def test_sync_cuotas_sociales_club_sin_fila_vitalicio(self) -> None:
		sync_cuotas_sociales_club()

		settings = frappe.get_single("Club Settings")
		categorias = {row.categoria for row in (settings.cuotas_categoria or [])}
		self.assertNotIn("Vitalicio", categorias)
		self.assertEqual(categorias, set(CUOTAS_CATEGORIAS))

	def test_sync_post_guardado_menor_mantiene_item_unico(self) -> None:
		rows = self._all_cuota_rows()
		rows[1]["monto"] = 27_200.0  # Menor

		save_cuotas_sociales_payload(rows)
		sync_cuotas_sociales_club(update_montos_from_vigentes=False)

		settings = frappe.get_single("Club Settings")
		menor = next(row for row in (settings.cuotas_categoria or []) if row.categoria == "Menor")
		self.assertEqual(float(menor.monto), 27_200.0)
		self.assertEqual(menor.item, CUOTA_SOCIAL_ITEM_CODE)
		self.assertEqual(settings.item_cuota_social, CUOTA_SOCIAL_ITEM_CODE)

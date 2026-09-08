"""Valores de cuota en la landing pública.

Spec: `club_management/specs/valores_cuota_social_page.md` (landing pública).
"""

from __future__ import annotations

import frappe
from frappe.exceptions import PermissionError, ValidationError

from club_management.members.api.cuota_publica import get_valores_cuota
from club_management.members.api.secretaria_workspace import save_cuotas_sociales
from club_management.members.services.cuotas_sociales_public import (
	get_valores_cuota_publica_payload,
)
from club_management.members.services.secretaria_workspace_panel import (
	CUOTAS_CATEGORIAS,
	save_cuotas_sociales_payload,
)
from club_management.members.test_helpers import MembersTestCase


class TestCuotaPublica(MembersTestCase):
	def _rows(self, activo: float = 29_000.0) -> list[dict[str, float | str]]:
		base = 10_000.0
		out: list[dict[str, float | str]] = []
		for idx, categoria in enumerate(CUOTAS_CATEGORIAS):
			monto = activo if categoria == "Activo" else base + idx * 100
			out.append({"categoria": categoria, "monto": monto})
		return out

	def test_payload_publico_refleja_club_settings_sin_item_erpnext(self) -> None:
		save_cuotas_sociales_payload(self._rows(31_250.0), vigente_desde="2026-04-01")

		try:
			frappe.set_user("Guest")
			payload = get_valores_cuota_publica_payload()
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(payload.get("vigente_desde"), "2026-04-01")
		self.assertNotIn("item", payload)
		self.assertNotIn("item_cuota_social_default", payload)

		by_cat = {row["categoria"]: row for row in payload["categorias"]}
		self.assertEqual(by_cat["Activo"]["valor"], 31_250.0)
		self.assertTrue(by_cat["Activo"]["condicion"])
		for row in payload["categorias"]:
			self.assertEqual(set(row.keys()), {"categoria", "valor", "condicion"})
			self.assertGreater(row["valor"], 0)

	def test_guardar_en_desk_actualiza_el_payload_publico(self) -> None:
		save_cuotas_sociales_payload(self._rows(29_000.0), vigente_desde="2026-01-01")
		save_cuotas_sociales_payload(self._rows(40_000.0), vigente_desde="2026-08-01")

		payload = get_valores_cuota_publica_payload()
		by_cat = {row["categoria"]: row for row in payload["categorias"]}
		self.assertEqual(by_cat["Activo"]["valor"], 40_000.0)
		self.assertEqual(payload["vigente_desde"], "2026-08-01")

	def test_guest_lee_valores_y_no_puede_guardar(self) -> None:
		save_cuotas_sociales_payload(self._rows(29_000.0), vigente_desde="2026-04-01")
		original = get_valores_cuota_publica_payload()["categorias"][0]["valor"]

		frappe.set_user("Guest")
		leido = get_valores_cuota()
		self.assertEqual(leido["categorias"][0]["valor"], original)

		with self.assertRaises((PermissionError, ValidationError)):
			save_cuotas_sociales(self._rows(99_999.0))

		frappe.set_user("Administrator")
		despues = get_valores_cuota_publica_payload()
		self.assertEqual(despues["categorias"][0]["valor"], original)

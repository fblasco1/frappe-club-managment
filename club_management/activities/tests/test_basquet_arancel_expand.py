"""Expansión de ítems de arancel básquet para Pagos por equipo.

Spec: `club_management/specs/pagos_por_equipo.md` (SUPERIOR B).
"""

from __future__ import annotations

from unittest import TestCase

from club_management.activities.data.basquet_aranceles_icdpe import (
	ITEM_MASCULINO_SUPERIOR_AMARILLO,
	expand_arancel_item_codes_for_pagos,
	expand_basquet_arancel_item_codes,
)


class TestBasquetArancelExpand(TestCase):
	def test_superior_amarillo_incluye_factura_historica_voley(self) -> None:
		codes = expand_basquet_arancel_item_codes(ITEM_MASCULINO_SUPERIOR_AMARILLO)
		self.assertIn(ITEM_MASCULINO_SUPERIOR_AMARILLO, codes)
		self.assertIn("ICDPE-VOLEY-FEDERADO", codes)

	def test_pagos_expand_une_voley_y_basquet(self) -> None:
		codes = expand_arancel_item_codes_for_pagos(ITEM_MASCULINO_SUPERIOR_AMARILLO)
		self.assertIn(ITEM_MASCULINO_SUPERIOR_AMARILLO, codes)
		self.assertIn("ICDPE-VOLEY-FEDERADO", codes)

	def test_otro_item_no_agrega_voley(self) -> None:
		codes = expand_basquet_arancel_item_codes("ICDPE-BASQUET-MASCULINO-MINIBASQUET")
		self.assertEqual(codes, {"ICDPE-BASQUET-MASCULINO-MINIBASQUET"})

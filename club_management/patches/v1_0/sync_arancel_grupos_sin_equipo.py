"""Sincroniza aranceles a nivel Grupo/tira (facturación sin equipo).

- Re-seed estructura con `Grupo.item` en deportes no-básquet.
- Remapea equipos Vóley Tira U11/U12 de ICDPE-VOLEY-TIRA-21500 → FEDERADO.
"""

from __future__ import annotations

import frappe

from club_management.activities.data.futbol_aranceles_icdpe import FUTBOL_ITEM_SPECS
from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.activities.data.patin_aranceles_icdpe import PATIN_ITEM_SPECS
from club_management.activities.data.voley_aranceles_icdpe import (
	ITEM_VOLEY_FEDERADO,
	ITEM_VOLEY_TIRA_21500,
	VOLEY_ITEM_SPECS,
)
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def _remap_voley_tira_u11_u12_to_federado() -> int:
	"""Equipos U11/U12 que aún apuntan al ítem legacy 21500 pasan a Federado."""
	if not frappe.db.exists("Item", ITEM_VOLEY_FEDERADO):
		return 0
	updated = 0
	for name in frappe.get_all(
		"Equipo Actividad",
		filters={
			"item": ITEM_VOLEY_TIRA_21500,
			"titulo": ["in", ["U11", "U12"]],
			"habilitada": 1,
		},
		pluck="name",
	):
		frappe.db.set_value(
			"Equipo Actividad",
			name,
			"item",
			ITEM_VOLEY_FEDERADO,
			update_modified=True,
		)
		updated += 1
	return updated


def execute() -> None:
	sync_arancel_items(VOLEY_ITEM_SPECS)
	sync_arancel_items(FUTBOL_ITEM_SPECS)
	sync_arancel_items(PATIN_ITEM_SPECS)
	sync_arancel_items(OTRAS_ACTIVIDADES_ITEM_SPECS)
	seed_estructura_actividades_completa(crear_equipos=True)
	_remap_voley_tira_u11_u12_to_federado()

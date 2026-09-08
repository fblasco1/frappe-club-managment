"""Sincroniza grupos Funcional (GAP/CROSSFIT/Facundo) y remapea inscripciones legacy."""

from __future__ import annotations

import frappe

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)

# titulo legacy → titulo nuevo (bajo Actividad Funcional)
_LEGACY_GRUPO_TITULO: dict[str, str] = {
	"1 Clase por Semana": "Funcional 1 vez/sem - Prof Facundo",
	"2 Clases por Semana": "Funcional 2 veces/sem - Prof Facundo",
	"GAP": "GAP 2 veces/sem - Prof Noelia",
}


def _remap_inscripciones_grupos_legacy() -> int:
	funcional = frappe.db.get_value("Actividad", {"titulo": "Funcional"}, "name")
	if not funcional:
		return 0
	updated = 0
	for old_titulo, new_titulo in _LEGACY_GRUPO_TITULO.items():
		old_name = f"{funcional} / {old_titulo}"
		new_name = f"{funcional} / {new_titulo}"
		if not frappe.db.exists("Grupo Actividad", new_name):
			continue
		for ins_name in frappe.get_all(
			"Inscripcion Actividad",
			filters={"grupo_actividad": old_name},
			pluck="name",
		):
			frappe.db.set_value(
				"Inscripcion Actividad",
				ins_name,
				"grupo_actividad",
				new_name,
				update_modified=True,
			)
			updated += 1
	return updated


def execute() -> None:
	sync_arancel_items(OTRAS_ACTIVIDADES_ITEM_SPECS)
	seed_estructura_actividades_completa(crear_equipos=True)
	_remap_inscripciones_grupos_legacy()

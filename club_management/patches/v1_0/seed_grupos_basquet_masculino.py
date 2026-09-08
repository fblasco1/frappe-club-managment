"""Grupos/tiras de ejemplo para Basquet Masculino (Secretaría completa ítems en Desk)."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_icdpe_catalog import (
	ACTIVIDADES_CON_GRUPOS,
	sync_actividades_catalogo_icdpe,
)

_TIRAS_BASQUET_MASC: tuple[tuple[str, int], ...] = (
	("Tira Azul", 10),
	("Tira Amarilla", 20),
	("Tira Flex", 30),
	("Primera Division B", 40),
)


def _upsert_grupo(actividad: str, titulo: str, orden: int) -> str:
	name = f"{actividad} / {titulo}"
	if frappe.db.exists("Grupo Actividad", name):
		frappe.db.set_value(
			"Grupo Actividad",
			name,
			{"habilitada": 1, "orden": orden, "actividad": actividad, "titulo": titulo},
			update_modified=True,
		)
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Grupo Actividad",
			"name": name,
			"actividad": actividad,
			"titulo": titulo,
			"orden": orden,
			"habilitada": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def execute() -> None:
	"""Obsoleto: delega al seed completo (grupos + equipos de todas las actividades con tiras)."""
	from club_management.activities.services.estructura_actividades_seed import (
		seed_estructura_actividades_completa,
	)

	seed_estructura_actividades_completa(crear_equipos=True)

"""Catálogo inicial de espacios físicos del club (idempotente)."""

from __future__ import annotations

import frappe

# (titulo, tipo, alquilable)
ESPACIOS_SEED: tuple[tuple[str, str, int], ...] = (
	("GIMNASIO BAJO TRIBUNA", "Gimnasio", 0),
	("SALON P.B.", "Salon", 1),
	("SUM P.B.", "Salon", 1),
	("SUBSUELO", "Otro", 1),
	("SALA ALBAMONTE", "Salon", 1),
	("PARRILLA - TERRAZA", "Otro", 1),
	("LA CASONA", "Salon", 1),
)


def ensure_espacios_catalogo() -> list[str]:
	"""Crea los espacios del catálogo si no existen. Devuelve nombres creados o ya existentes."""
	names: list[str] = []
	for titulo, tipo, alquilable in ESPACIOS_SEED:
		if frappe.db.exists("Espacio", titulo):
			names.append(titulo)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Espacio",
				"titulo": titulo,
				"tipo": tipo,
				"alquilable": alquilable,
				"habilitado": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		names.append(doc.name)
	return names

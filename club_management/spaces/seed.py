"""Catálogo inicial de espacios físicos del club (idempotente)."""

from __future__ import annotations

import frappe

from club_management.spaces.planilla import CANCHA_1, CANCHA_2, CANCHA_3

# (titulo, tipo, alquilable)
ESPACIOS_SEED: tuple[tuple[str, str, int], ...] = (
	(CANCHA_1, "Cancha", 0),
	(CANCHA_2, "Cancha", 0),
	(CANCHA_3, "Cancha", 0),
	("GIMNASIO BAJO TRIBUNA", "Gimnasio", 0),
	("SALON P.B.", "Salon", 1),
	("SUM P.B.", "Salon", 1),
	("SUBSUELO", "Otro", 1),
	("SALA ALBAMONTE", "Salon", 1),
	("PARRILLA - TERRAZA", "Otro", 1),
	("LA CASONA", "Salon", 1),
)


def ensure_espacios_catalogo() -> list[str]:
	"""Crea o alinea los espacios del catálogo. Devuelve nombres creados o ya existentes."""
	names: list[str] = []
	for titulo, tipo, alquilable in ESPACIOS_SEED:
		if frappe.db.exists("Espacio", titulo):
			doc = frappe.get_doc("Espacio", titulo)
			changed = False
			if doc.tipo != tipo:
				doc.tipo = tipo
				changed = True
			if int(doc.alquilable or 0) != alquilable:
				doc.alquilable = alquilable
				changed = True
			if int(doc.habilitado or 0) != 1:
				doc.habilitado = 1
				changed = True
			if changed:
				doc.save(ignore_permissions=True)
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

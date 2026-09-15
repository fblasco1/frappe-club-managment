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

TARIFAS_SOCIO: dict[str, float] = {
	"SALON P.B.": 28000,
	"SUM P.B.": 30000,
	"SUBSUELO": 18000,
	"SALA ALBAMONTE": 25000,
	"PARRILLA - TERRAZA": 20000,
	"LA CASONA": 35000,
}

IMAGENES_PORTAL: dict[str, str] = {
	"SALON P.B.": "/images/salon.png",
	"SUM P.B.": "/images/salon.png",
	"SALA ALBAMONTE": "/images/salon.png",
	"LA CASONA": "/images/salon.png",
	"PARRILLA - TERRAZA": "/placeholder.jpg",
	"SUBSUELO": "/placeholder.jpg",
}

COMBOS: tuple[tuple[str, str], ...] = (
	("PARRILLA - TERRAZA", "SALA ALBAMONTE"),
)


def _sync_combo(espacio: str, partners: list[str]) -> None:
	doc = frappe.get_doc("Espacio", espacio)
	current = {row.espacio for row in (doc.combo_con or [])}
	desired = set(partners)
	if current == desired:
		return
	doc.set("combo_con", [])
	for partner in partners:
		if frappe.db.exists("Espacio", partner):
			doc.append("combo_con", {"espacio": partner})
	doc.save(ignore_permissions=True)


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
			tarifa = TARIFAS_SOCIO.get(titulo)
			if tarifa is not None and float(doc.get("tarifa_socio") or 0) != float(tarifa):
				doc.tarifa_socio = tarifa
				changed = True
			img = IMAGENES_PORTAL.get(titulo)
			if img and (doc.get("imagen_portal") or "") != img:
				doc.imagen_portal = img
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
				"tarifa_socio": TARIFAS_SOCIO.get(titulo) or 0,
				"imagen_portal": IMAGENES_PORTAL.get(titulo) or "",
			}
		)
		doc.insert(ignore_permissions=True)
		names.append(doc.name)

	partners: dict[str, list[str]] = {}
	for a, b in COMBOS:
		partners.setdefault(a, []).append(b)
		partners.setdefault(b, []).append(a)
	for espacio, plist in partners.items():
		if frappe.db.exists("Espacio", espacio):
			_sync_combo(espacio, plist)

	return names

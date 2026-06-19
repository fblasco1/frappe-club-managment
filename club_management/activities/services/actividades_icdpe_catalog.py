"""Catálogo oficial de actividades alineado al plan ICDPE (Items + centros de costo).

Cada fila apunta al Item de arancel mensual creado por
`scripts/icdpe_create_service_items.py` (prefijo `ICDPE-ARANCEL-MENSUAL-…`).
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe


@dataclass(frozen=True)
class ActividadCatalogEntry:
	"""Actividad operativa del club."""

	titulo: str
	orden: int
	item_code: str
	"""`item_code` del Item ERPNext (arancel mensual de la actividad)."""


# Orden y títulos acordados con Secretaría / plan de cuentas ICDPE.
ACTIVIDADES_CATALOGO_ICDPE: tuple[ActividadCatalogEntry, ...] = (
	ActividadCatalogEntry("Basquet Masculino", 10, "ICDPE-ARANCEL-MENSUAL-basquet-masculino"),
	ActividadCatalogEntry("Basquet Femenino", 20, "ICDPE-ARANCEL-MENSUAL-basquet-femenino"),
	ActividadCatalogEntry("Voley Femenino", 30, "ICDPE-ARANCEL-MENSUAL-voley"),
	ActividadCatalogEntry("Futbol", 40, "ICDPE-ARANCEL-MENSUAL-futbol"),
	ActividadCatalogEntry("Patin Artistico", 50, "ICDPE-ARANCEL-MENSUAL-patin"),
	ActividadCatalogEntry("Gimnasia Artistica", 60, "ICDPE-ARANCEL-MENSUAL-gimnasia-artistica"),
	ActividadCatalogEntry("Iniciacion Deportiva", 70, "ICDPE-ARANCEL-MENSUAL-ACT-iniciacion-deportiva"),
	ActividadCatalogEntry("Danza", 80, "ICDPE-ARANCEL-MENSUAL-ACT-danza"),
	ActividadCatalogEntry("Gimnasio Fitness", 90, "ICDPE-ARANCEL-MENSUAL-FITNESS-MUSC"),
	ActividadCatalogEntry("Funcional", 100, "ICDPE-ARANCEL-MENSUAL-ACT-funcional"),
	ActividadCatalogEntry("Crossfit", 110, "ICDPE-ARANCEL-MENSUAL-ACT-crossfit"),
	ActividadCatalogEntry("Ritmos Latinos", 120, "ICDPE-ARANCEL-MENSUAL-ACT-ritmos-latinos"),
	ActividadCatalogEntry("Zumba", 130, "ICDPE-ARANCEL-MENSUAL-ACT-zumba"),
)

# Actividades que requieren elegir grupo/tira al inscribir (el arancel va en Grupo Actividad).
ACTIVIDADES_CON_GRUPOS: frozenset[str] = frozenset(
	{
		"Basquet Masculino",
		"Basquet Femenino",
		"Voley Femenino",
		"Futbol",
	}
)

_TITULOS_OFICIALES = frozenset(e.titulo for e in ACTIVIDADES_CATALOGO_ICDPE)

# Títulos del seed anterior u otras variantes → catálogo ICDPE actual.
_LEGACY_TITULO_A_OFICIAL: dict[str, str | None] = {
	"Básquet Masculino": "Basquet Masculino",
	"Básquet Femenino": "Basquet Femenino",
	"Fútbol": "Futbol",
	"Vóley": "Voley Femenino",
	"Vóley Femenino": "Voley Femenino",
	"Natación": None,
	"Gimnasio": "Gimnasio Fitness",
	"Tenis": None,
	"Handball": None,
	"Hockey": None,
}


def _relink_inscripciones_actividad(actividad_vieja: str, actividad_nueva: str) -> None:
	if not frappe.db.table_exists("tabInscripcion Actividad"):
		return
	for row in frappe.get_all(
		"Inscripcion Actividad",
		filters={"actividad": actividad_vieja},
		pluck="name",
	):
		frappe.db.set_value(
			"Inscripcion Actividad",
			row,
			"actividad",
			actividad_nueva,
			update_modified=False,
		)


def _migrate_legacy_actividades() -> None:
	"""Deshabilita duplicados legacy; el upsert oficial actualiza título e ítem."""
	for titulo_viejo, titulo_nuevo in _LEGACY_TITULO_A_OFICIAL.items():
		if not frappe.db.exists("Actividad", titulo_viejo):
			continue
		if titulo_nuevo and _resolve_actividad_docname(titulo_nuevo) not in (None, titulo_viejo):
			_relink_inscripciones_actividad(titulo_viejo, titulo_nuevo)
			frappe.db.set_value(
				"Actividad",
				titulo_viejo,
				"habilitada",
				0,
				update_modified=True,
			)
		elif not titulo_nuevo:
			frappe.db.set_value(
				"Actividad",
				titulo_viejo,
				"habilitada",
				0,
				update_modified=True,
			)


def resolve_item_name(item_code: str) -> str | None:
	"""Devuelve el `name` del Item si existe en el sitio."""
	if not item_code:
		return None
	try:
		if frappe.db.exists("Item", item_code):
			return item_code
		return frappe.db.get_value("Item", {"item_code": item_code}, "name")
	except Exception:
		return None


def _resolve_actividad_docname(titulo_oficial: str) -> str | None:
	"""Localiza un registro existente (name o título legacy)."""
	if frappe.db.exists("Actividad", titulo_oficial):
		return titulo_oficial
	for titulo_viejo, titulo_nuevo in _LEGACY_TITULO_A_OFICIAL.items():
		if titulo_nuevo == titulo_oficial and frappe.db.exists("Actividad", titulo_viejo):
			return titulo_viejo
	name = frappe.db.get_value("Actividad", {"titulo": titulo_oficial}, "name")
	return name


def upsert_actividad_catalog_entry(entry: ActividadCatalogEntry) -> str:
	"""Crea o actualiza una `Actividad` del catálogo ICDPE. Devuelve `name`."""
	item_link = resolve_item_name(entry.item_code)
	payload: dict = {
		"titulo": entry.titulo,
		"habilitada": 1,
		"orden": entry.orden,
		"usa_grupos": 1 if entry.titulo in ACTIVIDADES_CON_GRUPOS else 0,
	}
	if item_link:
		payload["item"] = item_link

	existing = _resolve_actividad_docname(entry.titulo)
	if existing:
		frappe.db.set_value("Actividad", existing, "titulo", entry.titulo, update_modified=False)
		frappe.db.set_value("Actividad", existing, "orden", entry.orden, update_modified=False)
		frappe.db.set_value("Actividad", existing, "habilitada", 1, update_modified=False)
		if item_link:
			frappe.db.set_value("Actividad", existing, "item", item_link, update_modified=True)
		else:
			frappe.db.set_value("Actividad", existing, "modified", frappe.utils.now(), update_modified=False)
		return existing

	doc = frappe.get_doc({"doctype": "Actividad", **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def sync_actividades_catalogo_icdpe(*, deshabilitar_legacy: bool = True) -> list[str]:
	"""Sincroniza el catálogo completo. Devuelve nombres de actividades oficiales."""
	_migrate_legacy_actividades()
	names: list[str] = []
	for entry in ACTIVIDADES_CATALOGO_ICDPE:
		names.append(upsert_actividad_catalog_entry(entry))

	if deshabilitar_legacy and frappe.db.table_exists("tabActividad"):
		for row in frappe.get_all("Actividad", fields=["name", "titulo"]):
			titulo = (row.titulo or row.name or "").strip()
			if titulo not in _TITULOS_OFICIALES:
				frappe.db.set_value("Actividad", row.name, "habilitada", 0, update_modified=True)

	return names

"""Catálogo jerárquico para el workspace Gestión de Actividades."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

ACTIVIDAD_DOCTYPE = "Actividad"
GRUPO_DOCTYPE = "Grupo Actividad"
EQUIPO_DOCTYPE = "Equipo Actividad"
INSCRIPCION_DOCTYPE = "Inscripcion Actividad"
ARANCEL_DOCTYPES = frozenset({ACTIVIDAD_DOCTYPE, GRUPO_DOCTYPE, EQUIPO_DOCTYPE})


def get_catalog_payload() -> dict[str, Any]:
	"""Árbol actividad → grupos → equipos con aranceles resueltos."""
	actividades = frappe.get_all(
		ACTIVIDAD_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo", "item", "usa_grupos", "orden", "descripcion"],
		order_by="orden asc, titulo asc",
	)
	grupos = frappe.get_all(
		GRUPO_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo", "actividad", "item", "orden"],
		order_by="orden asc, titulo asc",
	)
	equipos = frappe.get_all(
		EQUIPO_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo", "grupo_actividad", "item", "orden"],
		order_by="orden asc, titulo asc",
	)

	grupos_by_actividad: dict[str, list[dict[str, Any]]] = {}
	for grupo in grupos:
		grupos_by_actividad.setdefault(grupo["actividad"], []).append(grupo)

	equipos_by_grupo: dict[str, list[dict[str, Any]]] = {}
	for equipo in equipos:
		equipos_by_grupo.setdefault(equipo["grupo_actividad"], []).append(equipo)

	catalog = []
	for actividad in actividades:
		act_row = _format_actividad_row(actividad)
		act_row["grupos"] = []
		actividad_item = actividad.get("item") or ""
		for grupo in grupos_by_actividad.get(actividad["name"], []):
			grupo_row = _format_grupo_row(grupo)
			grupo_item = grupo.get("item") or ""
			grupo_row["equipos"] = [
				_format_equipo_row(
					equipo,
					grupo_item=grupo_item,
					actividad_item=actividad_item,
				)
				for equipo in equipos_by_grupo.get(grupo["name"], [])
			]
			act_row["grupos"].append(grupo_row)
		catalog.append(act_row)

	return {"actividades": catalog}


def create_actividad(*, titulo: str, usa_grupos: int = 0) -> dict[str, str]:
	"""Crea una Actividad habilitada (nombre = titulo)."""
	title = (titulo or "").strip()
	if not title:
		frappe.throw(frappe._("Indique el nombre de la actividad."))
	if frappe.db.exists(ACTIVIDAD_DOCTYPE, title):
		frappe.throw(frappe._("Ya existe una actividad con el nombre {0}.").format(title))

	doc = frappe.get_doc(
		{
			"doctype": ACTIVIDAD_DOCTYPE,
			"titulo": title,
			"habilitada": 1,
			"usa_grupos": 1 if usa_grupos else 0,
		}
	)
	doc.insert()
	return {"name": doc.name, "titulo": doc.titulo}


def create_grupo(*, actividad: str, titulo: str) -> dict[str, str]:
	"""Crea un Grupo Actividad bajo la actividad indicada."""
	_ensure_actividad(actividad)
	title = (titulo or "").strip()
	if not title:
		frappe.throw(frappe._("Indique el nombre del grupo / tira."))

	doc = frappe.get_doc(
		{
			"doctype": GRUPO_DOCTYPE,
			"actividad": actividad,
			"titulo": title,
			"habilitada": 1,
		}
	)
	doc.insert()
	return {"name": doc.name, "titulo": doc.titulo}


def create_equipo(*, grupo_actividad: str, titulo: str) -> dict[str, str]:
	"""Crea un Equipo Actividad bajo el grupo indicado."""
	_ensure_grupo(grupo_actividad)
	title = (titulo or "").strip()
	if not title:
		frappe.throw(frappe._("Indique el nombre del equipo / categoría."))

	doc = frappe.get_doc(
		{
			"doctype": EQUIPO_DOCTYPE,
			"grupo_actividad": grupo_actividad,
			"titulo": title,
			"habilitada": 1,
		}
	)
	doc.insert()
	return {"name": doc.name, "titulo": doc.titulo}


def set_arancel(
	*,
	doctype: str,
	name: str,
	item: str | None = None,
	rate: float | int | str | None = None,
) -> dict[str, Any]:
	"""Actualiza ítem de arancel y tarifa estándar ERPNext."""
	if doctype not in ARANCEL_DOCTYPES:
		frappe.throw(frappe._("DocType no soportado para arancel."))
	if not frappe.db.exists(doctype, name):
		frappe.throw(frappe._("Documento no encontrado."), frappe.DoesNotExistError)

	previous_item = (frappe.db.get_value(doctype, name, "item") or "").strip()
	item_code = (item or "").strip() or previous_item
	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw(frappe._("Ítem ERPNext inválido."))

	if rate is None:
		rate_value = _resolve_item_rate(item_code)
	else:
		rate_value = flt(rate)
		if rate_value < 0:
			frappe.throw(frappe._("La tarifa no puede ser negativa."))
		if rate_value == 0 and item_code != previous_item:
			resolved = _resolve_item_rate(item_code)
			if resolved > 0:
				rate_value = resolved

	frappe.db.set_value(doctype, name, "item", item_code, update_modified=True)
	frappe.db.set_value("Item", item_code, "standard_rate", rate_value, update_modified=True)
	_upsert_item_selling_price(item_code, rate_value)

	return {
		"doctype": doctype,
		"name": name,
		"item": item_code,
		"rate": rate_value,
	}


def default_arancel_item_group() -> str:
	return (
		frappe.db.get_value("Item Group", {"name": "Ingresos por Actividades Deportivas"}, "name")
		or frappe.db.get_value("Item Group", {"name": ["like", "ICDPE / Aranceles%"]}, "name")
		or frappe.db.get_value("Item Group", {"name": ["like", "ICDPE%"]}, "name")
		or frappe.db.get_value("Item Group", {}, "name")
		or "All Item Groups"
	)


def _default_selling_price_list() -> str | None:
	return (
		frappe.get_single_value("Selling Settings", "selling_price_list")
		or frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
	)


def _upsert_item_selling_price(item_code: str, rate: float) -> None:
	"""Sincroniza `Item Price` en la lista de venta estándar (panel Secretaría)."""
	price_list = _default_selling_price_list()
	if not price_list:
		return

	existing = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list},
		"name",
	)
	if existing:
		frappe.db.set_value("Item Price", existing, "price_list_rate", rate, update_modified=True)
		return

	frappe.get_doc(
		{
			"doctype": "Item Price",
			"price_list": price_list,
			"item_code": item_code,
			"price_list_rate": rate,
		}
	).insert(ignore_permissions=True)


def create_arancel_item(
	*,
	item_code: str,
	item_name: str,
	standard_rate: float | int | str = 0,
) -> dict[str, Any]:
	"""Crea un Item de servicio ICDPE para aranceles desde el panel."""
	code = (item_code or "").strip()
	title = (item_name or code).strip()
	if not code:
		frappe.throw(frappe._("Indique el código del ítem."))
	if not title:
		frappe.throw(frappe._("Indique el nombre del ítem."))
	if frappe.db.exists("Item", code):
		frappe.throw(frappe._("Ya existe un ítem con el código {0}.").format(code))

	rate_value = flt(standard_rate)
	if rate_value < 0:
		frappe.throw(frappe._("La tarifa no puede ser negativa."))

	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": title,
			"item_group": default_arancel_item_group(),
			"is_stock_item": 0,
			"is_sales_item": 1,
			"stock_uom": "Servicio",
			"standard_rate": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("Item", code, "standard_rate", rate_value, update_modified=True)
	_upsert_item_selling_price(code, rate_value)
	return {"item": doc.name, "rate": rate_value}


def update_actividad(
	*,
	name: str,
	titulo: str | None = None,
	usa_grupos: int | None = None,
	habilitada: int | None = None,
	orden: int | None = None,
	descripcion: str | None = None,
) -> dict[str, Any]:
	"""Actualiza metadatos de una actividad desde el panel Desk."""
	_ensure_actividad(name)
	doc = frappe.get_doc(ACTIVIDAD_DOCTYPE, name)

	if usa_grupos is not None and doc.usa_grupos and not int(usa_grupos):
		if _count_inscripciones_activas({"actividad": name, "grupo_actividad": ["is", "set"]}):
			frappe.throw(
				frappe._(
					"No se puede desactivar grupos/tiras: hay inscripciones activas con grupo."
				)
			)

	if habilitada is not None and not int(habilitada):
		if _count_inscripciones_activas({"actividad": name}):
			frappe.throw(
				frappe._(
					"No se puede deshabilitar la actividad: hay inscripciones activas."
				)
			)

	if titulo is not None:
		new_title = (titulo or "").strip()
		if not new_title:
			frappe.throw(frappe._("Indique el nombre de la actividad."))
		if new_title != doc.titulo:
			frappe.rename_doc(ACTIVIDAD_DOCTYPE, doc.name, new_title, force=True)
			doc = frappe.get_doc(ACTIVIDAD_DOCTYPE, new_title)

	if usa_grupos is not None:
		doc.usa_grupos = 1 if int(usa_grupos) else 0
	if habilitada is not None:
		doc.habilitada = 1 if int(habilitada) else 0
	if orden is not None:
		doc.orden = int(orden)
	if descripcion is not None:
		doc.descripcion = descripcion

	doc.save(ignore_permissions=True)
	return {
		"name": doc.name,
		"titulo": doc.titulo,
		"usa_grupos": bool(doc.usa_grupos),
		"habilitada": bool(doc.habilitada),
		"orden": doc.orden,
		"descripcion": doc.descripcion or "",
	}


def update_grupo(
	*,
	name: str,
	titulo: str | None = None,
	orden: int | None = None,
	habilitada: int | None = None,
) -> dict[str, str]:
	"""Actualiza un Grupo Actividad; renombra si cambia el título."""
	_ensure_grupo(name)
	doc = frappe.get_doc(GRUPO_DOCTYPE, name)

	if habilitada is not None and not int(habilitada):
		if _count_inscripciones_activas({"grupo_actividad": name}):
			frappe.throw(
				frappe._("No se puede deshabilitar el grupo: hay inscripciones activas.")
			)

	if titulo is not None:
		new_title = (titulo or "").strip()
		if not new_title:
			frappe.throw(frappe._("Indique el nombre del grupo / tira."))
		doc.titulo = new_title

	if orden is not None:
		doc.orden = int(orden)
	if habilitada is not None:
		doc.habilitada = 1 if int(habilitada) else 0

	new_name = doc._build_name()
	if new_name != doc.name:
		doc.save(ignore_permissions=True)
		frappe.rename_doc(GRUPO_DOCTYPE, doc.name, new_name, force=True)
		doc = frappe.get_doc(GRUPO_DOCTYPE, new_name)
	else:
		doc.save(ignore_permissions=True)

	return {"name": doc.name, "titulo": doc.titulo}


def update_equipo(
	*,
	name: str,
	titulo: str | None = None,
	orden: int | None = None,
	habilitada: int | None = None,
) -> dict[str, str]:
	"""Actualiza un Equipo Actividad; renombra si cambia el título."""
	if not frappe.db.exists(EQUIPO_DOCTYPE, name):
		frappe.throw(frappe._("Equipo no encontrado."), frappe.DoesNotExistError)
	doc = frappe.get_doc(EQUIPO_DOCTYPE, name)

	if habilitada is not None and not int(habilitada):
		if _count_inscripciones_activas({"equipo_actividad": name}):
			frappe.throw(
				frappe._("No se puede deshabilitar el equipo: hay inscripciones activas.")
			)

	if titulo is not None:
		new_title = (titulo or "").strip()
		if not new_title:
			frappe.throw(frappe._("Indique el nombre del equipo / categoría."))
		doc.titulo = new_title

	if orden is not None:
		doc.orden = int(orden)
	if habilitada is not None:
		doc.habilitada = 1 if int(habilitada) else 0

	new_name = doc._build_name()
	if new_name != doc.name:
		doc.save(ignore_permissions=True)
		frappe.rename_doc(EQUIPO_DOCTYPE, doc.name, new_name, force=True)
		doc = frappe.get_doc(EQUIPO_DOCTYPE, new_name)
	else:
		doc.save(ignore_permissions=True)

	return {"name": doc.name, "titulo": doc.titulo}


def _format_actividad_row(row: dict[str, Any]) -> dict[str, Any]:
	item = row.get("item") or ""
	return {
		"name": row["name"],
		"titulo": row.get("titulo") or row["name"],
		"usa_grupos": bool(row.get("usa_grupos")),
		"orden": row.get("orden") or 0,
		"descripcion": row.get("descripcion") or "",
		"item": item,
		"rate": _resolve_item_rate(item),
	}


def _format_grupo_row(row: dict[str, Any]) -> dict[str, Any]:
	item = row.get("item") or ""
	return {
		"name": row["name"],
		"titulo": row.get("titulo") or row["name"],
		"actividad": row.get("actividad"),
		"item": item,
		"rate": _resolve_item_rate(item),
	}


def _format_equipo_row(
	row: dict[str, Any],
	*,
	grupo_item: str = "",
	actividad_item: str = "",
) -> dict[str, Any]:
	item = row.get("item") or ""
	arancel = resolve_arancel_efectivo_from_chain(
		equipo_item=item,
		grupo_item=grupo_item,
		actividad_item=actividad_item,
	)
	return {
		"name": row["name"],
		"titulo": row.get("titulo") or row["name"],
		"grupo_actividad": row.get("grupo_actividad"),
		"item": item,
		"rate": _resolve_item_rate(item),
		"arancel": arancel,
	}


def _arancel_payload(item_code: str, origen: str) -> dict[str, Any]:
	code = (item_code or "").strip()
	if not code:
		return {"item": "", "item_name": "", "rate": 0.0, "origen": "Sin arancel"}
	item_name = frappe.db.get_value("Item", code, "item_name") or code
	return {
		"item": code,
		"item_name": item_name,
		"rate": _resolve_item_rate(code),
		"origen": origen,
	}


def resolve_arancel_efectivo_from_chain(
	*,
	equipo_item: str | None = None,
	grupo_item: str | None = None,
	actividad_item: str | None = None,
) -> dict[str, Any]:
	"""Cascada de cobro: equipo → grupo → actividad."""
	if (equipo_item or "").strip():
		return _arancel_payload(equipo_item or "", "Equipo")
	if (grupo_item or "").strip():
		return _arancel_payload(grupo_item or "", "Grupo")
	if (actividad_item or "").strip():
		return _arancel_payload(actividad_item or "", "Actividad")
	return {"item": "", "item_name": "", "rate": 0.0, "origen": "Sin arancel"}


def resolve_arancel_efectivo_equipo(equipo_name: str) -> dict[str, Any]:
	"""Arancel efectivo de cobro para un Equipo Actividad (cascada)."""
	name = (equipo_name or "").strip()
	if not name or not frappe.db.exists(EQUIPO_DOCTYPE, name):
		frappe.throw(frappe._("Equipo no encontrado."), frappe.DoesNotExistError)

	equipo = frappe.db.get_value(
		EQUIPO_DOCTYPE,
		name,
		["item", "grupo_actividad"],
		as_dict=True,
	)
	grupo_item = ""
	actividad_item = ""
	grupo_name = (equipo.grupo_actividad or "").strip() if equipo else ""
	if grupo_name and frappe.db.exists(GRUPO_DOCTYPE, grupo_name):
		grupo = frappe.db.get_value(
			GRUPO_DOCTYPE,
			grupo_name,
			["item", "actividad"],
			as_dict=True,
		)
		grupo_item = (grupo.item or "") if grupo else ""
		actividad_name = (grupo.actividad or "").strip() if grupo else ""
		if actividad_name and frappe.db.exists(ACTIVIDAD_DOCTYPE, actividad_name):
			actividad_item = frappe.db.get_value(ACTIVIDAD_DOCTYPE, actividad_name, "item") or ""

	return resolve_arancel_efectivo_from_chain(
		equipo_item=(equipo.item or "") if equipo else "",
		grupo_item=grupo_item,
		actividad_item=actividad_item,
	)


def _resolve_item_rate(item_code: str) -> float:
	if not item_code or not frappe.db.exists("Item", item_code):
		return 0.0
	return flt(frappe.db.get_value("Item", item_code, "standard_rate"))


def resolve_item_arancel_rate(item_code: str) -> float:
	"""Tarifa estándar del ítem ERP para el panel de actividades."""
	return _resolve_item_rate((item_code or "").strip())


def _ensure_actividad(name: str) -> None:
	if not frappe.db.exists(ACTIVIDAD_DOCTYPE, name):
		frappe.throw(frappe._("Actividad no encontrada."), frappe.DoesNotExistError)


def _ensure_grupo(name: str) -> None:
	if not frappe.db.exists(GRUPO_DOCTYPE, name):
		frappe.throw(frappe._("Grupo no encontrado."), frappe.DoesNotExistError)


def _count_inscripciones_activas(filters: dict[str, Any]) -> int:
	return frappe.db.count(INSCRIPCION_DOCTYPE, {**filters, "estado": "Activa"})

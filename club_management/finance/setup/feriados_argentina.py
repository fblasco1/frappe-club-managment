"""Feriados nacionales de Argentina (Ley 27.399) para la Holiday List.

Incluye feriados inamovibles, trasladables (con la fecha efectiva del año) y
los días no laborables con fines turísticos. **No** incluye los días no
laborables de colectividades (judía, islámica, armenia), que no forman parte
del calendario de feriados nacionales.

Fuente: https://www.argentina.gob.ar/feriados y Resolución 164/2025 (puentes
turísticos 2026: 23/03, 10/07 y 07/12).
"""

from __future__ import annotations

import frappe

HOLIDAY_LIST_PREFIX = "Feriados Argentina"

# Año -> tupla de (fecha ISO, descripción). Las fechas trasladables ya están
# resueltas a la fecha efectiva del año correspondiente.
FERIADOS_POR_ANIO: dict[int, tuple[tuple[str, str], ...]] = {
	2026: (
		("2026-01-01", "Año Nuevo"),
		("2026-02-16", "Carnaval"),
		("2026-02-17", "Carnaval"),
		("2026-03-23", "Día no laborable con fines turísticos"),
		("2026-03-24", "Día Nacional de la Memoria por la Verdad y la Justicia"),
		("2026-04-02", "Día del Veterano y de los Caídos en la Guerra de Malvinas"),
		("2026-04-03", "Viernes Santo"),
		("2026-05-01", "Día del Trabajador"),
		("2026-05-25", "Día de la Revolución de Mayo"),
		("2026-06-15", "Paso a la Inmortalidad del Gral. Martín Miguel de Güemes"),
		("2026-06-20", "Paso a la Inmortalidad del Gral. Manuel Belgrano"),
		("2026-07-09", "Día de la Independencia"),
		("2026-07-10", "Día no laborable con fines turísticos"),
		("2026-08-17", "Paso a la Inmortalidad del Gral. José de San Martín"),
		("2026-10-12", "Día del Respeto a la Diversidad Cultural"),
		("2026-11-23", "Día de la Soberanía Nacional"),
		("2026-12-07", "Día no laborable con fines turísticos"),
		("2026-12-08", "Inmaculada Concepción de María"),
		("2026-12-25", "Navidad"),
	),
}


def holiday_list_name(anio: int) -> str:
	return f"{HOLIDAY_LIST_PREFIX} {anio}"


def ensure_holiday_list_argentina(anio: int = 2026, set_as_default: bool = True) -> str:
	"""Crea (idempotente) la Holiday List AR del año y la asigna como default.

	Devuelve el nombre de la Holiday List.
	"""
	feriados = FERIADOS_POR_ANIO.get(anio)
	if not feriados:
		frappe.throw(f"No hay feriados cargados para el año {anio}")

	name = holiday_list_name(anio)
	if frappe.db.exists("Holiday List", name):
		_sync_holidays(name, feriados)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": name,
				"from_date": f"{anio}-01-01",
				"to_date": f"{anio}-12-31",
				"holidays": [
					{"holiday_date": fecha, "description": desc} for fecha, desc in feriados
				],
			}
		)
		doc.insert(ignore_permissions=True)

	if set_as_default:
		_assign_default_holiday_list(name)
	return name


def _sync_holidays(name: str, feriados: tuple[tuple[str, str], ...]) -> None:
	"""Agrega feriados faltantes a una lista existente (no borra los cargados a mano)."""
	doc = frappe.get_doc("Holiday List", name)
	existentes = {str(h.holiday_date) for h in doc.holidays}
	changed = False
	for fecha, desc in feriados:
		if fecha not in existentes:
			doc.append("holidays", {"holiday_date": fecha, "description": desc})
			changed = True
	if changed:
		doc.save(ignore_permissions=True)


def _assign_default_holiday_list(name: str) -> None:
	"""Asigna la lista como `default_holiday_list` de las empresas de Argentina.

	Solo pisa el valor si la empresa no tiene lista o si tenía una lista creada
	por este mismo setup (prefijo `Feriados Argentina`), para no sobrescribir una
	elección manual del administrador.
	"""
	companies = frappe.get_all("Company", filters={"country": "Argentina"}, pluck="name")
	for company in companies:
		actual = frappe.db.get_value("Company", company, "default_holiday_list")
		if not actual or str(actual).startswith(HOLIDAY_LIST_PREFIX):
			frappe.db.set_value("Company", company, "default_holiday_list", name)

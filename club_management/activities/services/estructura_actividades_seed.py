"""Carga idempotente de actividades, grupos y equipos."""

from __future__ import annotations

import frappe

from club_management.activities.data.estructura_actividades_club import (
	CATEGORIAS_EQUIPO,
	ESTRUCTURA_CON_GRUPOS,
	EquipoSeed,
	GrupoSeed,
)
from club_management.activities.services.actividades_icdpe_catalog import (
	_resolve_actividad_docname,
	disable_legacy_basquet_actividades,
	resolve_item_name,
	sync_actividades_catalogo_icdpe,
)


def _actividad_docname(titulo: str) -> str | None:
	return _resolve_actividad_docname(titulo) or titulo


def upsert_grupo_actividad(
	actividad_titulo: str,
	grupo: GrupoSeed,
) -> str:
	actividad = _actividad_docname(actividad_titulo)
	if not actividad or not frappe.db.exists("Actividad", actividad):
		frappe.throw(f"Actividad inexistente: {actividad_titulo}")

	name = f"{actividad} / {grupo.titulo}"
	# Si el grupo declara item_code, es la fuente de cobro (aunque existan equipos).
	# Basquet no setea item_code → Grupo.item queda vacío y cobra por equipo.
	item_link = resolve_item_name(grupo.item_code) if grupo.item_code else None

	payload: dict = {
		"actividad": actividad,
		"titulo": grupo.titulo,
		"orden": grupo.orden,
		"habilitada": 1,
		"item": item_link,
		"condicion_socio": grupo.condicion_socio or "",
	}

	if frappe.db.exists("Grupo Actividad", name):
		for key, value in payload.items():
			frappe.db.set_value("Grupo Actividad", name, key, value, update_modified=False)
		frappe.db.set_value("Grupo Actividad", name, "modified", frappe.utils.now(), update_modified=True)
		return name

	doc = frappe.get_doc({"doctype": "Grupo Actividad", "name": name, **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def upsert_equipo_actividad(
	grupo_name: str,
	titulo: str,
	orden: int,
	*,
	item_code: str | None = None,
	descripcion: str = "",
) -> str:
	if not frappe.db.exists("Grupo Actividad", grupo_name):
		frappe.throw(f"Grupo inexistente: {grupo_name}")

	name = f"{grupo_name} / {titulo}"
	item_link = resolve_item_name(item_code) if item_code else None
	payload = {
		"grupo_actividad": grupo_name,
		"titulo": titulo,
		"orden": orden,
		"habilitada": 1,
		"descripcion": descripcion or None,
		"item": item_link,
	}
	if frappe.db.exists("Equipo Actividad", name):
		for key, value in payload.items():
			frappe.db.set_value("Equipo Actividad", name, key, value, update_modified=False)
		return name

	doc = frappe.get_doc({"doctype": "Equipo Actividad", "name": name, **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def _disable_equipos_no_seed(grupo_name: str, expected_titles: set[str]) -> None:
	for row in frappe.get_all(
		"Equipo Actividad",
		filters={"grupo_actividad": grupo_name, "habilitada": 1},
		fields=["name", "titulo"],
	):
		if (row.titulo or "") not in expected_titles:
			frappe.db.set_value("Equipo Actividad", row.name, "habilitada", 0, update_modified=True)


def _seed_equipos_grupo(grupo_name: str, grupo: GrupoSeed) -> int:
	count = 0
	if grupo.equipos:
		expected = {eq.titulo for eq in grupo.equipos}
		for eq in grupo.equipos:
			upsert_equipo_actividad(
				grupo_name,
				eq.titulo,
				eq.orden,
				item_code=eq.item_code,
				descripcion=eq.descripcion,
			)
			count += 1
		_disable_equipos_no_seed(grupo_name, expected)
		return count

	for idx, categoria in enumerate(CATEGORIAS_EQUIPO):
		upsert_equipo_actividad(grupo_name, categoria, (idx + 1) * 10)
		count += 1
	return count


def seed_estructura_actividades_completa(*, crear_equipos: bool = True) -> dict[str, int]:
	"""Sincroniza catálogo ICDPE + grupos + equipos. Devuelve conteos."""
	from club_management.activities.data.futbol_aranceles_icdpe import FUTBOL_ITEM_SPECS
	from club_management.activities.data.otras_actividades_aranceles_icdpe import (
		OTRAS_ACTIVIDADES_ITEM_SPECS,
	)
	from club_management.activities.data.patin_aranceles_icdpe import PATIN_ITEM_SPECS
	from club_management.activities.data.voley_aranceles_icdpe import VOLEY_ITEM_SPECS
	from club_management.activities.services.deporte_icdpe_items import sync_arancel_items

	sync_actividades_catalogo_icdpe(deshabilitar_legacy=True)
	# Asegura ítems antes de linkear Grupo/Equipo.item (cobro por tira).
	sync_arancel_items(VOLEY_ITEM_SPECS)
	sync_arancel_items(FUTBOL_ITEM_SPECS)
	sync_arancel_items(PATIN_ITEM_SPECS)
	sync_arancel_items(OTRAS_ACTIVIDADES_ITEM_SPECS)

	grupos_creados = 0
	equipos_creados = 0

	for estructura in ESTRUCTURA_CON_GRUPOS:
		actividad = _actividad_docname(estructura.actividad)
		if not actividad:
			continue
		frappe.db.set_value("Actividad", actividad, "usa_grupos", 1, update_modified=False)
		admite_no_socios = int(any(g.condicion_socio == "No Socio" for g in estructura.grupos))
		frappe.db.set_value(
			"Actividad", actividad, "admite_no_socios", admite_no_socios, update_modified=False
		)
		expected_grupos = {g.titulo for g in estructura.grupos}

		for grupo_seed in estructura.grupos:
			grupo_name = upsert_grupo_actividad(estructura.actividad, grupo_seed)
			grupos_creados += 1

			if not crear_equipos:
				continue
			equipos_creados += _seed_equipos_grupo(grupo_name, grupo_seed)

		for row in frappe.get_all(
			"Grupo Actividad",
			filters={"actividad": actividad, "habilitada": 1},
			fields=["name", "titulo"],
		):
			if (row.titulo or "") not in expected_grupos:
				frappe.db.set_value("Grupo Actividad", row.name, "habilitada", 0, update_modified=True)

	actividades_habilitadas = frappe.db.count("Actividad", {"habilitada": 1})
	disable_legacy_basquet_actividades()
	cto_comp = seed_cuota_complementaria_tarifas()
	return {
		"actividades": actividades_habilitadas,
		"grupos": grupos_creados,
		"equipos": equipos_creados,
		"cto_comp": cto_comp,
	}


# (actividad_titulo, grupo_titulo) → (monto, concepto CTO COMP canónico)
# Montos vigentes según cargos/informe prod (nov 2026).
CTO_COMP_TARIFAS_POR_GRUPO: dict[tuple[str, str], tuple[float, str]] = {
	("Basquet", "Masculino / Azul"): (7000.0, "CTO COMP BASQ TIRA A/B/FLEX"),
	("Basquet", "Masculino / Amarillo"): (7000.0, "CTO COMP BASQ TIRA A/B/FLEX"),
	("Basquet", "Masculino / Flex"): (7000.0, "CTO COMP BASQ TIRA A/B/FLEX"),
	("Basquet", "Femenino / Formativa"): (6000.0, "CTO COMP BASQ ESC/FEM"),
	("Basquet", "Femenino / Superior"): (6000.0, "CTO COMP BASQ ESC/FEM"),
	("Basquet", "Mixto / Escuela"): (6000.0, "CTO COMP BASQ ESC/FEM"),
	("Futbol", "FAFI"): (8400.0, "CTO COMP FUTBOL FAFI/TABI"),
	("Futbol", "TABI A"): (8400.0, "CTO COMP FUTBOL FAFI/TABI"),
	("Futbol", "TABI B"): (7400.0, "CTO COMP FUTBOL ESC"),
	("Voley Femenino", "Tira"): (6100.0, "CTO COMP VOLEY"),
	("Voley Femenino", "Escuela Adolescente"): (4300.0, "CTO COMP VOLEY ESC"),
	("Voley Femenino", "Escuelita Minivoley"): (4300.0, "CTO COMP VOLEY ESC"),
	("Voley Femenino", "escuelita"): (4300.0, "CTO COMP VOLEY ESC"),
	("Patin Artistico", "Patin Avanzado"): (2520.0, "CTO COMP PATIN AVANZADO"),
	("Patin Artistico", "Patin Intermedio"): (2160.0, "CTO COMP PATIN INTERMEDIO"),
	("Patin Artistico", "Patin Mini"): (1230.0, "CTO COMP PATIN INICIAL"),
	("Patin Artistico", "Patin Teens"): (1230.0, "CTO COMP PATIN INICIAL"),
	("Patin Artistico", "Patin Danza"): (1230.0, "CTO COMP PATIN INICIAL"),
	("Patin Artistico", "Adulto"): (1590.0, "CTO COMP PATIN ADULTOS"),
}


def _tarifa_cto_comp_basquet_grupo(titulo: str) -> float | None:
	"""Compat: ESC/FEM → 6000; Masculino → 7000."""
	key = ("Basquet", (titulo or "").strip())
	row = CTO_COMP_TARIFAS_POR_GRUPO.get(key)
	return row[0] if row else None


def seed_basquet_cuota_complementaria_tarifas() -> dict[str, int]:
	"""Compat: solo Basquet. Preferir `seed_cuota_complementaria_tarifas`."""
	return seed_cuota_complementaria_tarifas(solo_actividad="Basquet")


def seed_cuota_complementaria_tarifas(*, solo_actividad: str | None = None) -> dict[str, int]:
	"""Enlaza monto + título CTO COMP a cada grupo de deporte con concepto conocido."""
	updated = 0
	por_actividad: dict[str, int] = {}

	for (act_titulo, grupo_titulo), (monto, concepto) in CTO_COMP_TARIFAS_POR_GRUPO.items():
		if solo_actividad and act_titulo != solo_actividad:
			continue
		actividad = _actividad_docname(act_titulo)
		if not actividad or not frappe.db.exists("Actividad", actividad):
			continue
		grupo_name = frappe.db.get_value(
			"Grupo Actividad",
			{"actividad": actividad, "titulo": grupo_titulo, "habilitada": 1},
			"name",
		)
		if not grupo_name:
			# Match case-insensitive for legacy titles (p. ej. «escuelita»).
			for row in frappe.get_all(
				"Grupo Actividad",
				filters={"actividad": actividad, "habilitada": 1},
				fields=["name", "titulo"],
			):
				if (row.titulo or "").strip().casefold() == grupo_titulo.casefold():
					grupo_name = row.name
					break
		if not grupo_name:
			continue
		frappe.db.set_value(
			"Grupo Actividad",
			grupo_name,
			{
				"monto_cuota_complementaria": monto,
				"titulo_cuota_complementaria": concepto,
			},
			update_modified=True,
		)
		updated += 1
		por_actividad[act_titulo] = por_actividad.get(act_titulo, 0) + 1

	return {"grupos_actualizados": updated, "por_actividad": por_actividad}

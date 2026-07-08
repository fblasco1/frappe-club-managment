"""Vinculación de socios al roster de básquet por DNI (categoría + equipo)."""

from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frappe
from frappe import _

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	_format_inscripcion_label,
	inscribir_socio_selecciones,
	sync_socio_actividad_resumen,
	_resolve_equipo_actividad,
	_resolve_grupo_actividad,
)
from club_management.activities.services.actividades_catalog import ensure_actividad_exists

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
VALID_CATEGORIAS = frozenset({"U7", "U9", "U11", "U13", "U15", "U17", "U21", "MAYOR"})
VALID_EQUIPOS = frozenset(
	{"Azul", "Amarillo", "Flex", "Femenino", "Escuelita", "MAYOR"}
)
from club_management.activities.services.basquet_unified_map import (
	basquet_actividad_docnames,
	map_roster_basquet_seleccion,
)


LOG_NO_PADRON_SIN_DNI = "JUGADORES QUE NO ESTAN EN EL PADRON y NO TIENEN DNI EN EL CSV.csv"
LOG_NO_PADRON_CON_DNI = "JUGADORES QUE NO ESTAN EN EL PADRON y TIENEN DNI EN EL CSV.csv"
LOG_YA_INSCRIPTOS = "JUGADORES QUE YA TENIAN INSCRIPCION CARGADA.csv"
LOG_ROW_FIELDS = (
	"numero",
	"dni",
	"nombre",
	"categoria",
	"equipo",
	"socio",
	"inscripcion_existente",
	"detalle",
)


@dataclass
class RosterImportJugadoresResult:
	total_filas: int = 0
	inscripciones_nuevas: int = 0
	ya_inscriptos: int = 0
	no_padron_sin_dni: int = 0
	no_padron_con_dni: int = 0
	omitidos_duplicado_csv: int = 0
	errores: list[str] = field(default_factory=list)
	log_no_padron_sin_dni: list[dict[str, str]] = field(default_factory=list)
	log_no_padron_con_dni: list[dict[str, str]] = field(default_factory=list)
	log_ya_inscriptos: list[dict[str, str]] = field(default_factory=list)
	log_paths: dict[str, str] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"inscripciones_nuevas": self.inscripciones_nuevas,
			"ya_inscriptos": self.ya_inscriptos,
			"no_padron_sin_dni": self.no_padron_sin_dni,
			"no_padron_con_dni": self.no_padron_con_dni,
			"omitidos_duplicado_csv": self.omitidos_duplicado_csv,
			"errores": self.errores,
			"log_paths": self.log_paths,
		}


LOG_NO_PADRON_SIN_DNI = "JUGADORES QUE NO ESTAN EN EL PADRON y NO TIENEN DNI EN EL CSV.csv"
LOG_NO_PADRON_CON_DNI = "JUGADORES QUE NO ESTAN EN EL PADRON y TIENEN DNI EN EL CSV.csv"
LOG_YA_INSCRIPTOS = "JUGADORES QUE YA TENIAN INSCRIPCION CARGADA.csv"
LOG_ROW_FIELDS = (
	"numero",
	"dni",
	"nombre",
	"categoria",
	"equipo",
	"socio",
	"inscripcion_existente",
	"detalle",
)


@dataclass
class RosterImportJugadoresResult:
	total_filas: int = 0
	inscripciones_nuevas: int = 0
	ya_inscriptos: int = 0
	no_padron_sin_dni: int = 0
	no_padron_con_dni: int = 0
	omitidos_duplicado_csv: int = 0
	errores: list[str] = field(default_factory=list)
	log_no_padron_sin_dni: list[dict[str, str]] = field(default_factory=list)
	log_no_padron_con_dni: list[dict[str, str]] = field(default_factory=list)
	log_ya_inscriptos: list[dict[str, str]] = field(default_factory=list)
	log_paths: dict[str, str] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"inscripciones_nuevas": self.inscripciones_nuevas,
			"ya_inscriptos": self.ya_inscriptos,
			"no_padron_sin_dni": self.no_padron_sin_dni,
			"no_padron_con_dni": self.no_padron_con_dni,
			"omitidos_duplicado_csv": self.omitidos_duplicado_csv,
			"errores": self.errores,
			"log_paths": self.log_paths,
		}


@dataclass
class RosterLinkStats:
	total_filas: int = 0
	vinculados: int = 0
	omitidos: int = 0
	socios_no_encontrados: int = 0
	errores: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"vinculados": self.vinculados,
			"omitidos": self.omitidos,
			"socios_no_encontrados": self.socios_no_encontrados,
			"errores": self.errores,
		}


def normalize_roster_dni(raw: str | float | int | None) -> str:
	if raw in (None, ""):
		return ""
	text = str(raw).strip()
	if "E" in text.upper():
		try:
			text = str(int(float(text)))
		except ValueError:
			pass
	digits = re.sub(r"\D", "", text)
	if not (7 <= len(digits) <= 8):
		return ""
	return digits


def normalize_roster_nombre(value: str | None) -> str:
	return re.sub(r"\s+", " ", (value or "").strip()).upper()


def _log_row(**kwargs: str) -> dict[str, str]:
	return {field: kwargs.get(field, "") for field in LOG_ROW_FIELDS}


def _is_person_name(value: str | None) -> bool:
	text = (value or "").strip()
	if not text or re.fullmatch(r"20\d{2}\.0", text):
		return False
	if normalize_roster_dni(text):
		return False
	upper = text.upper()
	if upper in VALID_CATEGORIAS or text.title() in VALID_EQUIPOS:
		return False
	return "," in text or (len(text.split()) >= 2 and any(char.isalpha() for char in text))


def map_basquet_seleccion(categoria: str, equipo: str) -> dict[str, str]:
	"""Mapea categoría/equipo del roster a actividad, grupo y equipo ICDPE."""
	cat = (categoria or "").strip().upper()
	eq = (equipo or "").strip().title()
	if eq == "Mayor":
		eq = "MAYOR"
	if cat not in VALID_CATEGORIAS:
		frappe.throw(_("Categoría de básquet no reconocida: {0}").format(categoria))
	try:
		return map_roster_basquet_seleccion(cat, eq)
	except ValueError:
		frappe.throw(_("Equipo de básquet no reconocido para {0} / {1}").format(cat, equipo))


def resolve_seleccion_basquet(seleccion: dict[str, str]) -> dict[str, str | None]:
	actividad_name = ensure_actividad_exists(seleccion["actividad"])
	if not actividad_name:
		frappe.throw(_("Actividad no encontrada: {0}").format(seleccion["actividad"]))
	grupo_name = _resolve_grupo_actividad(actividad_name, seleccion.get("grupo"))
	if not grupo_name:
		frappe.throw(_("Grupo no encontrado: {0}").format(seleccion.get("grupo")))
	equipo_name = _resolve_equipo_actividad(grupo_name, seleccion.get("equipo"))
	if not equipo_name:
		frappe.throw(_("Equipo no encontrado: {0}").format(seleccion.get("equipo")))
	return {
		"actividad": actividad_name,
		"grupo_actividad": grupo_name,
		"equipo_actividad": equipo_name,
	}


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
	root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
	strings: list[str] = []
	for item in root.findall(f".//{NS}si"):
		strings.append("".join((node.text or "") for node in item.findall(f".//{NS}t")))
	return strings


def _read_worksheet(zf: zipfile.ZipFile, sheet_path: str, strings: list[str]) -> list[list[str]]:
	root = ET.fromstring(zf.read(sheet_path))
	rows: list[list[str]] = []
	for row in root.findall(f".//{NS}row"):
		cells: list[str] = []
		for cell in row.findall(NS + "c"):
			cell_type = cell.attrib.get("t")
			value_node = cell.find(NS + "v")
			if value_node is None:
				cells.append("")
			elif cell_type == "s":
				cells.append(strings[int(value_node.text)])
			else:
				cells.append(value_node.text or "")
		rows.append(cells)
	return rows


def _parse_roster_row(cells: list[Any]) -> dict[str, str] | None:
	texts = [str(cell).strip() if cell not in (None, "") else "" for cell in cells]
	if any(text == "DNI" for text in texts[:3]):
		return None

	categoria = equipo = ""
	for text in reversed(texts):
		upper = text.upper()
		if upper in VALID_CATEGORIAS and not categoria:
			categoria = upper
		elif text.title() in VALID_EQUIPOS and not equipo:
			equipo = text.title() if text.title() != "Mayor" else "MAYOR"
	if not categoria:
		return None

	dni = ""
	nombre = ""
	for text in texts:
		normalized_dni = normalize_roster_dni(text)
		if normalized_dni and not dni:
			dni = normalized_dni
		elif _is_person_name(text) and not nombre:
			nombre = text

	return {
		"dni": dni,
		"nombre": nombre,
		"categoria": categoria,
		"equipo": equipo,
	}


def _name_to_dni_map(rows: list[list[str]]) -> dict[str, str]:
	mapping: dict[str, str] = {}
	for cells in rows[1:]:
		if len(cells) < 2:
			continue
		dni = normalize_roster_dni(cells[0])
		nombre = str(cells[1] or "").strip().upper()
		if dni and nombre:
			mapping[nombre] = dni
	return mapping


def parse_jugadores_xlsx(xlsx_path: str) -> list[dict[str, str]]:
	path = Path(xlsx_path)
	if not path.is_file():
		frappe.throw(_("Archivo no encontrado: {0}").format(xlsx_path))

	players: list[dict[str, str]] = []
	with zipfile.ZipFile(path) as zf:
		strings = _load_shared_strings(zf)
		name_map = _name_to_dni_map(_read_worksheet(zf, "xl/worksheets/sheet4.xml", strings))
		for cells in _read_worksheet(zf, "xl/worksheets/sheet3.xml", strings):
			parsed = _parse_roster_row(cells)
			if not parsed:
				continue
			if not parsed["dni"] and parsed["nombre"]:
				parsed["dni"] = name_map.get(parsed["nombre"].upper(), "")
			if not parsed["dni"]:
				continue
			if not parsed["equipo"]:
				continue
			players.append(parsed)
	return players


def parse_jugadores_csv_rows(csv_path: str) -> list[dict[str, str]]:
	"""Parsea todas las filas válidas del CSV Jugadorxs (DNI opcional)."""
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw(_("Archivo no encontrado: {0}").format(csv_path))

	players: list[dict[str, str]] = []
	with path.open(encoding="utf-8-sig", newline="") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			dni = normalize_roster_dni(
				row.get("dni") or row.get("DNI") or row.get("doc_identidad") or ""
			)
			categoria = (row.get("categoria") or row.get("Categoria 2026") or "").strip().upper()
			equipo = (row.get("equipo") or row.get("Equipo 2026") or "").strip().title()
			if equipo == "Mayor":
				equipo = "MAYOR"
			nombre = (row.get("nombre") or row.get("Nombre y Apellido") or "").strip()
			if categoria not in VALID_CATEGORIAS or not equipo:
				continue
			players.append(
				{
					"numero": (row.get("Numero") or row.get("numero") or "").strip(),
					"dni": dni,
					"nombre": nombre,
					"categoria": categoria,
					"equipo": equipo,
				}
			)
	return players


def parse_jugadores_csv(csv_path: str) -> list[dict[str, str]]:
	return [row for row in parse_jugadores_csv_rows(csv_path) if row.get("dni")]


def _find_socio_by_dni(dni: str) -> str | None:
	normalized = normalize_roster_dni(dni)
	if not normalized:
		return None
	for candidate in {normalized, normalized.lstrip("0")}:
		name = frappe.db.get_value("Socio", {"dni": candidate}, "name")
		if name:
			return name
	rows = frappe.get_all("Socio", filters={"dni": ["like", f"%{normalized[-8:]}"]}, fields=["name", "dni"])
	for row in rows:
		if normalize_roster_dni(row.dni) == normalized:
			return row.name
	return None


def _build_socio_lookup_maps() -> tuple[dict[str, str], dict[str, str]]:
	dni_map: dict[str, str] = {}
	nombre_map: dict[str, str] = {}
	for row in frappe.get_all(
		"Socio",
		fields=["name", "dni", "nombre_completo", "apellido", "nombre"],
	):
		socio_name = row.name
		normalized_dni = normalize_roster_dni(row.dni)
		if normalized_dni:
			for candidate in {normalized_dni, normalized_dni.lstrip("0")}:
				dni_map.setdefault(candidate, socio_name)
		label = (row.nombre_completo or "").strip()
		if not label:
			from club_management.members.doctype.socio.socio import format_socio_nombre_completo

			label = format_socio_nombre_completo(row.apellido, row.nombre)
		nombre_key = normalize_roster_nombre(label)
		if nombre_key:
			nombre_map.setdefault(nombre_key, socio_name)
	return dni_map, nombre_map


def _find_socio_by_nombre(
	nombre: str,
	*,
	nombre_map: dict[str, str] | None = None,
) -> str | None:
	key = normalize_roster_nombre(nombre)
	if not key:
		return None
	if nombre_map is None:
		_, nombre_map = _build_socio_lookup_maps()
	return nombre_map.get(key)


def _find_socio_roster(
	row: dict[str, str],
	*,
	dni_map: dict[str, str],
	nombre_map: dict[str, str],
) -> str | None:
	dni = row.get("dni") or ""
	if dni:
		for candidate in {dni, dni.lstrip("0")}:
			if candidate in dni_map:
				return dni_map[candidate]
	nombre = row.get("nombre") or ""
	if nombre:
		return _find_socio_by_nombre(nombre, nombre_map=nombre_map)
	return None


def _inscripcion_basquet_activa(socio_name: str) -> dict[str, str] | None:
	actividad_names = basquet_actividad_docnames()
	if not actividad_names:
		return None
	row = frappe.db.get_value(
		INSCRIPCION_DOCTYPE,
		{
			"socio": socio_name,
			"estado": "Activa",
			"actividad": ["in", actividad_names],
		},
		["name", "actividad", "grupo_actividad", "equipo_actividad"],
		as_dict=True,
	)
	if not row:
		return None
	return {
		"name": row.name,
		"label": _format_inscripcion_label(
			{
				"actividad": row.actividad,
				"grupo_actividad": row.grupo_actividad,
				"equipo_actividad": row.equipo_actividad,
			}
		),
	}


def _write_roster_log_csv(output_dir: Path, filename: str, rows: list[dict[str, str]]) -> str:
	output_dir.mkdir(parents=True, exist_ok=True)
	path = output_dir / filename
	with path.open("w", encoding="utf-8-sig", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=LOG_ROW_FIELDS, extrasaction="ignore")
		writer.writeheader()
		writer.writerows(rows)
	return str(path)


def _baja_inscripciones_basquet(socio_name: str) -> None:
	from club_management.members.services.suscripciones_socio import cancel_arancel_inscripcion

	actividad_names = basquet_actividad_docnames()
	if not actividad_names:
		return

	for inscripcion_name in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": socio_name, "estado": "Activa", "actividad": ["in", actividad_names]},
		pluck="name",
	):
		doc = frappe.get_doc(INSCRIPCION_DOCTYPE, inscripcion_name)
		doc.estado = "Baja"
		doc.save(ignore_permissions=True)
		cancel_arancel_inscripcion(inscripcion_name)


def vincular_basquet_socio(
	socio_name: str,
	*,
	categoria: str,
	equipo: str,
	dry_run: bool = True,
	reemplazar_inscripciones: bool = True,
) -> dict[str, Any]:
	seleccion = map_basquet_seleccion(categoria, equipo)
	resolved = resolve_seleccion_basquet(seleccion)
	label = _format_inscripcion_label(
		{
			"actividad": resolved["actividad"],
			"grupo_actividad": resolved["grupo_actividad"],
			"equipo_actividad": resolved["equipo_actividad"],
		}
	)
	if dry_run:
		return {
			"status": "dry_run",
			"socio": socio_name,
			"seleccion": seleccion,
			"equipo_actividad": resolved["equipo_actividad"],
			"label": label,
		}

	if reemplazar_inscripciones:
		_baja_inscripciones_basquet(socio_name)
	inscribir_socio_selecciones(
		socio_name,
		[
			{
				"actividad": seleccion["actividad"],
				"grupo": seleccion["grupo"],
				"equipo": seleccion["equipo"],
			}
		],
		activar=False,
	)
	sync_socio_actividad_resumen(socio_name)
	return {
		"status": "ok",
		"socio": socio_name,
		"equipo_actividad": resolved["equipo_actividad"],
		"label": label,
	}


def vincular_roster_basquet(
	*,
	source_path: str,
	dry_run: bool = True,
) -> dict[str, Any]:
	path = Path(source_path)
	if path.suffix.lower() == ".csv":
		rows = parse_jugadores_csv(source_path)
	else:
		rows = parse_jugadores_xlsx(source_path)

	stats = RosterLinkStats(total_filas=len(rows))
	seen_dnis: set[str] = set()

	for row in rows:
		dni = row["dni"]
		if dni in seen_dnis:
			stats.omitidos += 1
			continue
		seen_dnis.add(dni)

		socio_name = _find_socio_by_dni(dni)
		if not socio_name:
			stats.socios_no_encontrados += 1
			stats.errores.append(
				_("Socio no encontrado DNI {0} ({1})").format(dni, row.get("nombre") or "—")
			)
			continue

		try:
			result = vincular_basquet_socio(
				socio_name,
				categoria=row["categoria"],
				equipo=row["equipo"],
				dry_run=dry_run,
			)
			if result["status"] in {"ok", "dry_run"}:
				stats.vinculados += 1
		except Exception as exc:  # noqa: BLE001 — import masivo continúa
			stats.errores.append(
				_("DNI {0}: {1}").format(dni, str(exc)[:200])
			)

	if not dry_run:
		frappe.db.commit()
	return stats.to_dict()


def _row_dedupe_key(row: dict[str, str]) -> str:
	dni = row.get("dni") or ""
	if dni:
		return f"dni:{dni}"
	return f"nombre:{normalize_roster_nombre(row.get('nombre'))}|{row.get('categoria')}|{row.get('equipo')}"


def import_roster_jugadores(
	*,
	source_path: str,
	dry_run: bool = True,
	output_dir: str | None = None,
) -> dict[str, Any]:
	"""Importa roster CSV Jugadorxs: inscribe solo si no hay básquet activo; genera 3 logs."""
	rows = parse_jugadores_csv_rows(source_path)
	result = RosterImportJugadoresResult(total_filas=len(rows))
	dni_map, nombre_map = _build_socio_lookup_maps()
	seen_keys: set[str] = set()
	out_dir = Path(output_dir) if output_dir else Path(source_path).parent

	for row in rows:
		dedupe = _row_dedupe_key(row)
		if dedupe in seen_keys:
			result.omitidos_duplicado_csv += 1
			continue
		seen_keys.add(dedupe)

		base = _log_row(
			numero=row.get("numero", ""),
			dni=row.get("dni", ""),
			nombre=row.get("nombre", ""),
			categoria=row.get("categoria", ""),
			equipo=row.get("equipo", ""),
		)
		socio_name = _find_socio_roster(row, dni_map=dni_map, nombre_map=nombre_map)
		if not socio_name:
			if row.get("dni"):
				result.no_padron_con_dni += 1
				result.log_no_padron_con_dni.append(base)
			else:
				result.no_padron_sin_dni += 1
				result.log_no_padron_sin_dni.append(base)
			continue

		existing = _inscripcion_basquet_activa(socio_name)
		if existing:
			result.ya_inscriptos += 1
			result.log_ya_inscriptos.append(
				{
					**base,
					"socio": socio_name,
					"inscripcion_existente": existing["label"],
				}
			)
			continue

		try:
			link = vincular_basquet_socio(
				socio_name,
				categoria=row["categoria"],
				equipo=row["equipo"],
				dry_run=dry_run,
				reemplazar_inscripciones=False,
			)
			if link["status"] in {"ok", "dry_run"}:
				result.inscripciones_nuevas += 1
		except Exception as exc:  # noqa: BLE001 — lote continúa
			result.errores.append(
				_("{0} ({1}): {2}").format(
					row.get("nombre") or "—",
					row.get("dni") or "sin DNI",
					str(exc)[:200],
				)
			)

	if not dry_run:
		frappe.db.commit()

	result.log_paths = {
		"no_padron_sin_dni": _write_roster_log_csv(
			out_dir, LOG_NO_PADRON_SIN_DNI, result.log_no_padron_sin_dni
		),
		"no_padron_con_dni": _write_roster_log_csv(
			out_dir, LOG_NO_PADRON_CON_DNI, result.log_no_padron_con_dni
		),
		"ya_inscriptos": _write_roster_log_csv(out_dir, LOG_YA_INSCRIPTOS, result.log_ya_inscriptos),
	}
	return result.to_dict()


def default_roster_csv_jugadorxs_path() -> str:
	candidates = [
		Path("/mnt/c/Users/USUARIO/Desktop/JUGADORES BASQUET - PEDRO ECHAGUE - Jugadorxs.csv"),
		Path(frappe.get_site_path("private/files/JUGADORES BASQUET - PEDRO ECHAGUE - Jugadorxs.csv")),
	]
	for candidate in candidates:
		if candidate.is_file():
			return str(candidate)
	return str(candidates[0])


def default_roster_xlsx_path() -> str:
	candidates = [
		Path("/mnt/c/Users/USUARIO/Desktop/JUGADORES BASQUET - PEDRO ECHAGUE.xlsx"),
		Path(frappe.get_site_path("private/files/JUGADORES BASQUET - PEDRO ECHAGUE.xlsx")),
		Path(frappe.get_site_path("JUGADORES BASQUET - PEDRO ECHAGUE.xlsx")),
	]
	for candidate in candidates:
		if candidate.is_file():
			return str(candidate)
	return str(candidates[0])

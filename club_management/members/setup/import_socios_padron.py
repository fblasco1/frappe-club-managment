"""Migración masiva del padrón legacy de socios desde CSV hacia el DocType `Socio`.

Diseñado para ejecutarse con `bench execute` dentro del entorno Frappe.

Ejemplo (desde el contenedor `backend` o el bench local):

    bench --site <sitio> execute \\
        club_management.members.setup.import_socios_padron.run \\
        --kwargs '{"csv_path": "/home/francisco/frappe-bench/sites/socios_limpios_frappe.csv"}'

Parámetros opcionales de `run()`:
- `csv_path` (str): ruta absoluta al CSV.
- `dry_run` (bool): si True, valida y mapea pero no inserta.
- `commit_every` (int): commits parciales cada N inserciones exitosas (0 = solo al final).
- `default_estado` (str): estado inicial para registros no Vitalicio (default: "Activo").

Notas:
- El DocType destino es **`Socio`**. Si en su bench difiere (p. ej. `Member`), cambie
  la constante `DOCTYPE` al inicio de este archivo.
- Campos legacy sin columna nativa en `Socio` (`nro_socio`, `matrícula`, `cobrador`,
  `cuenta`, `notas`) se persisten si existen Custom Fields configurados en
  `LEGACY_FIELD_MAP`; si no, quedan en un comentario JSON trazable en el documento.
- Contacto: `telefono_fijo` / `telefono_movil` vía heurística `parsear_telefono` (≥10 dígitos → móvil; &lt;10 → fijo); `email` vacío si el CSV no trae valor.
- Domicilio: `calle`, `numero`, `piso`, `departamento`, `provincia`, `ciudad`, `localidad_barrio`.
- Para menores sin tutor en el CSV, la migración usa `flags.ignore_validate` de forma
  explícita (solo en este script) para no bloquear el padrón; Secretaría debe completar
  tutores en un segundo paso.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frappe
from frappe.exceptions import DuplicateEntryError, MandatoryError, ValidationError
from frappe.utils import getdate

from club_management.members.services.telefono import mapear_telefonos_desde_fila

# ---------------------------------------------------------------------------
# Configuración del DocType destino
# ---------------------------------------------------------------------------
DOCTYPE = "Socio"  # Cambiar a "Member" (u otro) si su bench usa otro nombre.

# Placeholders de migración (mismos paths simbólicos que en tests de Members).
MIGRATION_FOTO_PERFIL = "/files/padron_migracion_foto.jpg"
MIGRATION_DNI_FRENTE = "/files/padron_migracion_dni_frente.jpg"
MIGRATION_DNI_DORSO = "/files/padron_migracion_dni_dorso.jpg"
MIGRATION_FICHA_MEDICA = "/files/padron_migracion_ficha_medica.pdf"

# Mapeo CSV → Custom Field (opcional). Si el field no existe en el DocType, se omite.
LEGACY_FIELD_MAP: dict[str, str] = {
	"nro_socio": "nro_socio_padron",
	"matrícula": "matricula_padron",
	"cobrador": "cobrador_padron",
	"cuenta": "cuenta_padron",
	"notas": "notas_padron",
}

# Transformación de tiras de básquet: A → Azul, B → Amarillo (spec activities_jerarquia).
BASKETBALL_TIRA_MAP: dict[str, str] = {
	"A": "Azul",
	"B": "Amarillo",
	"a": "Azul",
	"b": "Amarillo",
}

# Mapeo de categorías del padrón → `Socio.categoria`.
CATEGORIA_PADRON_MAP: dict[str, str] = {
	"ACTIVO": "Activo",
	"MENOR": "Menor",
	"ADHERENTE": "Adherente",
	"2º HIJO": "2° Hermano",
	"2° HIJO": "2° Hermano",
	"2ª HIJO": "2° Hermano",
	"3º HIJO": "3° Hermano",
	"JUBILADO": "Jubilado",
	"JUBILADO CENTRO": "Jubilado",
	"VITALICIO": "Vitalicio",
	"BECADO": "Activo",
	"SOCIOS BEC. 7A.": "Activo",
}

TELEFONOS_INVALIDOS_ETIQUETA = "Teléfonos Inválidos"

CSV_COLUMNS: tuple[str, ...] = (
	"nro_socio",
	"socio",
	"fecha_alta",
	"fecha_nacimiento",
	"doc_identidad",
	"categoria_socio",
	"matrícula",
	"cobrador",
	"teléfono",
	"tel_movil",
	"email",
	"cuenta",
	"foto",
	"notas",
	"calle",
	"numero",
	"piso",
	"departamento",
	"provincia",
	"ciudad",
	"localidad_barrio",
	"codigo_postal",
)


@dataclass
class MigrationStats:
	total_leidos: int = 0
	total_exitosos: int = 0
	total_fallidos: int = 0
	choques: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

	def registrar_fallo(self, etiqueta_error: str, identificador: str) -> None:
		self.total_fallidos += 1
		self.choques[etiqueta_error].append(identificador)

	def registrar_advertencia(self, etiqueta: str, detalle: str) -> None:
		"""Registra un choque informativo sin contar como fallo de inserción."""
		self.choques[etiqueta].append(detalle)

	def registrar_exito(self) -> None:
		self.total_exitosos += 1

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_leidos": self.total_leidos,
			"total_exitosos": self.total_exitosos,
			"total_fallidos": self.total_fallidos,
			"choques": dict(self.choques),
		}


def run(
	csv_path: str | None = None,
	dry_run: bool = False,
	commit_every: int = 50,
	default_estado: str = "Activo",
) -> dict[str, Any]:
	"""Punto de entrada para `bench execute`."""
	path = Path(csv_path or _default_csv_path())
	if not path.is_file():
		frappe.throw(f"No se encontró el CSV en: {path}")

	stats = migrate_padron_csv(
		path,
		dry_run=dry_run,
		commit_every=commit_every,
		default_estado=default_estado,
	)
	_print_resumen(stats, dry_run=dry_run)
	return stats.to_dict()


def migrate_padron_csv(
	csv_path: Path,
	*,
	dry_run: bool = False,
	commit_every: int = 50,
	default_estado: str = "Activo",
) -> MigrationStats:
	"""Lee el CSV completo e intenta insertar cada fila en `Socio`."""
	stats = MigrationStats()
	meta_fieldnames = {
		df.fieldname for df in frappe.get_meta(DOCTYPE).fields
	}
	rows = _read_csv_rows(csv_path)
	stats.total_leidos = len(rows)

	for row in rows:
		identificador = _row_identifier(row)
		try:
			payload, telefonos_invalidos = build_socio_payload(
				row,
				meta_fieldnames=meta_fieldnames,
				default_estado=default_estado,
				return_telefonos_invalidos=True,
			)
			for numero in telefonos_invalidos:
				stats.registrar_advertencia(
					TELEFONOS_INVALIDOS_ETIQUETA,
					f"{identificador} — {numero}",
				)
			if dry_run:
				stats.registrar_exito()
				continue

			doc = frappe.get_doc(payload)
			doc.flags.ignore_validate = True
			if payload.get("estado") == "Vitalicio":
				doc.flags.estado_change_authorized = True

			doc.insert(ignore_permissions=True, ignore_mandatory=True)
			_persist_legacy_metadata(doc, row, meta_fieldnames)
			stats.registrar_exito()

			if commit_every and stats.total_exitosos % commit_every == 0:
				frappe.db.commit()

		except (ValidationError, DuplicateEntryError, MandatoryError) as exc:
			stats.registrar_fallo(_classify_frappe_error(exc), identificador)
		except Exception as exc:  # noqa: BLE001 — migración masiva: no detener el lote
			stats.registrar_fallo(f"Error inesperado: {type(exc).__name__}", identificador)

	if not dry_run:
		frappe.db.commit()

	return stats


def build_socio_payload(
	row: dict[str, str],
	*,
	meta_fieldnames: set[str] | None = None,
	default_estado: str = "Activo",
	return_telefonos_invalidos: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], list[str]]:
	"""Transforma una fila del CSV en el dict para `frappe.get_doc`."""
	meta_fieldnames = meta_fieldnames or {
		df.fieldname for df in frappe.get_meta(DOCTYPE).fields
	}

	apellido, nombre = _split_socio_name(row.get("socio", ""))
	dni = _normalize_dni(row.get("doc_identidad", ""))
	categoria = _map_categoria(row.get("categoria_socio", ""))
	basket_context = _basketball_context(row)
	matricula = _transform_basketball_category(
		(row.get("matrícula") or "").strip(),
		context=basket_context,
	)

	telefono_fijo, telefono_movil, telefonos_invalidos = mapear_telefonos_desde_fila(row)
	email = _normalize_email(row.get("email", ""))
	provincia = (row.get("provincia") or "").strip()
	ciudad = (row.get("ciudad") or "").strip()
	localidad_barrio = (row.get("localidad_barrio") or "").strip()
	codigo_postal = (row.get("codigo_postal") or "").strip()
	fecha_nacimiento = _parse_date(row.get("fecha_nacimiento", ""))
	fecha_alta = _parse_date(row.get("fecha_alta", ""))

	estado = "Vitalicio" if categoria == "Vitalicio" else (default_estado or "Activo")

	payload: dict[str, Any] = {
		"doctype": DOCTYPE,
		"nombre": nombre or "Sin nombre",
		"apellido": apellido or "Sin apellido",
		"dni": dni,
		"nacionalidad": "Argentina",
		"fecha_nacimiento": fecha_nacimiento,
		"genero": "Prefiero no decir",
		"email": email,
		"telefono_fijo": telefono_fijo,
		"telefono_movil": telefono_movil,
		"calle": (row.get("calle") or "").strip(),
		"numero": (row.get("numero") or "").strip(),
		"piso": (row.get("piso") or "").strip(),
		"departamento": (row.get("departamento") or "").strip(),
		"provincia": provincia,
		"ciudad": ciudad,
		"localidad_barrio": localidad_barrio,
		"codigo_postal": codigo_postal,
		"categoria": categoria,
		"estado": estado,
		"foto_perfil": MIGRATION_FOTO_PERFIL if _is_missing_attachment(row.get("foto")) else row["foto"],
		"dni_frente": MIGRATION_DNI_FRENTE,
		"dni_dorso": MIGRATION_DNI_DORSO,
		"ficha_medica": MIGRATION_FICHA_MEDICA,
	}

	if fecha_alta:
		payload["fecha_alta"] = fecha_alta

	_assign_legacy_fields(payload, row, meta_fieldnames)
	if matricula and "matricula_padron" in meta_fieldnames:
		payload["matricula_padron"] = matricula

	_validate_required_mapping(payload, row)
	if return_telefonos_invalidos:
		return payload, telefonos_invalidos
	return payload


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
	with csv_path.open(newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		if not reader.fieldnames:
			frappe.throw(f"El CSV no tiene encabezados: {csv_path}")

		missing = [col for col in CSV_COLUMNS if col not in reader.fieldnames]
		if missing:
			frappe.throw(
				"Faltan columnas obligatorias en el CSV: "
				+ ", ".join(missing)
				+ f". Encontradas: {', '.join(reader.fieldnames)}"
			)

		return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def _split_socio_name(full_name: str) -> tuple[str, str]:
	"""Convención del padrón: «APELLIDO NOMBRE(S)»."""
	parts = (full_name or "").strip().split()
	if not parts:
		return "", ""
	if len(parts) == 1:
		return parts[0], parts[0]
	return parts[0], " ".join(parts[1:])


def _normalize_dni(raw: str) -> str:
	text = (raw or "").strip()
	if not text:
		return ""
	digits = re.sub(r"\D", "", text)
	return digits or text


def _map_categoria(raw: str) -> str:
	key = (raw or "").strip().upper()
	if not key:
		return "Activo"
	return CATEGORIA_PADRON_MAP.get(key, "Activo")


def _basketball_context(row: dict[str, str]) -> str:
	parts = [
		row.get("categoria_socio", ""),
		row.get("matrícula", ""),
		row.get("notas", ""),
	]
	return " ".join(p for p in parts if p)


def _transform_basketball_category(value: str, *, context: str = "") -> str:
	"""A/B de básquet → Azul/Amarillo cuando el contexto lo indica."""
	if not value:
		return value

	normalized = value.strip()
	context_upper = (context or "").upper()
	is_basketball = any(token in context_upper for token in ("BASQUET", "BÁSQUET", "BASQUETBOL"))

	if normalized in BASKETBALL_TIRA_MAP and (is_basketball or len(normalized) == 1):
		return BASKETBALL_TIRA_MAP[normalized]
	return normalized


def _first_non_empty(*values: str | None) -> str:
	for value in values:
		text = (value or "").strip()
		if text:
			return text
	return ""


def _normalize_email(raw: str) -> str:
	email = (raw or "").strip().lower()
	return email if email else ""


def _parse_date(raw: str) -> str | None:
	text = (raw or "").strip()
	if not text:
		return None
	try:
		return str(getdate(text))
	except Exception:
		return None


def _is_missing_attachment(raw: str | None) -> bool:
	value = (raw or "").strip().upper()
	return not value or value in {"NO", "N/A", "NA", "SIN FOTO", "0"}


def _assign_legacy_fields(
	payload: dict[str, Any],
	row: dict[str, str],
	meta_fieldnames: set[str],
) -> None:
	for csv_col, fieldname in LEGACY_FIELD_MAP.items():
		if fieldname not in meta_fieldnames:
			continue
		value = (row.get(csv_col) or "").strip()
		if csv_col == "matrícula" and value:
			value = _transform_basketball_category(value, context=_basketball_context(row))
		if value:
			payload[fieldname] = value


def _validate_required_mapping(payload: dict[str, Any], row: dict[str, str]) -> None:
	"""Validaciones previas para mensajes de error más claros antes del insert."""
	if not payload.get("dni"):
		frappe.throw(
			"Falta campo obligatorio: doc_identidad (DNI)",
			MandatoryError,
		)
	if not payload.get("fecha_nacimiento"):
		frappe.throw(
			"Falta campo obligatorio: fecha_nacimiento",
			MandatoryError,
		)

	email = (row.get("email") or "").strip().lower()
	if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
		frappe.throw(
			"Formato de correo inválido",
			ValidationError,
		)


def _persist_legacy_metadata(
	doc: frappe.model.document.Document,
	row: dict[str, str],
	meta_fieldnames: set[str],
) -> None:
	"""Guarda metadatos legacy en comentario si no hay Custom Fields."""
	legacy: dict[str, Any] = {}
	for csv_col, fieldname in LEGACY_FIELD_MAP.items():
		if fieldname in meta_fieldnames:
			continue
		value = (row.get(csv_col) or "").strip()
		if csv_col == "matrícula" and value:
			value = _transform_basketball_category(value, context=_basketball_context(row))
		if value:
			legacy[csv_col] = value

	if not legacy:
		return

	doc.add_comment(
		"Comment",
		"Padron legacy: " + json.dumps(legacy, ensure_ascii=False, sort_keys=True),
	)


def _classify_frappe_error(exc: Exception) -> str:
	message = str(exc).strip()
	lower = message.lower()

	if isinstance(exc, DuplicateEntryError):
		return "DNI duplicado"

	if isinstance(exc, MandatoryError):
		if "fecha_nacimiento" in lower:
			return "Falta campo obligatorio: fecha_nacimiento"
		if "doc_identidad" in lower or "dni" in lower:
			return "Falta campo obligatorio: doc_identidad (DNI)"
		return f"Falta campo obligatorio: {message or 'desconocido'}"

	if isinstance(exc, ValidationError):
		if "duplicate" in lower or "already exists" in lower or "unique" in lower:
			return "DNI duplicado"
		if "email" in lower and ("invalid" in lower or "inválid" in lower):
			return "Formato de correo inválido"
		if "menor requiere tutor" in lower:
			return "Menor sin tutor responsable"
		if "vitalicio" in lower and "manualmente" in lower:
			return "Estado Vitalicio bloqueado en alta manual"
		return f"ValidationError: {message or 'sin detalle'}"

	return f"Error Frappe: {message or type(exc).__name__}"


def _row_identifier(row: dict[str, str]) -> str:
	nro = (row.get("nro_socio") or "").strip()
	nombre = (row.get("socio") or "").strip()
	if nro and nombre:
		return f"{nro} — {nombre}"
	return nro or nombre or "fila sin identificador"


def _default_csv_path() -> str:
	candidates = [
		Path("/mnt/c/Users/USUARIO/Desktop/socios_limpios_frappe.csv"),
		Path(frappe.get_site_path("socios_limpios_frappe.csv")),
	]
	for candidate in candidates:
		if candidate.is_file():
			return str(candidate)
	return str(candidates[1])


def _print_resumen(stats: MigrationStats, *, dry_run: bool = False) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "MIGRACIÓN"
	print("\n" + "=" * 72)
	print(f" RESUMEN {mode} — DocType `{DOCTYPE}`")
	print("=" * 72)
	print(f" Total registros leídos del CSV : {stats.total_leidos}")
	print(f" Total insertados con éxito      : {stats.total_exitosos}")
	print(f" Total fallidos                  : {stats.total_fallidos}")
	print("-" * 72)
	print(" Choques agrupados por tipo de error:")
	if not stats.choques:
		print("  (ninguno)")
	else:
		for error_type in sorted(stats.choques):
			afectados = stats.choques[error_type]
			print(f"\n  [{len(afectados)}] {error_type}")
			for item in afectados:
				print(f"      - {item}")
	print("=" * 72 + "\n")

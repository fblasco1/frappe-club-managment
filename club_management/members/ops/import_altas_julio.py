"""Importa altas desde ``ALTAS JULIO.xlsx`` (solo socios inexistentes por DNI).

Uso:

    bench --site dev.localhost execute \\
        club_management.members.ops.import_altas_julio.run \\
        --kwargs '{"dry_run": true}'

    bench --site dev.localhost execute \\
        club_management.members.ops.import_altas_julio.run \\
        --kwargs '{"apply": true}'
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import frappe
import openpyxl
from frappe.utils import getdate

from club_management.members.services.cobranza_manual import (
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.socio_operaciones_secretaria import activar_socio_manual
from club_management.members.services.suscripciones_socio import sync_suscripcion_cuota_al_validar_socio
from club_management.members.setup.import_socios_padron import (
	MIGRATION_DNI_DORSO,
	MIGRATION_DNI_FRENTE,
	MIGRATION_FICHA_MEDICA,
	MIGRATION_FOTO_PERFIL,
	_split_socio_name,
)

DEFAULT_XLSX = "/workspace/development/frappe-bench/sites/ALTAS_JULIO.xlsx"

_CATEGORIA_NOTAS: dict[str, str] = {
	"MENOR": "Menor",
	"ACTIVO": "Activo",
	"ADHERENTE": "Adherente",
	"JUBILADO": "Jubilado",
	"VITALICIO": "Vitalicio",
	"2 HIJO": "2° Hermano",
	"2° HIJO": "2° Hermano",
	"2º HIJO": "2° Hermano",
	"3 HIJO": "3° Hermano",
	"3° HIJO": "3° Hermano",
	"3º HIJO": "3° Hermano",
}


def run(
	*,
	dry_run: bool = False,
	apply: bool = False,
	xlsx_path: str | None = None,
) -> dict[str, Any]:
	"""Crea socios del Excel que aún no existen (match por DNI)."""
	if dry_run and apply:
		frappe.throw("Usar solo dry_run o apply, no ambos.")
	modo = "apply" if apply else "dry_run"
	path = xlsx_path or DEFAULT_XLSX
	filas = _leer_filas(path)
	resultado: dict[str, Any] = {
		"modo": modo,
		"xlsx": path,
		"total": len(filas),
		"creados": [],
		"existentes": [],
		"omitidos": [],
		"errores": [],
	}

	for fila in filas:
		try:
			item = _procesar_fila(fila, modo=modo)
			accion = item.get("accion")
			if accion == "crear":
				resultado["creados"].append(item)
			elif accion == "existente":
				resultado["existentes"].append(item)
			else:
				resultado["omitidos"].append(item)
		except Exception as exc:
			resultado["errores"].append({"fila": fila, "error": str(exc)})

	if apply:
		frappe.db.commit()

	resultado["resumen"] = {
		"creados": len(resultado["creados"]),
		"existentes": len(resultado["existentes"]),
		"omitidos": len(resultado["omitidos"]),
		"errores": len(resultado["errores"]),
	}
	return resultado


def _leer_filas(path: str) -> list[dict[str, Any]]:
	wb = openpyxl.load_workbook(path, data_only=True)
	ws = wb.active
	rows = list(ws.iter_rows(values_only=True))
	# Encabezado en fila 4 (1-based); datos desde fila 5.
	out: list[dict[str, Any]] = []
	for row in rows[4:]:
		if not row or row[0] is None:
			continue
		out.append(
			{
				"numero_socio": int(row[0]),
				"nombre_completo": str(row[1] or "").strip(),
				"fecha_alta": row[2],
				"fecha_nacimiento": row[3],
				"doc_identidad": row[4],
				"direccion": str(row[6] or "").strip(),
				"ciudad": str(row[7] or "").strip(),
				"provincia": str(row[8] or "").strip() or "CABA",
				"telefono": row[9],
				"email": str(row[10] or "").strip().lower(),
				"notas": str(row[12] or "").strip() if row[12] is not None else "",
			}
		)
	return out


def _procesar_fila(fila: dict[str, Any], *, modo: str) -> dict[str, Any]:
	dni = _parse_dni(fila.get("doc_identidad"))
	item: dict[str, Any] = {
		"numero_excel": fila["numero_socio"],
		"dni": dni,
		"nombre_completo": fila["nombre_completo"],
		"accion": None,
		"socio": None,
	}
	if not dni:
		item["accion"] = "omitido_sin_dni"
		return item

	existente = frappe.db.get_value("Socio", {"dni": dni}, "name")
	if existente:
		item["accion"] = "existente"
		item["socio"] = existente
		return item

	apellido, nombre = _split_socio_name(fila["nombre_completo"])
	categoria = _categoria_desde_notas(fila.get("notas") or "")
	fecha_nac = _parse_date(fila.get("fecha_nacimiento"))
	fecha_alta = _parse_date(fila.get("fecha_alta"))
	telefono = _normalize_phone(fila.get("telefono"))
	email = (fila.get("email") or "").strip()
	if not email:
		email = f"alta.julio.{dni}@local.invalid"

	numero = int(fila["numero_socio"])
	numero_libre = not frappe.db.exists("Socio", str(numero))

	payload: dict[str, Any] = {
		"doctype": "Socio",
		"nombre": (nombre or apellido).title(),
		"apellido": (apellido or nombre).title(),
		"dni": dni,
		"nacionalidad": "Argentina",
		"fecha_nacimiento": fecha_nac or date(2000, 1, 1),
		"genero": "Prefiero no decir",
		"email": email,
		"telefono_movil": telefono or "1100000000",
		"calle": fila.get("direccion") or "Sin domicilio",
		"provincia": fila.get("provincia") or "CABA",
		"ciudad": fila.get("ciudad") or "CABA",
		"localidad_barrio": fila.get("ciudad") or "CABA",
		"codigo_postal": "0000",
		"categoria": categoria,
		"estado": "Pendiente de Pago",
		"foto_perfil": MIGRATION_FOTO_PERFIL,
		"dni_frente": MIGRATION_DNI_FRENTE,
		"dni_dorso": MIGRATION_DNI_DORSO,
		"ficha_medica": MIGRATION_FICHA_MEDICA,
	}
	if numero_libre:
		payload["numero_socio"] = numero
	else:
		item["numero_conflicto"] = numero

	item["accion"] = "crear"
	item["categoria"] = categoria
	item["payload_preview"] = {
		"apellido": payload["apellido"],
		"nombre": payload["nombre"],
		"numero_socio": payload.get("numero_socio"),
		"email": email,
	}

	if modo != "apply":
		return item

	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
	if erpnext_cobranza_disponible():
		ensure_customer_for_socio(doc.name, skip_permission_check=True)
	sync_suscripcion_cuota_al_validar_socio(doc.name)
	activar_socio_manual(doc.name, motivo="Alta Julio 2026 (import ALTAS JULIO.xlsx)")
	if fecha_alta:
		# fecha_alta la setea activar; si el padrones trae otra, respetarla.
		frappe.db.set_value("Socio", doc.name, "fecha_alta", getdate(fecha_alta), update_modified=False)
	item["socio"] = doc.name
	return item


def _parse_dni(value: Any) -> str | None:
	if value is None:
		return None
	match = re.search(r"(\d{7,8})", str(value))
	return match.group(1) if match else None


def _parse_date(value: Any) -> date | None:
	if value is None or value == "":
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	text = str(value).strip()
	for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
		try:
			return datetime.strptime(text, fmt).date()
		except ValueError:
			continue
	try:
		return getdate(text)
	except Exception:
		return None


def _normalize_phone(value: Any) -> str:
	if value is None:
		return ""
	digits = re.sub(r"\D", "", str(value))
	return digits


def _categoria_desde_notas(notas: str) -> str:
	raw = (notas or "").replace("_x000D_", "\n").replace("\r", "\n")
	primera = raw.split("\n", 1)[0].strip().upper()
	primera = re.sub(r"\s+", " ", primera)
	if primera in _CATEGORIA_NOTAS:
		return _CATEGORIA_NOTAS[primera]
	# Prefijos frecuentes
	for key, cat in _CATEGORIA_NOTAS.items():
		if primera.startswith(key):
			return cat
	return "Activo"

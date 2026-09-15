"""Alta masiva de socios becados (beca total) — jugadores que no juegan más.

Uso:

    bench --site dev.localhost execute \\
        club_management.members.ops.import_socios_becados_no_juegan.run \\
        --kwargs '{"dry_run": true}'

    bench --site dev.localhost execute \\
        club_management.members.ops.import_socios_becados_no_juegan.run \\
        --kwargs '{"apply": true}'
"""

from __future__ import annotations

import datetime
from typing import Any

import frappe
from frappe.utils import add_months, getdate, today

from club_management.members.services.cobranza_manual import (
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.socio_operaciones_secretaria import activar_socio_manual
from club_management.members.services.suscripciones_socio import sync_suscripcion_cuota_al_validar_socio

# Socios becados básquet — julio 2026.
# «No juegan más» (Furfaro, Fernandez) = excluir del roster; NO crear socio.
_FILAS: list[dict[str, Any]] = [
	{"dni": "43988843", "nombre_display": "Caria, Ramiro", "cat_basquet": "MAYOR", "tira": "Azul"},
	{"dni": "42875700", "nombre_display": "FILINICH, Santiago Lucas", "cat_basquet": "MAYOR", "tira": "Azul"},
	{"dni": "43905592", "nombre_display": "Ramayo, Juan Cruz", "cat_basquet": "MAYOR", "tira": "Azul"},
	{"dni": "43088633", "nombre_display": "Lucero, Lucas", "cat_basquet": "MAYOR", "tira": "Azul"},
	{"nombre_display": "Rinaldi, Martin", "cat_basquet": "MAYOR", "tira": "Azul"},
	{"nombre_display": "Di Biase, Rodolfo", "cat_basquet": "MAYOR", "tira": "Azul"},
	{"nombre_display": "Sandoval, Javier Osvaldo", "cat_basquet": "U17", "tira": "Azul"},
	{"dni": "52140838", "nombre_display": "Greco, Xavier", "cat_basquet": "U15", "tira": "Azul"},
]

_EDAD_POR_CAT = {"U13": 12, "U15": 14, "U17": 16, "MAYOR": 25}
_TUTOR_PLACEHOLDER_DNI = "90000001"


def run(*, dry_run: bool = False, apply: bool = False) -> dict[str, Any]:
	"""Crea socios faltantes y asigna beca total vigente."""
	if dry_run and apply:
		frappe.throw("Usar solo dry_run o apply, no ambos.")

	modo = "apply" if apply else "dry_run"
	resultado: dict[str, Any] = {"modo": modo, "filas": [], "errores": []}

	tutor_menor = _resolver_tutor_menor(modo=modo, resultado=resultado)

	for fila in _FILAS:
		try:
			item = _procesar_fila(fila, tutor_menor=tutor_menor, modo=modo)
			resultado["filas"].append(item)
		except Exception as exc:
			resultado["errores"].append({"fila": fila, "error": str(exc)})

	if apply:
		frappe.db.commit()

	return resultado


def _procesar_fila(fila: dict[str, Any], *, tutor_menor: str | None, modo: str) -> dict[str, Any]:
	dni = (fila.get("dni") or "").strip()
	apellido, nombre = _parse_nombre(fila["nombre_display"])
	genero = _inferir_genero(nombre, fila.get("tira"))
	cat_basquet = fila.get("cat_basquet") or "MAYOR"
	categoria = "Menor" if cat_basquet in ("U13", "U15", "U17") else "Activo"
	fecha_nac = _fecha_nac_por_cat(cat_basquet)

	item: dict[str, Any] = {
		"dni": dni or None,
		"nombre_display": fila["nombre_display"],
		"cat_basquet": cat_basquet,
		"tira": fila.get("tira"),
		"accion_socio": None,
		"accion_beca": None,
		"socio": None,
	}

	socio_name = _buscar_socio(dni=dni, apellido=apellido, nombre=nombre)
	if socio_name:
		item["socio"] = socio_name
		item["accion_socio"] = "existente"
	else:
		if not dni:
			item["accion_socio"] = "omitido_sin_dni"
			return item

		payload = _payload_socio(
			dni=dni,
			apellido=apellido,
			nombre=nombre,
			genero=genero,
			categoria=categoria,
			fecha_nacimiento=fecha_nac,
			numero_socio=fila.get("numero_socio"),
			cat_basquet=cat_basquet,
			tira=fila.get("tira"),
			tutor_menor=tutor_menor if categoria == "Menor" else None,
		)
		item["accion_socio"] = "crear"
		item["payload"] = {k: v for k, v in payload.items() if k != "doctype"}

		if modo == "apply":
			doc = frappe.get_doc(payload)
			doc.insert(ignore_permissions=True, ignore_mandatory=True)
			if erpnext_cobranza_disponible():
				ensure_customer_for_socio(doc.name, skip_permission_check=True)
			sync_suscripcion_cuota_al_validar_socio(doc.name)
			socio_name = doc.name
			item["socio"] = socio_name

	if not socio_name:
		return item

	estado = frappe.db.get_value("Socio", socio_name, "estado")
	if estado != "Activo":
		item["estado_previo"] = estado
		item["accion_activar"] = "activar"
		if modo == "apply":
			activar_socio_manual(socio_name, motivo="Alta becado — no juega más (básquet)")
	else:
		item["accion_activar"] = "ya_activo"

	beca_existente = _beca_total_vigente(socio_name)
	if beca_existente:
		item["accion_beca"] = "beca_vigente_existente"
		item["beca"] = beca_existente
	else:
		item["accion_beca"] = "crear_beca_total"
		if modo == "apply":
			beca = frappe.get_doc(
				{
					"doctype": "Beca Socio",
					"socio": socio_name,
					"tipo_beca": "Total",
					"fecha_desde": today(),
					"fecha_hasta": add_months(today(), 6),
					"estado": "Activa",
					"observaciones": _obs_beca(cat_basquet, fila.get("tira")),
				}
			)
			beca.insert(ignore_permissions=True)
			item["beca"] = beca.name

	return item


def _parse_nombre(display: str) -> tuple[str, str]:
	texto = (display or "").strip()
	if "," in texto:
		ap, nom = texto.split(",", 1)
		return ap.strip().title(), nom.strip()
	partes = texto.split()
	if len(partes) >= 2:
		return partes[0].title(), " ".join(partes[1:]).title()
	return texto.title(), ""


def _inferir_genero(nombre: str, tira: str | None) -> str:
	if (tira or "").lower() == "femenino":
		return "Femenino"
	nom = nombre.lower()
	if any(x in nom for x in ("maria", "paz", "sabina", "ines")):
		return "Femenino"
	return "Masculino"


def _fecha_nac_por_cat(cat_basquet: str) -> datetime.date:
	anos = _EDAD_POR_CAT.get(cat_basquet, 25)
	hoy = datetime.date.today()
	try:
		return hoy.replace(year=hoy.year - anos)
	except ValueError:
		return hoy.replace(month=2, day=28, year=hoy.year - anos)


def _payload_socio(
	*,
	dni: str,
	apellido: str,
	nombre: str,
	genero: str,
	categoria: str,
	fecha_nacimiento: datetime.date,
	numero_socio: int | None,
	cat_basquet: str,
	tira: str | None,
	tutor_menor: str | None,
) -> dict[str, Any]:
	email = f"{dni}@becado.icdpedroechague.local"
	payload: dict[str, Any] = {
		"doctype": "Socio",
		"nombre": nombre,
		"apellido": apellido,
		"dni": dni,
		"nacionalidad": "Argentina",
		"fecha_nacimiento": fecha_nacimiento,
		"genero": genero,
		"email": email,
		"telefono_movil": "+540000000000",
		"calle": "Sin domicilio cargado",
		"provincia": "Buenos Aires",
		"ciudad": "Pedro Echagüe",
		"localidad_barrio": "Pedro Echagüe",
		"codigo_postal": "3190",
		"categoria": categoria,
		"estado": "Pendiente de Pago",
		"foto_perfil": "/files/placeholder.jpg",
		"dni_frente": "/files/placeholder.jpg",
		"dni_dorso": "/files/placeholder.jpg",
		"ficha_medica": "/files/placeholder.pdf",
	}
	if numero_socio:
		payload["numero_socio"] = int(numero_socio)
	if categoria == "Menor" and tutor_menor:
		payload["tipo_tutor"] = "Tutor No Socio"
		payload["tutor"] = tutor_menor
	payload["observaciones"] = (
		f"No juega más (básquet). Cat. roster: {cat_basquet}"
		+ (f" / {tira}" if tira else "")
		+ ". Alta operativa jul-2026."
	)
	return payload


def _obs_beca(cat_basquet: str, tira: str | None) -> str:
	base = f"Beca total 100% — no juega más (básquet {cat_basquet}"
	return base + (f", {tira}" if tira else "") + ")"


def _buscar_socio(*, dni: str, apellido: str, nombre: str) -> str | None:
	if dni:
		return frappe.db.get_value("Socio", {"dni": dni}, "name")
	if not (apellido and nombre):
		return None

	# Sin DNI: coincidencia estricta por apellido + todas las palabras del nombre.
	palabras = [p for p in nombre.split() if len(p) > 2]
	filters: dict[str, Any] = {"apellido": ["like", f"%{apellido}%"]}
	for palabra in palabras:
		filters["nombre"] = ["like", f"%{palabra}%"]

	rows = frappe.get_all("Socio", filters=filters, fields=["name", "nombre", "apellido"], limit=5)
	if len(rows) != 1:
		return None

	row = rows[0]
	ap_db = (row.get("apellido") or "").lower()
	nom_db = (row.get("nombre") or "").lower()
	if apellido.lower() not in ap_db:
		return None
	for palabra in palabras:
		if palabra.lower() not in nom_db:
			return None
	return row["name"]


def _beca_total_vigente(socio_name: str) -> str | None:
	if not frappe.db.exists("DocType", "Beca Socio"):
		return None
	ref = getdate(today())
	return frappe.db.get_value(
		"Beca Socio",
		{
			"socio": socio_name,
			"estado": "Activa",
			"tipo_beca": "Total",
			"fecha_desde": ["<=", ref],
			"fecha_hasta": [">=", ref],
		},
		"name",
	)


def _resolver_tutor_menor(*, modo: str, resultado: dict[str, Any]) -> str | None:
	"""Tutor No Socio genérico para menores del lote."""
	if frappe.db.exists("Tutor No Socio", {"dni": _TUTOR_PLACEHOLDER_DNI}):
		return frappe.db.get_value("Tutor No Socio", {"dni": _TUTOR_PLACEHOLDER_DNI}, "name")

	if modo != "apply":
		resultado["tutor_menor"] = "se_crearia_tutor_placeholder"
		return "TUTOR-PLACEHOLDER"

	hoy = datetime.date.today()
	doc = frappe.get_doc(
		{
			"doctype": "Tutor No Socio",
			"nombre": "Club",
			"apellido": "ICDPE (importación)",
			"dni": _TUTOR_PLACEHOLDER_DNI,
			"nacionalidad": "Argentina",
			"fecha_nacimiento": hoy.replace(year=hoy.year - 40),
			"genero": "Masculino",
			"email": "tutor.importacion@icdpedroechague.local",
			"telefono_movil": "+540000000001",
			"calle": "Club",
			"provincia": "Buenos Aires",
			"ciudad": "Pedro Echagüe",
			"localidad_barrio": "Pedro Echagüe",
			"codigo_postal": "3190",
		}
	)
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
	resultado["tutor_menor"] = doc.name
	return doc.name

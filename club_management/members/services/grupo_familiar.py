"""Servicios de `Grupo Familiar` para el flujo Solicitud de Asociación."""

from __future__ import annotations

from datetime import date

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today

ROL_MIEMBOR_MENOR = "Hijo"


def ensure_grupo_for_socio(
	socio: Document,
	*,
	solicitud: Document | None = None,
	tutor_tipo: str | None = None,
	tutor_name: str | None = None,
	rol_miembro: str = ROL_MIEMBOR_MENOR,
) -> str:
	"""Asigna `grupo_familiar` al socio y devuelve el nombre del grupo.

	- Adulto: crea un grupo nuevo con el socio como único titular principal.
	- Menor: agrega el socio a `miembros` del grupo del tutor (debe existir).
	"""
	if socio.categoria == "Menor":
		if not tutor_tipo or not tutor_name:
			frappe.throw("Menor requiere tutor para ensure_grupo_for_socio")
		grupo_name = find_active_grupo_for_titular(tutor_tipo, tutor_name)
		if not grupo_name:
			frappe.throw(
				frappe._("Tutor debe ser titular activo de un Grupo Familiar")
			)
		_add_socio_miembro(grupo_name, socio.name, rol=rol_miembro)
		socio.db_set("grupo_familiar", grupo_name, commit=False)
		return grupo_name

	grupo = _create_grupo_for_socio_titular(socio, solicitud=solicitud)
	socio.db_set("grupo_familiar", grupo.name, commit=False)
	return grupo.name


def add_socio_a_grupo_existente(
	socio: Document,
	grupo_name: str,
	*,
	rol: str = "Otro",
) -> str:
	"""Suma un socio ya creado a un grupo existente, sin crear uno nuevo.

	Usado por el alta familiar del portal: el titular crea el `Grupo Familiar`
	al validarse y los demás integrantes del trámite se incorporan a ese mismo
	grupo con su `rol_en_grupo`.

	El cónyuge entra como **cotitular** (`titulares`, `es_principal=0`,
	`rol=Cotitular`). Secretaría puede quitar la titularidad después poniendo
	`hasta` en esa fila. El resto de roles adultos van a `miembros`.
	"""
	if rol == "Cónyuge":
		return add_cotitular_a_grupo(socio, grupo_name)

	_add_socio_miembro(grupo_name, socio.name, rol=rol or "Otro")
	socio.db_set("grupo_familiar", grupo_name, commit=False)
	return grupo_name


def add_cotitular_a_grupo(socio: Document, grupo_name: str) -> str:
	"""Agrega al socio como cotitular no principal del grupo.

	El validate de `Grupo Familiar` sincroniza titulares Socio a `miembros`.
	"""
	grupo = frappe.get_doc("Grupo Familiar", grupo_name)
	for fila in grupo.titulares or []:
		if (
			fila.tipo_titular == "Socio"
			and fila.titular == socio.name
			and not fila.hasta
		):
			socio.db_set("grupo_familiar", grupo_name, commit=False)
			return grupo_name

	grupo.append(
		"titulares",
		{
			"tipo_titular": "Socio",
			"titular": socio.name,
			"es_principal": 0,
			"rol": "Cotitular",
			"desde": today(),
		},
	)
	grupo.save(ignore_permissions=True)
	socio.db_set("grupo_familiar", grupo_name, commit=False)
	return grupo_name


def find_active_grupo_for_titular(tipo_titular: str, titular: str) -> str | None:
	rows = frappe.db.sql(
		"""
		SELECT t.parent
		FROM `tabTitular de Grupo Familiar` t
		WHERE t.parenttype = 'Grupo Familiar'
		  AND t.tipo_titular = %(tipo)s
		  AND t.titular = %(titular)s
		  AND t.hasta IS NULL
		LIMIT 1
		""",
		{"tipo": tipo_titular, "titular": titular},
	)
	return rows[0][0] if rows else None


def _create_grupo_for_socio_titular(
	socio: Document,
	*,
	solicitud: Document | None = None,
) -> Document:
	nombre_grupo = "Familia"
	apellido = socio.apellido or "Solicitud"
	if solicitud:
		nombre_grupo = f"Familia {solicitud.apellido or apellido}"
		apellido = solicitud.apellido or apellido

	grupo = frappe.get_doc(
		{
			"doctype": "Grupo Familiar",
			"nombre_grupo": nombre_grupo,
			"apellido_principal": apellido,
			"titulares": [
				{
					"tipo_titular": "Socio",
					"titular": socio.name,
					"es_principal": 1,
					"rol": "Titular",
				}
			],
		}
	)
	grupo.insert(ignore_permissions=True)
	return grupo


def create_grupo_for_tutor_no_socio(
	tutor_name: str,
	*,
	rol_titular: str = "Padre",
	apellido_principal: str | None = None,
	nombre_grupo: str | None = None,
) -> Document:
	tutor = frappe.get_doc("Tutor No Socio", tutor_name)
	grupo = frappe.get_doc(
		{
			"doctype": "Grupo Familiar",
			"nombre_grupo": nombre_grupo or f"Familia {tutor.apellido}",
			"apellido_principal": apellido_principal or tutor.apellido,
			"titulares": [
				{
					"tipo_titular": "Tutor No Socio",
					"titular": tutor_name,
					"es_principal": 1,
					"rol": rol_titular,
				}
			],
		}
	)
	grupo.insert(ignore_permissions=True)
	return grupo


def _add_socio_miembro(grupo_name: str, socio_name: str, *, rol: str) -> None:
	grupo = frappe.get_doc("Grupo Familiar", grupo_name)
	for fila in grupo.miembros or []:
		if fila.socio == socio_name and not fila.hasta:
			return
	grupo.append(
		"miembros",
		{
			"socio": socio_name,
			"rol": rol,
			"desde": today(),
		},
	)
	grupo.save(ignore_permissions=True)


def tutor_es_mayor_de_edad(fecha_nacimiento) -> bool:
	hoy = date.today()
	fn = getdate(fecha_nacimiento)
	edad = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
	return edad >= 18

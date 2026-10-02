"""Practicantes No Socio del gimnasio (spec gimnasio_cobro_socios_no_socios.md)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from club_management.members.doctype.socio.socio import CATEGORIA_NO_SOCIO, Socio
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)

SOCIO_DOCTYPE = "Socio"
INSCRIPCION_DOCTYPE = "Inscripcion Actividad"
ACTIVIDAD_GIMNASIO = "Gimnasio Fitness"
CONDICION_SOCIO = "Socio"
CONDICION_NO_SOCIO = "No Socio"
GRUPO_GIMNASIO_NO_SOCIO = f"{ACTIVIDAD_GIMNASIO} / {CONDICION_NO_SOCIO}"
GRUPO_GIMNASIO_SOCIO = f"{ACTIVIDAD_GIMNASIO} / {CONDICION_SOCIO}"
CATEGORIAS_NO_CONVERTIBLES = frozenset({CATEGORIA_NO_SOCIO, "Vitalicio"})


def es_no_socio(socio_name: str | None) -> bool:
	if not socio_name:
		return False
	return frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "categoria") == CATEGORIA_NO_SOCIO


def grupo_gimnasio_por_condicion(condicion: str) -> str | None:
	"""Grupo habilitado del gimnasio marcado con `condicion_socio`."""
	grupo = frappe.db.get_value(
		"Grupo Actividad",
		{"actividad": ACTIVIDAD_GIMNASIO, "condicion_socio": condicion, "habilitada": 1},
		"name",
	)
	if grupo:
		return grupo
	fallback = f"{ACTIVIDAD_GIMNASIO} / {condicion}"
	return fallback if frappe.db.exists("Grupo Actividad", fallback) else None


def crear_practicante_no_socio(datos: dict[str, Any], *, inscribir_gimnasio: bool = True) -> str:
	"""Alta de practicante No Socio: serie NS, activo e inscripto al gimnasio (grupo No Socio)."""
	ensure_secretaria_operacion_access()
	if not isinstance(datos, dict):
		frappe.throw(_("Datos de alta inválidos."), frappe.ValidationError)

	from club_management.members.services.socio_alta_secretaria import crear_socio_desk

	payload = dict(datos)
	payload["categoria"] = CATEGORIA_NO_SOCIO
	payload.pop("numero_socio", None)
	payload.pop("tipo_tutor", None)
	payload.pop("tutor", None)

	selecciones = None
	if inscribir_gimnasio:
		grupo = grupo_gimnasio_por_condicion(CONDICION_NO_SOCIO)
		if not grupo:
			frappe.throw(_("No está configurado el grupo No Socio del gimnasio."), frappe.ValidationError)
		selecciones = [{"actividad": ACTIVIDAD_GIMNASIO, "grupo": grupo}]

	ex_socio = frappe.db.get_value(
		SOCIO_DOCTYPE,
		{"dni": (payload.get("dni") or "").strip(), "estado": "Baja"},
		"name",
	)
	if ex_socio:
		return _reingresar_ex_socio_como_no_socio(ex_socio, payload, selecciones)

	return crear_socio_desk(
		payload,
		activar_al_guardar=True,
		selecciones_inscripcion=selecciones,
	)


_CAMPOS_NO_ACTUALIZABLES_REINGRESO = frozenset({"dni", "categoria", "numero_socio", "tipo_tutor", "tutor"})


def _reingresar_ex_socio_como_no_socio(
	socio_name: str,
	payload: dict[str, Any],
	selecciones: list[dict[str, Any]] | None,
) -> str:
	"""Reutiliza la ficha del ex socio dado de baja como practicante No Socio (conserva historial y `name`)."""
	from club_management.members.services.cobranza_manual import (
		ensure_customer_for_socio,
		erpnext_cobranza_disponible,
	)
	from club_management.members.services.socio_transitions import cambiar_estado

	socio = frappe.get_doc(SOCIO_DOCTYPE, socio_name)
	for campo, valor in payload.items():
		if campo in _CAMPOS_NO_ACTUALIZABLES_REINGRESO or valor in (None, ""):
			continue
		if socio.meta.has_field(campo):
			socio.set(campo, valor)
	socio.categoria = CATEGORIA_NO_SOCIO
	socio.save(ignore_permissions=True)

	cambiar_estado(socio_name, "Activo", motivo=_("Reingreso como practicante No Socio"))
	if erpnext_cobranza_disponible():
		ensure_customer_for_socio(socio_name, skip_permission_check=True)

	if selecciones:
		from club_management.activities.services.inscripcion_socio import inscribir_actividades_desk

		inscribir_actividades_desk(socio_name, selecciones)
	return socio_name


def convertir_no_socio_a_socio(socio_name: str, *, categoria: str) -> str:
	"""Pasa un practicante NS a socio con `categoria`.

	Un NS de serie `NS-` se renombra al próximo número de socio; un ex socio que había
	reingresado como NS conserva su número. Las inscripciones activas al grupo No Socio
	del gimnasio pasan al grupo Socio.
	"""
	ensure_secretaria_operacion_access()
	if not frappe.db.exists(SOCIO_DOCTYPE, socio_name):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)
	if not es_no_socio(socio_name):
		frappe.throw(_("Solo se pueden convertir practicantes No Socio."), frappe.ValidationError)

	opciones = (frappe.get_meta(SOCIO_DOCTYPE).get_field("categoria").options or "").split("\n")
	if not categoria or categoria not in opciones or categoria in CATEGORIAS_NO_CONVERTIBLES:
		frappe.throw(_("Categoría de socio inválida: {0}").format(categoria), frappe.ValidationError)

	if socio_name.isdigit():
		numero = int(socio_name)
		nuevo = socio_name
	else:
		numero = Socio._siguiente_numero_socio()
		nuevo = frappe.rename_doc(
			SOCIO_DOCTYPE,
			socio_name,
			str(numero),
			force=True,
			show_alert=False,
		)

	socio = frappe.get_doc(SOCIO_DOCTYPE, nuevo)
	socio.numero_socio = numero
	socio.categoria = categoria
	socio.save(ignore_permissions=True)

	_mover_inscripciones_gimnasio_a_socio(nuevo)
	_actualizar_nombre_customer(socio)

	from club_management.members.services.suscripciones_socio import (
		sync_suscripcion_cuota_al_validar_socio,
	)

	sync_suscripcion_cuota_al_validar_socio(nuevo)
	return nuevo


def _mover_inscripciones_gimnasio_a_socio(socio_name: str) -> None:
	grupo_socio = grupo_gimnasio_por_condicion(CONDICION_SOCIO)
	if not grupo_socio:
		return
	grupos_no_socio = frappe.get_all(
		"Grupo Actividad",
		filters={"condicion_socio": CONDICION_NO_SOCIO},
		pluck="name",
	)
	if not grupos_no_socio:
		return
	for name in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": socio_name, "estado": "Activa", "grupo_actividad": ["in", grupos_no_socio]},
		pluck="name",
	):
		ins = frappe.get_doc(INSCRIPCION_DOCTYPE, name)
		ins.grupo_actividad = grupo_socio
		ins.actividad = frappe.db.get_value("Grupo Actividad", grupo_socio, "actividad")
		ins.equipo_actividad = None
		ins.save(ignore_permissions=True)


def _actualizar_nombre_customer(socio: Socio) -> None:
	from club_management.members.services.cobranza_manual import (
		CUSTOMER_DOCTYPE,
		_campo_socio_en,
		erpnext_cobranza_disponible,
	)

	if not erpnext_cobranza_disponible():
		return
	campo = _campo_socio_en(CUSTOMER_DOCTYPE)
	if not campo:
		return
	customer = frappe.db.get_value(CUSTOMER_DOCTYPE, {campo: socio.name}, "name")
	if customer:
		frappe.db.set_value(
			CUSTOMER_DOCTYPE,
			customer,
			"customer_name",
			f"{socio.apellido}, {socio.nombre} ({socio.name})",
		)

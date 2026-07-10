"""Alta manual de Socio desde Desk (Secretaría).

Spec: `club_management/specs/socio_alta_edicion_secretaria.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from club_management.members.services.cobranza_manual import (
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.socio_operaciones_secretaria import (
	activar_socio_manual,
	ensure_secretaria_operacion_access,
	omitir_pago_manual,
)
from club_management.members.services.contacto_domicilio import assert_contacto_alta_socio
from club_management.members.services.suscripciones_socio import sync_suscripcion_cuota_al_validar_socio

ESTADO_ALTA_MANUAL = "Pendiente de Pago"
MSG_DNI_YA_SOCIO = _("DNI ya registrado como Socio")

_CAMPOS_ALTA = (
	"numero_socio",
	"nombre",
	"apellido",
	"dni",
	"nacionalidad",
	"fecha_nacimiento",
	"genero",
	"email",
	"telefono_fijo",
	"telefono_movil",
	"calle",
	"numero",
	"piso",
	"departamento",
	"provincia",
	"ciudad",
	"localidad_barrio",
	"codigo_postal",
	"categoria",
	"foto_perfil",
	"dni_frente",
	"dni_dorso",
	"ficha_medica",
	"tipo_tutor",
	"tutor",
	"grupo_familiar",
)

_CAMPOS_OBLIGATORIOS_ALTA = (
	"nombre",
	"apellido",
	"dni",
	"nacionalidad",
	"fecha_nacimiento",
	"genero",
	"email",
	"telefono_movil",
	"categoria",
)

_EDAD_MENOR = 18


def sugerir_categoria_por_fecha_nacimiento(fecha_nacimiento: str | Any) -> str:
	"""Sugiere categoría según edad (alta guiada Desk)."""
	from frappe.utils import getdate

	hoy = getdate()
	nac = getdate(fecha_nacimiento)
	edad = hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
	if edad < _EDAD_MENOR:
		return "Menor"
	return "Activo"


def crear_socio_desk(
	datos: dict[str, Any],
	*,
	activar_al_guardar: bool = False,
	omitir_pago_al_guardar: bool = False,
	selecciones_inscripcion: list[dict[str, Any]] | None = None,
) -> str:
	"""Crea un `Socio` desde Desk con flujo guiado opcional (activar / inscribir)."""
	ensure_secretaria_operacion_access()
	payload = _normalizar_datos_alta(datos)
	_assert_dni_disponible(payload["dni"])

	socio = frappe.get_doc(
		{
			"doctype": "Socio",
			**payload,
			"estado": ESTADO_ALTA_MANUAL,
		}
	)
	socio.insert(ignore_permissions=True, ignore_mandatory=True)

	if erpnext_cobranza_disponible():
		ensure_customer_for_socio(socio.name, skip_permission_check=True)

	sync_suscripcion_cuota_al_validar_socio(socio.name)

	if omitir_pago_al_guardar and not activar_al_guardar:
		omitir_pago_manual(socio.name, motivo="Alta guiada sin pago online")
	if activar_al_guardar:
		activar_socio_manual(socio.name, motivo="Activación al guardar alta guiada")

	if selecciones_inscripcion:
		from club_management.activities.services.inscripcion_socio import (
			inscribir_actividades_desk,
		)

		inscribir_actividades_desk(socio.name, selecciones_inscripcion)

	return socio.name


def _normalizar_datos_alta(datos: dict[str, Any]) -> dict[str, Any]:
	if not isinstance(datos, dict):
		frappe.throw(_("Datos de alta inválidos."), frappe.ValidationError)

	payload: dict[str, Any] = {}
	for campo in _CAMPOS_ALTA:
		if campo in datos:
			payload[campo] = datos[campo]

	faltantes = [campo for campo in _CAMPOS_OBLIGATORIOS_ALTA if not payload.get(campo)]
	if faltantes:
		frappe.throw(
			_("Faltan datos obligatorios: {0}").format(", ".join(faltantes)),
			frappe.ValidationError,
		)

	if payload.get("categoria") == "Menor":
		for campo in ("tipo_tutor", "tutor"):
			if not payload.get(campo):
				frappe.throw(
					_("Menor: complete el tutor responsable."),
					frappe.ValidationError,
				)

	if payload.get("numero_socio") is not None and payload.get("numero_socio") != "":
		try:
			numero = int(payload["numero_socio"])
		except (TypeError, ValueError):
			frappe.throw(_("Número de socio inválido."), frappe.ValidationError)
		if numero <= 0:
			frappe.throw(_("El número de socio debe ser un entero positivo."), frappe.ValidationError)
		payload["numero_socio"] = numero
	else:
		payload.pop("numero_socio", None)

	assert_contacto_alta_socio(payload)
	return payload


def _assert_dni_disponible(dni: str) -> None:
	dni_limpio = (dni or "").strip()
	if not dni_limpio:
		frappe.throw(_("DNI es obligatorio."), frappe.ValidationError)
	if frappe.db.exists("Socio", {"dni": dni_limpio}):
		frappe.throw(MSG_DNI_YA_SOCIO, frappe.ValidationError)

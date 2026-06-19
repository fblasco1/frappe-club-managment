"""Validación de `Solicitud Asociacion` (transición workflow `Validar`).

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commit 4).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from club_management.members.services import grupo_familiar as gf
from club_management.members.services.solicitud_notificaciones import (
	enqueue_validacion_pago_email,
)
from club_management.members.services.contacto_domicilio import (
	map_socio_contacto_domicilio_desde_solicitud,
	map_tutor_contacto_domicilio_desde_solicitud,
)
from club_management.members.services.suscripciones_socio import sync_suscripcion_cuota_al_validar_socio
from club_management.members.services.user_provisioning import (
	provision_user_for_socio,
	provision_user_for_tutor_no_socio,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	STATE_VALIDADA,
)

ESTADO_SOCIO_TRAS_VALIDAR = "Pendiente de Pago"
CATEGORIA_MENOR = "Menor"
ROL_MIEMBRO_MENOR = "Hijo"

MSG_EMAIL_ADULTO_TOMADO = _(
	"El email ya tiene cuenta en el portal; pedí al solicitante un email distinto"
)
MSG_EMAIL_MENOR_TOMADO = _(
	"El email del menor ya tiene cuenta en el portal; usá el mismo email del tutor o pedí al solicitante uno distinto"
)
MSG_DNI_YA_SOCIO = _("DNI ya registrado como Socio")
MSG_DNI_YA_TNS = _(
	"DNI ya está registrado como Tutor No Socio; Secretaría debe migrar manualmente el registro a Socio antes de validar"
)
MSG_TUTOR_MENOR_EDAD = _("Tutor debe ser mayor de 18 años")

CAMPOS_TUTOR_OBLIGATORIOS = (
	"dni_tutor",
	"nombre_tutor",
	"apellido_tutor",
	"fecha_nacimiento_tutor",
	"email_tutor",
	"telefono_movil_tutor",
	"rol_tutor",
)


def ejecutar_validacion_desde_solicitud(solicitud: Document) -> None:
	"""Crea entidades de dominio al pasar la solicitud a `Validada` (idempotente)."""
	if solicitud.socio_generado:
		return
	if solicitud.workflow_state != STATE_VALIDADA:
		return

	if solicitud.categoria_solicitada == CATEGORIA_MENOR:
		_validar_menor(solicitud)
	else:
		_validar_adulto(solicitud)


def _validar_adulto(solicitud: Document) -> None:
	_assert_dni_no_socio(solicitud.dni)
	_assert_dni_no_tns_para_adulto(solicitud.dni)
	_assert_email_disponible(solicitud.email, mensaje=MSG_EMAIL_ADULTO_TOMADO)
	_assert_username_disponible(solicitud.dni, mensaje=MSG_EMAIL_ADULTO_TOMADO)

	socio = _insert_socio_desde_solicitud(solicitud, categoria=solicitud.categoria_solicitada)
	user_name = provision_user_for_socio(socio.name)
	grupo_name = gf.ensure_grupo_for_socio(socio, solicitud=solicitud)

	_finalize_solicitud(
		solicitud,
		socio_name=socio.name,
		user_name=user_name,
		grupo_name=grupo_name,
		email_destino=solicitud.email,
	)


def _validar_menor(solicitud: Document) -> None:
	_assert_datos_tutor_completos(solicitud)
	_assert_dni_no_socio(solicitud.dni)

	if not gf.tutor_es_mayor_de_edad(solicitud.fecha_nacimiento_tutor):
		frappe.throw(MSG_TUTOR_MENOR_EDAD, frappe.ValidationError)

	socio_tutor = frappe.db.get_value("Socio", {"dni": solicitud.dni_tutor}, "name")
	tns_tutor = frappe.db.get_value("Tutor No Socio", {"dni": solicitud.dni_tutor}, "name")

	if socio_tutor:
		_validar_menor_con_tutor_socio(solicitud, socio_tutor)
	elif tns_tutor:
		_validar_menor_con_tutor_tns_existente(solicitud, tns_tutor)
	else:
		_validar_menor_con_tutor_nuevo_tns(solicitud)


def _validar_menor_con_tutor_socio(solicitud: Document, socio_tutor: str) -> None:
	tutor_doc = frappe.get_doc("Socio", socio_tutor)
	if not gf.tutor_es_mayor_de_edad(tutor_doc.fecha_nacimiento):
		frappe.throw(MSG_TUTOR_MENOR_EDAD, frappe.ValidationError)

	grupo_name = gf.find_active_grupo_for_titular("Socio", socio_tutor)
	if not grupo_name:
		frappe.throw(_("Tutor debe ser titular activo de un Grupo Familiar"))

	email_menor = (solicitud.email or "").strip()
	email_tutor = (solicitud.email_tutor or "").strip()
	comparten_email = email_menor.lower() == email_tutor.lower()

	user_menor = ""
	if not comparten_email:
		_assert_email_disponible(email_menor, mensaje=MSG_EMAIL_MENOR_TOMADO)
		_assert_username_disponible(solicitud.dni, mensaje=MSG_EMAIL_MENOR_TOMADO)

	socio_menor = _insert_socio_desde_solicitud(
		solicitud,
		categoria=CATEGORIA_MENOR,
		tipo_tutor="Socio",
		tutor=socio_tutor,
		grupo_familiar=grupo_name,
	)
	if not comparten_email:
		user_menor = provision_user_for_socio(socio_menor.name)

	gf.ensure_grupo_for_socio(
		socio_menor,
		tutor_tipo="Socio",
		tutor_name=socio_tutor,
		rol_miembro=ROL_MIEMBRO_MENOR,
	)

	_finalize_solicitud(
		solicitud,
		socio_name=socio_menor.name,
		user_name=user_menor,
		grupo_name=grupo_name,
		email_destino=email_tutor,
	)


def _validar_menor_con_tutor_tns_existente(solicitud: Document, tns_name: str) -> None:
	tutor_doc = frappe.get_doc("Tutor No Socio", tns_name)
	if not gf.tutor_es_mayor_de_edad(tutor_doc.fecha_nacimiento):
		frappe.throw(MSG_TUTOR_MENOR_EDAD, frappe.ValidationError)

	grupo_name = gf.find_active_grupo_for_titular("Tutor No Socio", tns_name)
	if not grupo_name:
		frappe.throw(_("Tutor debe ser titular activo de un Grupo Familiar"))

	email_menor = (solicitud.email or "").strip()
	email_tutor = (solicitud.email_tutor or "").strip()
	comparten_email = email_menor.lower() == email_tutor.lower()

	user_menor = ""
	if not comparten_email:
		_assert_email_disponible(email_menor, mensaje=MSG_EMAIL_MENOR_TOMADO)
		_assert_username_disponible(solicitud.dni, mensaje=MSG_EMAIL_MENOR_TOMADO)

	socio_menor = _insert_socio_desde_solicitud(
		solicitud,
		categoria=CATEGORIA_MENOR,
		tipo_tutor="Tutor No Socio",
		tutor=tns_name,
		grupo_familiar=grupo_name,
	)
	if not comparten_email:
		user_menor = provision_user_for_socio(socio_menor.name)

	gf.ensure_grupo_for_socio(
		socio_menor,
		tutor_tipo="Tutor No Socio",
		tutor_name=tns_name,
		rol_miembro=ROL_MIEMBRO_MENOR,
	)

	_finalize_solicitud(
		solicitud,
		socio_name=socio_menor.name,
		user_name=user_menor,
		grupo_name=grupo_name,
		email_destino=email_tutor,
	)


def _validar_menor_con_tutor_nuevo_tns(solicitud: Document) -> None:
	_assert_dni_no_tns_para_adulto(solicitud.dni_tutor)
	email_tutor = (solicitud.email_tutor or "").strip()
	email_menor = (solicitud.email or "").strip()
	comparten_email = email_menor.lower() == email_tutor.lower()

	if not comparten_email:
		_assert_email_disponible(email_menor, mensaje=MSG_EMAIL_MENOR_TOMADO)
	_assert_email_disponible(email_tutor, mensaje=MSG_EMAIL_ADULTO_TOMADO)
	_assert_username_disponible(solicitud.dni_tutor, mensaje=MSG_EMAIL_ADULTO_TOMADO)
	if not comparten_email:
		_assert_username_disponible(solicitud.dni, mensaje=MSG_EMAIL_MENOR_TOMADO)

	tns = _insert_tutor_desde_solicitud(solicitud)
	provision_user_for_tutor_no_socio(tns.name)
	grupo = gf.create_grupo_for_tutor_no_socio(
		tns.name,
		rol_titular=solicitud.rol_tutor or "Padre",
		apellido_principal=solicitud.apellido_tutor,
	)

	socio_menor = _insert_socio_desde_solicitud(
		solicitud,
		categoria=CATEGORIA_MENOR,
		tipo_tutor="Tutor No Socio",
		tutor=tns.name,
		grupo_familiar=grupo.name,
	)
	user_menor = ""
	if not comparten_email:
		user_menor = provision_user_for_socio(socio_menor.name)

	gf.ensure_grupo_for_socio(
		socio_menor,
		tutor_tipo="Tutor No Socio",
		tutor_name=tns.name,
		rol_miembro=ROL_MIEMBRO_MENOR,
	)

	_finalize_solicitud(
		solicitud,
		socio_name=socio_menor.name,
		user_name=user_menor,
		grupo_name=grupo.name,
		email_destino=email_tutor,
	)


def _finalize_solicitud(
	solicitud: Document,
	*,
	socio_name: str,
	user_name: str,
	grupo_name: str,
	email_destino: str,
) -> None:
	solicitud.socio_generado = socio_name
	solicitud.user_generado = user_name or ""
	solicitud.grupo_familiar_generado = grupo_name
	sync_suscripcion_cuota_al_validar_socio(socio_name)
	enqueue_validacion_pago_email(solicitud.name, email_destino)


def _insert_socio_desde_solicitud(
	solicitud: Document,
	*,
	categoria: str,
	tipo_tutor: str = "",
	tutor: str = "",
	grupo_familiar: str = "",
) -> Document:
	payload = {
		"doctype": "Socio",
		"nombre": solicitud.nombre,
		"apellido": solicitud.apellido,
		"dni": solicitud.dni,
		"nacionalidad": solicitud.nacionalidad,
		"fecha_nacimiento": solicitud.fecha_nacimiento,
		"genero": solicitud.genero,
		**map_socio_contacto_domicilio_desde_solicitud(solicitud),
		"categoria": categoria,
		"estado": ESTADO_SOCIO_TRAS_VALIDAR,
		"solicitud_origen": solicitud.name,
		"foto_perfil": solicitud.foto_perfil,
		"dni_frente": solicitud.dni_frente,
		"dni_dorso": solicitud.dni_dorso,
		"ficha_medica": solicitud.ficha_medica,
		"tipo_tutor": tipo_tutor,
		"tutor": tutor,
		"grupo_familiar": grupo_familiar,
	}
	socio = frappe.get_doc(payload)
	socio.insert(ignore_permissions=True)
	return socio


def _insert_tutor_desde_solicitud(solicitud: Document) -> Document:
	tutor = frappe.get_doc(
		{
			"doctype": "Tutor No Socio",
			"nombre": solicitud.nombre_tutor,
			"apellido": solicitud.apellido_tutor,
			"dni": solicitud.dni_tutor,
			"nacionalidad": solicitud.nacionalidad_tutor or solicitud.nacionalidad,
			"fecha_nacimiento": solicitud.fecha_nacimiento_tutor,
			"genero": solicitud.genero_tutor,
			**map_tutor_contacto_domicilio_desde_solicitud(solicitud),
		}
	)
	tutor.insert(ignore_permissions=True)
	return tutor


def _assert_dni_no_socio(dni: str) -> None:
	if frappe.db.exists("Socio", {"dni": dni}):
		frappe.throw(MSG_DNI_YA_SOCIO, frappe.ValidationError)


def _assert_dni_no_tns_para_adulto(dni: str) -> None:
	if frappe.db.exists("Tutor No Socio", {"dni": dni}):
		frappe.throw(MSG_DNI_YA_TNS, frappe.ValidationError)


def _assert_email_disponible(email: str, *, mensaje: str) -> None:
	if email and frappe.db.exists("User", email):
		frappe.throw(mensaje, frappe.ValidationError)


def _assert_username_disponible(username: str, *, mensaje: str) -> None:
	if username and frappe.db.exists("User", {"username": username}):
		frappe.throw(mensaje, frappe.ValidationError)


def _assert_datos_tutor_completos(solicitud: Document) -> None:
	for campo in CAMPOS_TUTOR_OBLIGATORIOS:
		valor = solicitud.get(campo)
		if campo == "fecha_nacimiento_tutor":
			if not valor:
				frappe.throw(
					_("Datos del tutor incompletos: `{0}` es obligatorio").format(campo),
					frappe.ValidationError,
				)
			continue
		if not (str(valor).strip() if valor is not None else ""):
			frappe.throw(
				_("Datos del tutor incompletos: `{0}` es obligatorio").format(campo),
				frappe.ValidationError,
			)

"""Adjuntos vigentes de Socio y Tutor No Socio: privados, propios, pisa al renovar.

Spec: `club_management/specs/almacenamiento_documentacion_socios.md`.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

import frappe
from frappe.utils.file_manager import save_file_on_filesystem

CAMPOS_SOCIO: tuple[str, ...] = (
	"foto_perfil",
	"dni_frente",
	"dni_dorso",
	"ficha_medica",
	"comprobante_jubilado",
)

CAMPOS_TUTOR: tuple[str, ...] = (
	"foto_perfil",
	"dni_frente",
	"dni_dorso",
)

MAPA_SOLICITUD_SOCIO: tuple[tuple[str, str], ...] = (
	("foto_perfil", "foto_perfil"),
	("dni_frente", "dni_frente"),
	("dni_dorso", "dni_dorso"),
	("ficha_medica", "ficha_medica"),
	("comprobante_jubilado", "comprobante_jubilado"),
)

MAPA_SOLICITUD_TUTOR: tuple[tuple[str, str], ...] = (
	("foto_perfil_tutor", "foto_perfil"),
	("dni_frente_tutor", "dni_frente"),
	("dni_dorso_tutor", "dni_dorso"),
)


def _file_por_url(file_url: str) -> Any | None:
	if not file_url:
		return None
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		return None
	return frappe.get_doc("File", name)


def _es_propio(file_doc: Any, dt: str, dn: str, fieldname: str) -> bool:
	return (
		file_doc.attached_to_doctype == dt
		and str(file_doc.attached_to_name) == str(dn)
		and (not file_doc.attached_to_field or file_doc.attached_to_field == fieldname)
	)


def _ensure_privado(file_doc: Any) -> None:
	if int(file_doc.is_private or 0) == 1:
		return
	file_doc.is_private = 1
	file_doc.save(ignore_permissions=True)


def clonar_adjunto_privado(file_url: str, dt: str, dn: str, fieldname: str) -> str:
	"""Devuelve una URL de File privado adjunto a `dt/dn/fieldname`.

	Si no hay `File` (paths dummy de tests), se deja la URL original.
	Si el mismo blob ya está en otro documento, se clona para no compartir.
	"""
	if not file_url:
		return ""
	src = _file_por_url(file_url)
	if not src:
		return file_url
	if _es_propio(src, dt, dn, fieldname):
		_ensure_privado(src)
		return src.file_url

	try:
		content = src.get_content()
	except Exception:
		return file_url

	return _guardar_copia_propia(
		content, src.file_name or "adjunto", dt, dn, fieldname
	)


def _guardar_copia_propia(
	content: bytes | str, original_name: str, dt: str, dn: str, fieldname: str
) -> str:
	"""Escribe un blob nuevo en disco para no compartir File ni file_url."""
	base = os.path.basename(original_name or "adjunto")
	safe = re.sub(r"[^A-Za-z0-9._-]", "_", base) or "adjunto"
	fname = f"{dn}_{fieldname}_{uuid.uuid4().hex[:10]}_{safe}"
	file_data = save_file_on_filesystem(fname, content, is_private=1)
	cloned = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_data["file_name"],
			"file_url": file_data["file_url"],
			"folder": "Home",
			"is_private": 1,
			"attached_to_doctype": dt,
			"attached_to_name": str(dn),
			"attached_to_field": fieldname,
		}
	)
	cloned.insert(ignore_permissions=True)
	return cloned.file_url


def vincular_adjuntos(doc: Any, mapping: dict[str, str]) -> None:
	"""Clona cada URL al documento y actualiza el campo Attach."""
	if not doc or not doc.name:
		return
	for fieldname, url in mapping.items():
		if not url:
			continue
		nuevo = clonar_adjunto_privado(url, doc.doctype, doc.name, fieldname)
		if nuevo != (doc.get(fieldname) or ""):
			doc.db_set(fieldname, nuevo, update_modified=False)
		doc.set(fieldname, nuevo)


def mapping_desde_solicitud_socio(solicitud: Any) -> dict[str, str]:
	return {
		destino: (solicitud.get(origen) or "")
		for origen, destino in MAPA_SOLICITUD_SOCIO
	}


def mapping_desde_solicitud_tutor(solicitud: Any) -> dict[str, str]:
	return {
		destino: (solicitud.get(origen) or "")
		for origen, destino in MAPA_SOLICITUD_TUTOR
	}


def vincular_adjuntos_del_doc(doc: Any, campos: tuple[str, ...]) -> None:
	vincular_adjuntos(doc, {campo: (doc.get(campo) or "") for campo in campos})


def asegurar_adjuntos_privados(doc: Any, campos: tuple[str, ...]) -> None:
	"""En un save de documento ya persistido, clona URLs que aún no son propias."""
	if doc.is_new() or not doc.name:
		return
	for campo in campos:
		url = doc.get(campo) or ""
		if not url:
			continue
		nuevo = clonar_adjunto_privado(url, doc.doctype, doc.name, campo)
		if nuevo != url:
			doc.set(campo, nuevo)


def completar_docs_tutor_si_vacios(tutor: Any, solicitud: Any) -> None:
	"""Rellena adjuntos de un TNS existente solo si aún no tiene ninguno."""
	if tutor.doctype != "Tutor No Socio":
		return
	if any(tutor.get(campo) for campo in CAMPOS_TUTOR):
		return
	vincular_adjuntos(tutor, mapping_desde_solicitud_tutor(solicitud))


def pisa_adjuntos_reemplazados(doc: Any, campos: tuple[str, ...]) -> None:
	"""Borra el File anterior cuando un Attach vigente cambia."""
	if doc.is_new():
		return
	previo = doc.get_doc_before_save()
	if not previo:
		return
	for campo in campos:
		old_url = previo.get(campo) or ""
		new_url = doc.get(campo) or ""
		if old_url and old_url != new_url:
			_borrar_file_reemplazado(old_url, doc.doctype, doc.name)


def _borrar_file_reemplazado(file_url: str, dt: str, dn: str) -> None:
	nombres = frappe.get_all(
		"File",
		filters={"file_url": file_url},
		pluck="name",
	)
	for name in nombres:
		file_doc = frappe.get_doc("File", name)
		ajeno = (
			file_doc.attached_to_doctype
			and file_doc.attached_to_name
			and not (
				file_doc.attached_to_doctype == dt
				and str(file_doc.attached_to_name) == str(dn)
			)
		)
		if ajeno:
			continue
		try:
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
		except Exception:
			frappe.log_error(title="documentacion_adjuntos: no se pudo borrar File")

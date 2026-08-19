"""Gestión de documentación de socios nuevos y tutores.

Spec: `almacenamiento_documentacion_socios.md`, `tutor_no_socio_minimo.md`.
"""

from __future__ import annotations

import secrets

import frappe

from club_management.members.test_helpers import (
	MINIMAL_VALID_PDF,
	MembersTestCase,
	adult_birthdate,
	ensure_role_socio_exists,
	insert_socio,
	insert_solicitud_asociacion,
	make_solicitud_menor_payload,
	make_test_file,
	minor_birthdate,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)

SOLICITUD = "Solicitud Asociacion"
PDF_B: bytes = MINIMAL_VALID_PDF.replace(b"%PDF-1.0", b"%PDF-1.1")


def _rand_dni() -> str:
	return str(secrets.randbelow(90_000_000) + 10_000_000)


def _file_of(url: str) -> dict | None:
	if not url:
		return None
	return frappe.db.get_value(
		"File",
		{"file_url": url},
		["name", "is_private", "attached_to_doctype", "attached_to_name"],
		as_dict=True,
	)


class TestDocumentacionMeta(MembersTestCase):
	def test_socio_tiene_comprobante_jubilado(self) -> None:
		self.assertIsNotNone(frappe.get_meta("Socio").get_field("comprobante_jubilado"))

	def test_tutor_tiene_adjuntos_dni_y_foto(self) -> None:
		meta = frappe.get_meta("Tutor No Socio")
		for fname in ("foto_perfil", "dni_frente", "dni_dorso"):
			self.assertIsNotNone(meta.get_field(fname), fname)


class TestDocumentacionAlValidar(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()
		ensure_role_socio_exists()

	def _validar(self, name: str) -> None:
		doc = frappe.get_doc(SOLICITUD, name)
		doc.workflow_state = STATE_VALIDADA
		doc.save(ignore_permissions=True)

	def test_adulto_recibe_adjuntos_privados_propios(self) -> None:
		dni = _rand_dni()
		ficha = make_test_file(f"doc_ficha_{dni}.pdf", MINIMAL_VALID_PDF)
		frente = make_test_file(f"doc_frente_{dni}.pdf", MINIMAL_VALID_PDF)
		sol = insert_solicitud_asociacion(
			dni=dni,
			email=f"doc.act.{dni}@example.com",
			ficha_medica=ficha,
			dni_frente=frente,
		)
		self._validar(sol.name)

		sol.reload()
		socio = frappe.get_doc("Socio", sol.socio_generado)
		self.assertTrue(socio.ficha_medica)
		self.assertTrue(socio.dni_frente)
		meta = _file_of(socio.ficha_medica)
		self.assertIsNotNone(meta)
		self.assertEqual(int(meta.is_private), 1)
		self.assertEqual(meta.attached_to_doctype, "Socio")
		self.assertEqual(str(meta.attached_to_name), str(socio.name))

	def test_jubilado_copia_comprobante(self) -> None:
		dni = _rand_dni()
		ficha = make_test_file(f"doc_jub_ficha_{dni}.pdf", MINIMAL_VALID_PDF)
		comp = make_test_file(f"doc_jub_comp_{dni}.pdf", PDF_B)
		sol = insert_solicitud_asociacion(
			dni=dni,
			email=f"doc.jub.{dni}@example.com",
			categoria_solicitada="Jubilado",
			ficha_medica=ficha,
			comprobante_jubilado=comp,
		)
		self._validar(sol.name)
		socio = frappe.get_doc("Socio", frappe.db.get_value(SOLICITUD, sol.name, "socio_generado"))
		self.assertEqual(socio.categoria, "Jubilado")
		self.assertTrue(socio.comprobante_jubilado)
		meta = _file_of(socio.comprobante_jubilado)
		self.assertIsNotNone(meta)
		self.assertEqual(meta.attached_to_doctype, "Socio")

	def test_menor_copia_documentos_al_tutor_nuevo(self) -> None:
		dni_menor = _rand_dni()
		dni_tutor = _rand_dni()
		ficha = make_test_file(f"doc_men_ficha_{dni_menor}.pdf", MINIMAL_VALID_PDF)
		frente_t = make_test_file(f"doc_tut_frente_{dni_tutor}.pdf", MINIMAL_VALID_PDF)
		dorso_t = make_test_file(f"doc_tut_dorso_{dni_tutor}.pdf", PDF_B)
		foto_t = make_test_file(f"doc_tut_foto_{dni_tutor}.pdf", MINIMAL_VALID_PDF)
		payload = make_solicitud_menor_payload(
			dni=dni_menor,
			email=f"doc.men.{dni_menor}@example.com",
			fecha_nacimiento=minor_birthdate(12),
			ficha_medica=ficha,
			dni_tutor=dni_tutor,
			email_tutor=f"doc.tut.{dni_tutor}@example.com",
			dni_frente_tutor=frente_t,
			dni_dorso_tutor=dorso_t,
			foto_perfil_tutor=foto_t,
		)
		sol = frappe.get_doc(payload)
		sol.insert(ignore_permissions=True)
		self._validar(sol.name)

		sol.reload()
		menor = frappe.get_doc("Socio", sol.socio_generado)
		self.assertEqual(menor.tipo_tutor, "Tutor No Socio")
		tutor = frappe.get_doc("Tutor No Socio", menor.tutor)
		self.assertTrue(tutor.dni_frente)
		self.assertTrue(tutor.dni_dorso)
		self.assertTrue(tutor.foto_perfil)
		meta = _file_of(tutor.dni_frente)
		self.assertIsNotNone(meta)
		self.assertEqual(int(meta.is_private), 1)
		self.assertEqual(meta.attached_to_doctype, "Tutor No Socio")
		self.assertEqual(meta.attached_to_name, tutor.name)


class TestDocumentacionPisa(MembersTestCase):
	def test_renovar_ficha_borra_archivo_anterior(self) -> None:
		dni = _rand_dni()
		vieja = make_test_file(f"pisa_old_{dni}.pdf", MINIMAL_VALID_PDF)
		nueva = make_test_file(f"pisa_new_{dni}.pdf", PDF_B)
		socio = insert_socio(
			dni=dni,
			email=f"pisa.{dni}@example.com",
			ficha_medica=vieja,
		)
		# La ficha de alta puede haberse clonado; tomar la URL vigente.
		socio.reload()
		url_vieja = socio.ficha_medica
		nombre_viejo = frappe.db.get_value("File", {"file_url": url_vieja}, "name")
		self.assertTrue(nombre_viejo)

		socio.ficha_medica = nueva
		socio.save(ignore_permissions=True)
		socio.reload()

		self.assertFalse(frappe.db.exists("File", nombre_viejo))
		self.assertTrue(socio.ficha_medica)
		self.assertNotEqual(socio.ficha_medica, url_vieja)
		meta = _file_of(socio.ficha_medica)
		self.assertIsNotNone(meta)
		self.assertEqual(meta.attached_to_doctype, "Socio")

	def test_renovar_dni_tutor_pisa(self) -> None:
		from club_management.members.test_helpers import insert_tutor_no_socio

		dni = _rand_dni()
		vieja = make_test_file(f"tns_old_{dni}.pdf", MINIMAL_VALID_PDF)
		nueva = make_test_file(f"tns_new_{dni}.pdf", PDF_B)
		tutor = insert_tutor_no_socio(
			dni=dni,
			email=f"pisa.tns.{dni}@example.com",
			dni_frente=vieja,
		)
		tutor.reload()
		url_vieja = tutor.dni_frente
		nombre_viejo = frappe.db.get_value("File", {"file_url": url_vieja}, "name")
		self.assertTrue(nombre_viejo)

		tutor.dni_frente = nueva
		tutor.save(ignore_permissions=True)
		tutor.reload()
		self.assertFalse(frappe.db.exists("File", nombre_viejo))
		self.assertTrue(tutor.dni_frente)
		self.assertNotEqual(tutor.dni_frente, url_vieja)
		meta = _file_of(tutor.dni_frente)
		self.assertIsNotNone(meta)
		self.assertEqual(meta.attached_to_doctype, "Tutor No Socio")

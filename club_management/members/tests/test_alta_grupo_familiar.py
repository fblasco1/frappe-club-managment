"""Alta pública multi-persona con grupo familiar.

Spec: `club_management/specs/portal_alta_grupo_familiar.md`
"""

from __future__ import annotations

import secrets
from typing import Any

import frappe

from club_management.members.api.alta_grupo_publica import (
	_consultar_alta_grupo_impl,
	_submit_alta_grupo_impl,
)
from club_management.members.services.alta_grupo_familiar import (
	MSG_TITULAR_SIN_VALIDAR,
)
from club_management.members.test_helpers import (
	DUMMY_DNI_DORSO,
	DUMMY_DNI_FRENTE,
	DUMMY_FOTO_PERFIL,
	MINIMAL_VALID_PDF,
	MembersTestCase,
	adult_birthdate,
	ensure_role_socio_exists,
	make_test_file,
	minor_birthdate,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	STATE_PENDIENTE,
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)

TRAMITE_DOCTYPE = "Solicitud Grupo Familiar"
SOLICITUD_DOCTYPE = "Solicitud Asociacion"


def _rand_dni() -> str:
	return str(secrets.randbelow(90_000_000) + 10_000_000)


class TestAltaGrupoFamiliar(MembersTestCase):
	"""Wizard multi-persona del portal (estilo Sportivo Pilar)."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()
		ensure_role_socio_exists()

	def setUp(self) -> None:
		super().setUp()
		self.sufijo = secrets.token_hex(4)
		# El endpoint lee la ficha médica del disco (magic numbers), así que
		# necesita un archivo real, no una ruta simbólica.
		self.ficha_medica = make_test_file(
			f"qa_ficha_{self.sufijo}.pdf", MINIMAL_VALID_PDF
		)
		self.act_basquet = self._ensure_actividad(f"QA Basquet {self.sufijo}")
		self.act_futbol = self._ensure_actividad(f"QA Futbol {self.sufijo}")
		self.act_voley = self._ensure_actividad(f"QA Voley {self.sufijo}")

	def _ensure_actividad(self, titulo: str, *, habilitada: int = 1) -> str:
		existente = frappe.db.get_value("Actividad", {"titulo": titulo}, "name")
		if existente:
			frappe.db.set_value("Actividad", existente, "habilitada", habilitada)
			return existente
		doc = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": titulo,
				"habilitada": habilitada,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _persona(self, **overrides: Any) -> dict[str, Any]:
		dni = _rand_dni()
		payload: dict[str, Any] = {
			"nombre": "Ana",
			"apellido": "Pérez",
			"dni": dni,
			"nacionalidad": "Argentina",
			"fecha_nacimiento": str(adult_birthdate(35)),
			"genero": "Femenino",
			"categoria_solicitada": "Activo",
			"email": f"qa.{dni}@example.com",
			"telefono_movil": "+541112345678",
			"calle": "Falsa",
			"numero": "123",
			"provincia": "Buenos Aires",
			"ciudad": "Pilar",
			"localidad_barrio": "Pilar Centro",
			"codigo_postal": "1629",
			"dni_frente": DUMMY_DNI_FRENTE,
			"dni_dorso": DUMMY_DNI_DORSO,
			"foto_perfil": DUMMY_FOTO_PERFIL,
			"ficha_medica": self.ficha_medica,
		}
		payload.update(overrides)
		return payload

	def _solicitudes_del_tramite(self, tramite: str) -> list[dict[str, Any]]:
		return frappe.get_all(
			SOLICITUD_DOCTYPE,
			filters={"solicitud_grupo": tramite},
			fields=["name", "nombre", "rol_en_grupo", "workflow_state", "sin_actividad"],
			order_by="creation asc",
		)

	def _validar(self, solicitud_name: str) -> None:
		doc = frappe.get_doc(SOLICITUD_DOCTYPE, solicitud_name)
		doc.workflow_state = STATE_VALIDADA
		doc.save(ignore_permissions=True)

	# ------------------------------------------------------------------
	# Alta del trámite
	# ------------------------------------------------------------------

	def test_alta_familiar_crea_tramite_y_una_solicitud_por_persona(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(actividades=[{"actividad": self.act_basquet}]),
				"familiares": [
					self._persona(nombre="Bruno", rol_en_grupo="Cónyuge"),
					self._persona(
						nombre="Luca",
						rol_en_grupo="Hijo",
						categoria_solicitada="Menor",
						fecha_nacimiento=str(minor_birthdate(12)),
					),
				],
			}
		)

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["personas"], 3)
		self.assertTrue(result["token_seguimiento"])
		self.assertNotIn("tramite", result)

		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE,
			{"token_seguimiento": result["token_seguimiento"]},
			["name", "cantidad_personas", "solicitud_titular", "apellido_principal"],
			as_dict=True,
		)
		self.assertIsNotNone(tramite)
		self.assertEqual(tramite.cantidad_personas, 3)
		self.assertEqual(tramite.apellido_principal, "Pérez")

		filas = self._solicitudes_del_tramite(tramite.name)
		self.assertEqual(len(filas), 3)
		self.assertTrue(all(f["workflow_state"] == STATE_PENDIENTE for f in filas))

		titular = frappe.get_doc(SOLICITUD_DOCTYPE, tramite.solicitud_titular)
		self.assertEqual(titular.rol_en_grupo, "Titular")
		self.assertEqual(titular.nombre, "Ana")

	def test_actividades_no_se_mezclan_entre_personas(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(actividades=[{"actividad": self.act_basquet}]),
				"familiares": [
					self._persona(
						nombre="Luca",
						rol_en_grupo="Hijo",
						actividades=[
							{"actividad": self.act_futbol},
							{"actividad": self.act_voley},
						],
					)
				],
			}
		)
		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		filas = self._solicitudes_del_tramite(tramite)

		por_nombre = {f["nombre"]: frappe.get_doc(SOLICITUD_DOCTYPE, f["name"]) for f in filas}
		titular_acts = [r.actividad for r in por_nombre["Ana"].actividades_solicitadas]
		hijo_acts = sorted(r.actividad for r in por_nombre["Luca"].actividades_solicitadas)

		self.assertEqual(titular_acts, [self.act_basquet])
		self.assertEqual(hijo_acts, sorted([self.act_futbol, self.act_voley]))

	def test_socio_sin_actividad_queda_marcado_y_sin_filas(self) -> None:
		result = _submit_alta_grupo_impl(
			{"titular": self._persona(sin_actividad=1, actividades=[]), "familiares": []}
		)
		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		filas = self._solicitudes_del_tramite(tramite)
		self.assertEqual(len(filas), 1)

		doc = frappe.get_doc(SOLICITUD_DOCTYPE, filas[0]["name"])
		self.assertEqual(int(doc.sin_actividad), 1)
		self.assertEqual(len(doc.actividades_solicitadas), 0)

	def test_actividad_inexistente_o_deshabilitada_se_descarta(self) -> None:
		deshabilitada = self._ensure_actividad(
			f"QA Vieja {self.sufijo}", habilitada=0
		)
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(
					actividades=[
						{"actividad": self.act_basquet},
						{"actividad": deshabilitada},
						{"actividad": "Actividad Que No Existe"},
					]
				),
				"familiares": [],
			}
		)
		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		filas = self._solicitudes_del_tramite(tramite)
		doc = frappe.get_doc(SOLICITUD_DOCTYPE, filas[0]["name"])

		self.assertEqual([r.actividad for r in doc.actividades_solicitadas], [self.act_basquet])

	def test_alta_sin_titular_es_rechazada(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			_submit_alta_grupo_impl({"familiares": [self._persona()]})

	# ------------------------------------------------------------------
	# Validación en cadena
	# ------------------------------------------------------------------

	def test_validar_titular_crea_grupo_y_lo_registra_en_el_tramite(self) -> None:
		result = _submit_alta_grupo_impl(
			{"titular": self._persona(), "familiares": [self._persona(nombre="Bruno", rol_en_grupo="Cónyuge")]}
		)
		tramite_name = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		titular_name = frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "solicitud_titular")

		self._validar(titular_name)

		titular = frappe.get_doc(SOLICITUD_DOCTYPE, titular_name)
		self.assertTrue(titular.socio_generado)
		self.assertTrue(titular.grupo_familiar_generado)
		self.assertEqual(
			frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "grupo_familiar_generado"),
			titular.grupo_familiar_generado,
		)

	def test_conyuge_entra_como_cotitular_automatico(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(),
				"familiares": [self._persona(nombre="Bruno", rol_en_grupo="Cónyuge")],
			}
		)
		tramite_name = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		titular_name = frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "solicitud_titular")
		self._validar(titular_name)
		grupo = frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "grupo_familiar_generado")

		conyuge_name = next(
			f["name"] for f in self._solicitudes_del_tramite(tramite_name) if f["nombre"] == "Bruno"
		)
		self._validar(conyuge_name)

		conyuge = frappe.get_doc(SOLICITUD_DOCTYPE, conyuge_name)
		self.assertEqual(conyuge.grupo_familiar_generado, grupo)
		self.assertEqual(
			frappe.db.get_value("Socio", conyuge.socio_generado, "grupo_familiar"), grupo
		)

		grupo_doc = frappe.get_doc("Grupo Familiar", grupo)
		titulares_activos = [
			(t.titular, int(t.es_principal or 0), t.rol)
			for t in grupo_doc.titulares
			if not t.hasta
		]
		self.assertIn((conyuge.socio_generado, 0, "Cotitular"), titulares_activos)
		# El titular original sigue siendo el único principal.
		titular_socio = frappe.db.get_value(SOLICITUD_DOCTYPE, titular_name, "socio_generado")
		self.assertIn((titular_socio, 1, "Titular"), titulares_activos)

		# No se creó un grupo paralelo para el cónyuge.
		self.assertEqual(
			frappe.db.count(
				"Grupo Familiar", {"apellido_principal": "Pérez", "name": ["!=", grupo]}
			),
			0,
		)

	def test_familiar_otro_entra_como_miembro_no_cotitular(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(),
				"familiares": [self._persona(nombre="Carla", rol_en_grupo="Otro")],
			}
		)
		tramite_name = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		titular_name = frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "solicitud_titular")
		self._validar(titular_name)
		grupo = frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "grupo_familiar_generado")

		otro_name = next(
			f["name"] for f in self._solicitudes_del_tramite(tramite_name) if f["nombre"] == "Carla"
		)
		self._validar(otro_name)

		otro = frappe.get_doc(SOLICITUD_DOCTYPE, otro_name)
		grupo_doc = frappe.get_doc("Grupo Familiar", grupo)
		roles_miembro = {m.socio: m.rol for m in grupo_doc.miembros if not m.hasta}
		self.assertEqual(roles_miembro.get(otro.socio_generado), "Otro")
		titulares = {t.titular for t in grupo_doc.titulares if not t.hasta}
		self.assertNotIn(otro.socio_generado, titulares)

	def test_validar_familiar_antes_que_titular_falla(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(),
				"familiares": [self._persona(nombre="Bruno", rol_en_grupo="Cónyuge")],
			}
		)
		tramite_name = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		conyuge_name = next(
			f["name"] for f in self._solicitudes_del_tramite(tramite_name) if f["nombre"] == "Bruno"
		)

		with self.assertRaises(frappe.ValidationError) as ctx:
			self._validar(conyuge_name)
		self.assertIn(MSG_TITULAR_SIN_VALIDAR, str(ctx.exception))

		self.assertFalse(frappe.db.get_value(SOLICITUD_DOCTYPE, conyuge_name, "socio_generado"))

	def test_alta_individual_sin_grupo_sigue_creando_su_propio_grupo(self) -> None:
		"""Regresión: el alta de una sola persona no cambia de comportamiento."""
		result = _submit_alta_grupo_impl({"titular": self._persona(), "familiares": []})
		tramite_name = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		titular_name = frappe.db.get_value(TRAMITE_DOCTYPE, tramite_name, "solicitud_titular")
		self._validar(titular_name)

		titular = frappe.get_doc(SOLICITUD_DOCTYPE, titular_name)
		self.assertTrue(titular.grupo_familiar_generado)

	# ------------------------------------------------------------------
	# Consulta pública
	# ------------------------------------------------------------------

	def test_consultar_tramite_devuelve_estado_por_persona_sin_pii(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(),
				"familiares": [self._persona(nombre="Bruno", rol_en_grupo="Cónyuge")],
			}
		)
		consulta = _consultar_alta_grupo_impl(result["token_seguimiento"])

		self.assertEqual(consulta["status"], "ok")
		self.assertEqual(len(consulta["personas"]), 2)

		persona = consulta["personas"][0]
		self.assertIn("nombre", persona)
		self.assertIn("rol_en_grupo", persona)
		self.assertIn("workflow_state", persona)
		for prohibido in ("dni", "email", "ficha_medica", "dni_frente", "name"):
			self.assertNotIn(prohibido, persona)

	def test_consultar_tramite_con_token_invalido(self) -> None:
		with self.assertRaises(frappe.DoesNotExistError):
			_consultar_alta_grupo_impl("token-que-no-existe")

	# ------------------------------------------------------------------
	# Categoría Adherente / Jubilado
	# ------------------------------------------------------------------

	def test_adherente_solo_permite_actividades_whitelist(self) -> None:
		yoga = self._ensure_actividad("Yoga")
		gym = self._ensure_actividad("Gimnasio Fitness")
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(
					categoria_solicitada="Adherente",
					actividades=[
						{"actividad": self.act_basquet},
						{"actividad": yoga},
						{"actividad": gym},
					],
					sin_actividad=0,
				),
				"familiares": [],
			}
		)
		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		doc = frappe.get_doc(SOLICITUD_DOCTYPE, self._solicitudes_del_tramite(tramite)[0]["name"])
		self.assertEqual(doc.categoria_solicitada, "Adherente")
		self.assertEqual(int(doc.sin_actividad), 0)
		acts = sorted(r.actividad for r in doc.actividades_solicitadas)
		self.assertEqual(acts, sorted([yoga, gym]))

	def test_adherente_sin_deportes_permitidos_queda_sin_actividad(self) -> None:
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(
					categoria_solicitada="Adherente",
					actividades=[{"actividad": self.act_basquet}],
					sin_actividad=0,
				),
				"familiares": [],
			}
		)
		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		doc = frappe.get_doc(SOLICITUD_DOCTYPE, self._solicitudes_del_tramite(tramite)[0]["name"])
		self.assertEqual(int(doc.sin_actividad), 1)
		self.assertEqual(len(doc.actividades_solicitadas), 0)

	def test_jubilado_exige_comprobante(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			_submit_alta_grupo_impl(
				{
					"titular": self._persona(categoria_solicitada="Jubilado"),
					"familiares": [],
				}
			)

	def test_jubilado_con_comprobante_ok(self) -> None:
		comprobante = make_test_file(f"qa_jub_{self.sufijo}.pdf", MINIMAL_VALID_PDF)
		result = _submit_alta_grupo_impl(
			{
				"titular": self._persona(
					categoria_solicitada="Jubilado",
					comprobante_jubilado=comprobante,
					sin_actividad=1,
					actividades=[],
				),
				"familiares": [],
			}
		)
		tramite = frappe.db.get_value(
			TRAMITE_DOCTYPE, {"token_seguimiento": result["token_seguimiento"]}, "name"
		)
		doc = frappe.get_doc(SOLICITUD_DOCTYPE, self._solicitudes_del_tramite(tramite)[0]["name"])
		self.assertEqual(doc.categoria_solicitada, "Jubilado")
		self.assertTrue(doc.comprobante_jubilado)

	def test_menor_no_puede_ser_jubilado(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			_submit_alta_grupo_impl(
				{
					"titular": self._persona(
						fecha_nacimiento=str(minor_birthdate(10)),
						categoria_solicitada="Jubilado",
						comprobante_jubilado=make_test_file(
							f"qa_jub_bad_{self.sufijo}.pdf", MINIMAL_VALID_PDF
						),
					),
					"familiares": [],
				}
			)

	def test_catalogo_incluye_adherente_y_comprobante(self) -> None:
		from club_management.members.api.alta_grupo_publica import get_catalogo_alta

		cat = get_catalogo_alta()
		self.assertIn("Adherente", cat["categorias"])
		self.assertIn("Jubilado", cat["categorias"])
		self.assertNotIn("Cadete", cat["categorias"])
		self.assertIn("comprobante_jubilado", cat["adjuntos"])
		self.assertIn("Yoga", cat["actividades_adherente"])
		self.assertIn("Gimnasio Fitness", cat["actividades_adherente"])
		self.assertIn("Funcional", cat["actividades_adherente"])
		self.assertIn("Crossfit", cat["actividades_adherente"])

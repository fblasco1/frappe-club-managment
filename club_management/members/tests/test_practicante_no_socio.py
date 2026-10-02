"""Tests practicante No Socio (spec gimnasio_cobro_socios_no_socios.md)."""

from __future__ import annotations

import frappe

from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.members.doctype.socio.socio import CATEGORIA_NO_SOCIO
from club_management.members.services.cobranza_manual import (
	build_invoice_items_for_socio,
	resolve_cuota_social,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.practicante_no_socio import (
	GRUPO_GIMNASIO_NO_SOCIO,
	convertir_no_socio_a_socio,
	crear_practicante_no_socio,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	make_socio_payload,
)


def _datos_practicante(**overrides) -> dict:
	payload = make_socio_payload(**overrides)
	payload.pop("doctype", None)
	payload.pop("categoria", None)
	return payload


class TestPracticanteNoSocio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		seed_estructura_actividades_completa(crear_equipos=False)
		sync_cuotas_sociales_club()

	def test_insert_no_socio_usa_serie_ns_sin_numero(self) -> None:
		socio = insert_socio(dni="76001001", email="ns.serie@example.com", categoria=CATEGORIA_NO_SOCIO)
		self.assertTrue(socio.name.startswith("NS-"))
		self.assertFalse(socio.numero_socio)

	def test_no_socio_no_consume_numeracion(self) -> None:
		previo = insert_socio(dni="76001002", email="ns.prev@example.com")
		insert_socio(dni="76001003", email="ns.mid@example.com", categoria=CATEGORIA_NO_SOCIO)
		siguiente = insert_socio(dni="76001004", email="ns.next@example.com")
		self.assertEqual(int(siguiente.name), int(previo.name) + 1)

	def test_no_socio_cuota_social_cero(self) -> None:
		socio = insert_socio(dni="76001005", email="ns.cuota@example.com", categoria=CATEGORIA_NO_SOCIO)
		self.assertEqual(resolve_cuota_social(socio.name), (0.0, None))

	def test_crear_practicante_activo_e_inscripto_en_gimnasio(self) -> None:
		name = crear_practicante_no_socio(
			_datos_practicante(dni="76001006", email="ns.alta@example.com")
		)
		doc = frappe.get_doc("Socio", name)
		self.assertTrue(name.startswith("NS-"))
		self.assertEqual(doc.categoria, CATEGORIA_NO_SOCIO)
		self.assertEqual(doc.estado, "Activo")
		self.assertTrue(
			frappe.db.exists(
				"Inscripcion Actividad",
				{"socio": name, "grupo_actividad": GRUPO_GIMNASIO_NO_SOCIO, "estado": "Activa"},
			)
		)

	def test_deuda_mensual_no_socio_sin_cuota_con_arancel_gym(self) -> None:
		from club_management.activities.data.otras_actividades_aranceles_icdpe import (
			ITEM_GYM_NO_SOCIO,
		)

		name = crear_practicante_no_socio(
			_datos_practicante(dni="76001007", email="ns.deuda@example.com")
		)
		items = build_invoice_items_for_socio(name, reference_date="2026-10-01")
		codes = [row["item_code"] for row in items]
		settings = frappe.get_single("Club Settings")
		self.assertNotIn(settings.item_cuota_social, codes)
		self.assertIn(ITEM_GYM_NO_SOCIO, codes)

	def test_convertir_no_socio_a_socio(self) -> None:
		name = crear_practicante_no_socio(
			_datos_practicante(dni="76001008", email="ns.conv@example.com")
		)
		ultimo = insert_socio(dni="76001009", email="ns.conv.ult@example.com")
		nuevo = convertir_no_socio_a_socio(name, categoria="Activo")
		self.assertEqual(int(nuevo), int(ultimo.name) + 1)
		doc = frappe.get_doc("Socio", nuevo)
		self.assertEqual(doc.categoria, "Activo")
		self.assertEqual(int(doc.numero_socio), int(nuevo))
		self.assertFalse(frappe.db.exists("Socio", name))
		self.assertTrue(frappe.db.exists("Inscripcion Actividad", {"socio": nuevo}))

	def _ex_socio_baja(self, dni: str, email: str) -> str:
		from club_management.members.services.socio_transitions import cambiar_estado

		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test")
		cambiar_estado(socio.name, "Baja", motivo="Test baja")
		return socio.name

	def test_ex_socio_baja_reingresa_como_no_socio(self) -> None:
		ex = self._ex_socio_baja("76001020", "ns.ex.socio@example.com")
		name = crear_practicante_no_socio(
			_datos_practicante(dni="76001020", email="ns.ex.nuevo@example.com")
		)
		self.assertEqual(name, ex)
		doc = frappe.get_doc("Socio", name)
		self.assertEqual(doc.categoria, CATEGORIA_NO_SOCIO)
		self.assertEqual(doc.estado, "Activo")
		self.assertEqual(doc.email, "ns.ex.nuevo@example.com")
		self.assertEqual(frappe.db.count("Socio", {"dni": "76001020"}), 1)
		self.assertTrue(
			frappe.db.exists(
				"Inscripcion Actividad",
				{"socio": name, "grupo_actividad": GRUPO_GIMNASIO_NO_SOCIO, "estado": "Activa"},
			)
		)

	def test_dni_de_socio_vigente_sigue_rechazado(self) -> None:
		insert_socio(dni="76001021", email="ns.vigente@example.com")
		with self.assertRaises(frappe.ValidationError):
			crear_practicante_no_socio(_datos_practicante(dni="76001021", email="ns.vigente2@example.com"))

	def test_convertir_ex_socio_conserva_su_numero(self) -> None:
		ex = self._ex_socio_baja("76001022", "ns.ex.conv@example.com")
		crear_practicante_no_socio(_datos_practicante(dni="76001022", email="ns.ex.conv2@example.com"))
		nuevo = convertir_no_socio_a_socio(ex, categoria="Activo")
		self.assertEqual(nuevo, ex)
		doc = frappe.get_doc("Socio", nuevo)
		self.assertEqual(doc.categoria, "Activo")
		self.assertEqual(int(doc.numero_socio), int(ex))

	def test_convertir_rechaza_si_no_es_no_socio(self) -> None:
		socio = insert_socio(dni="76001010", email="ns.conv.rech@example.com")
		with self.assertRaises(frappe.ValidationError):
			convertir_no_socio_a_socio(socio.name, categoria="Activo")

	def test_corregir_numero_rechaza_no_socio(self) -> None:
		from club_management.members.services.corregir_numero_socio import corregir_numero_socio

		socio = insert_socio(dni="76001013", email="ns.corregir@example.com", categoria=CATEGORIA_NO_SOCIO)
		with self.assertRaises(frappe.ValidationError):
			corregir_numero_socio(socio.name, 999999)

	def test_no_socio_excluido_de_kpis(self) -> None:
		from club_management.members.services.secretaria_panel_kpis import count_socios_total

		antes = count_socios_total()
		insert_socio(dni="76001011", email="ns.kpi@example.com", categoria=CATEGORIA_NO_SOCIO)
		self.assertEqual(count_socios_total(), antes)

	def test_no_socio_no_solicitable_publicamente(self) -> None:
		from club_management.members.api.alta_grupo_publica import CATEGORIAS_SOLICITABLES

		self.assertNotIn(CATEGORIA_NO_SOCIO, CATEGORIAS_SOLICITABLES)

	def test_crear_practicante_requiere_secretaria(self) -> None:
		from club_management.members.test_helpers import ensure_role_socio_exists

		ensure_role_socio_exists()
		user = "socio.sin.permiso.gym@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "Sin",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)
		previous = frappe.session.user
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				crear_practicante_no_socio(
					_datos_practicante(dni="76001012", email="ns.perm@example.com")
				)
		finally:
			frappe.set_user(previous)

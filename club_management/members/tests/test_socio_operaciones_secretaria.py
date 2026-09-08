"""Tests operaciones Desk Secretaría sin pagos (MVP)."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, add_months, getdate, now, today

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.members.services.socio_operaciones_secretaria import (
	activar_socio_manual,
	dar_alta_socio,
	dar_baja_socio,
	marcar_moroso,
	omitir_pago_manual,
	reactivar_socio,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestSocioOperacionesSecretaria(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = "secretaria_mvp@example.com"
		if not frappe.db.exists("User", self._secretaria):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": self._secretaria,
					"first_name": "Secretaria",
					"send_welcome_email": 0,
					"roles": [{"role": "Secretaria"}],
				}
			)
			user.insert(ignore_permissions=True)

	def test_omitir_pago_pasa_a_pendiente_inscripcion(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Pendiente de Pago", motivo="Validada")
		frappe.set_user(self._secretaria)
		try:
			omitir_pago_manual(socio.name, motivo="Alta manual sin pago online")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, ESTADO_SOCIO_PENDIENTE_INSCRIPCION)
		self.assertIn("manual", (socio.motivo_ultimo_cambio_estado or "").lower())

	def test_activar_desde_pendiente_inscripcion(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, ESTADO_SOCIO_PENDIENTE_INSCRIPCION, motivo="Pago omitido")
		frappe.set_user(self._secretaria)
		try:
			activar_socio_manual(socio.name)
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertTrue(socio.fecha_alta)

	def test_moroso_y_reactivar(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		frappe.set_user(self._secretaria)
		try:
			marcar_moroso(socio.name, motivo="Cuota vencida")
			socio.reload()
			self.assertEqual(socio.estado, "Moroso")
			reactivar_socio(socio.name, motivo="Pago en efectivo")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")

	def test_dar_baja(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		frappe.set_user(self._secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Baja")

	def test_dar_alta_desde_baja(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		socio.reload()
		numero = socio.numero_socio
		fecha_alta = socio.fecha_alta
		frappe.set_user(self._secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
			dar_alta_socio(socio.name, motivo="Quiere volver")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(socio.numero_socio, numero)
		self.assertEqual(str(socio.fecha_alta), str(fecha_alta))
		self.assertIn("volver", (socio.motivo_ultimo_cambio_estado or "").lower())

	def test_dar_alta_conserva_fecha_alta_al_cumplirse_6_meses(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		socio.reload()
		fecha_alta = socio.fecha_alta
		frappe.set_user(self._secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
			frappe.db.set_value(
				"Socio",
				socio.name,
				"ultimo_cambio_estado_en",
				add_months(now(), -6),
			)
			dar_alta_socio(socio.name, motivo="Vuelve al límite")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(getdate(socio.fecha_alta), getdate(fecha_alta))

	def test_dar_alta_reinicia_fecha_alta_si_baja_mayor_a_6_meses(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		fecha_alta_original = add_months(today(), -24)
		frappe.db.set_value("Socio", socio.name, "fecha_alta", fecha_alta_original)
		frappe.set_user(self._secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
			frappe.db.set_value(
				"Socio",
				socio.name,
				"ultimo_cambio_estado_en",
				add_days(add_months(now(), -6), -1),
			)
			dar_alta_socio(socio.name, motivo="Vuelve tarde")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(getdate(socio.fecha_alta), getdate(today()))
		self.assertNotEqual(getdate(socio.fecha_alta), getdate(fecha_alta_original))
		self.assertTrue(socio.numero_socio)

	def test_dar_alta_solo_desde_baja(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Activo", motivo="Test")
		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				dar_alta_socio(socio.name, motivo="No corresponde")
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Activo")

	def test_socio_sin_rol_no_puede_dar_alta(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Baja", motivo="Renuncia")
		email = f"socio_alta_{socio.dni}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				dar_alta_socio(socio.name)
		finally:
			frappe.set_user("Administrator")
		socio.reload()
		self.assertEqual(socio.estado, "Baja")

	def test_socio_sin_rol_no_puede_omitir_pago(self) -> None:
		socio = insert_socio()
		cambiar_estado(socio.name, "Pendiente de Pago", motivo="Validada")
		email = f"socio_{socio.dni}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				omitir_pago_manual(socio.name)
		finally:
			frappe.set_user("Administrator")

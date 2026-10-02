"""Tests bonificaciones activas en la ficha del socio (spec bonificaciones_activas_socio.md)."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, add_months, today

from club_management.members.api.socio_operaciones_desk import (
	cancelar_bonificacion_socio,
	list_bonificaciones_activas_socio,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user

ACTIVIDAD = "Tenis"


def _periodo_actual() -> str:
	hoy = frappe.utils.getdate(today())
	return f"{hoy.month:02d}/{hoy.year}"


class TestBonificacionesActivasSocio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		for doctype in ("Beca Socio", "Bonificacion Recurrente", "Bonificacion Arancel"):
			if not frappe.db.exists("DocType", doctype):
				self.skipTest(f"Falta DocType {doctype}")
		if not frappe.db.exists("Actividad", ACTIVIDAD):
			frappe.get_doc({"doctype": "Actividad", "titulo": ACTIVIDAD, "habilitada": 1}).insert(
				ignore_permissions=True
			)
		self.secretaria = make_secretaria_user("sec.bonif.activas@example.com")

	def _beca(self, socio: str, **overrides):
		payload = {
			"doctype": "Beca Socio",
			"socio": socio,
			"tipo_beca": "Parcial Porcentaje",
			"pct_cuota_social": 50,
			"pct_arancel": 0,
			"fecha_desde": add_months(today(), -1),
			"fecha_hasta": add_months(today(), 5),
			"estado": "Activa",
		}
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def _recurrente(self, socio: str, **overrides):
		payload = {
			"doctype": "Bonificacion Recurrente",
			"socio": socio,
			"estado": "Activa",
			"tipo_descuento": "Porcentaje",
			"valor": 20,
			"actividad": ACTIVIDAD,
			"fecha_desde": add_months(today(), -1),
			"motivo": "Hermanos en tenis",
		}
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def _arancel(self, socio: str | None, **overrides):
		payload = {
			"doctype": "Bonificacion Arancel",
			"socio": socio,
			"periodo_cobro": _periodo_actual(),
			"estado": "Activa",
			"tipo_descuento": "Monto fijo",
			"valor": 5000,
			"motivo": "Descuento puntual",
		}
		if not socio:
			payload["actividad"] = ACTIVIDAD
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def _listar(self, socio: str) -> list[dict]:
		frappe.set_user(self.secretaria)
		try:
			return list_bonificaciones_activas_socio(socio)
		finally:
			frappe.set_user("Administrator")

	def _cancelar(self, doctype: str, name: str, socio: str) -> None:
		frappe.set_user(self.secretaria)
		try:
			cancelar_bonificacion_socio(doctype, name, socio)
		finally:
			frappe.set_user("Administrator")

	def test_lista_las_tres_activas(self) -> None:
		socio = insert_socio(dni="75101001", email="bonif.act.1@example.com").name
		beca = self._beca(socio)
		rec = self._recurrente(socio)
		arancel = self._arancel(socio)

		rows = self._listar(socio)
		por_nombre = {row["name"]: row for row in rows}
		self.assertEqual(set(por_nombre), {beca.name, rec.name, arancel.name})
		self.assertEqual(por_nombre[beca.name]["doctype"], "Beca Socio")
		self.assertEqual(por_nombre[rec.name]["doctype"], "Bonificacion Recurrente")
		self.assertEqual(por_nombre[arancel.name]["doctype"], "Bonificacion Arancel")
		self.assertIn("20", por_nombre[rec.name]["descuento"])
		self.assertIn(ACTIVIDAD, por_nombre[rec.name]["alcance"])
		self.assertIn("5.000", por_nombre[arancel.name]["descuento"])
		self.assertEqual(por_nombre[arancel.name]["vigencia"], _periodo_actual())

	def test_no_lista_inactivas_ni_vencidas(self) -> None:
		socio = insert_socio(dni="75101002", email="bonif.act.2@example.com").name
		self._beca(socio, estado="Cancelada")
		self._beca(
			socio,
			fecha_desde=add_months(today(), -6),
			fecha_hasta=add_days(today(), -1),
		)
		self._recurrente(socio, estado="Anulada")
		self._recurrente(
			socio,
			fecha_desde=add_months(today(), -6),
			fecha_hasta=add_days(today(), -1),
		)
		self._arancel(socio, estado="Anulada")
		self.assertEqual(self._listar(socio), [])

	def test_arancel_masiva_no_aparece(self) -> None:
		socio = insert_socio(dni="75101003", email="bonif.act.3@example.com").name
		self._arancel(None)
		self.assertEqual(self._listar(socio), [])

	def test_cancelar_cada_tipo(self) -> None:
		socio = insert_socio(dni="75101004", email="bonif.act.4@example.com").name
		beca = self._beca(socio)
		rec = self._recurrente(socio)
		arancel = self._arancel(socio)

		self._cancelar("Beca Socio", beca.name, socio)
		self._cancelar("Bonificacion Recurrente", rec.name, socio)
		self._cancelar("Bonificacion Arancel", arancel.name, socio)

		self.assertEqual(frappe.db.get_value("Beca Socio", beca.name, "estado"), "Cancelada")
		self.assertEqual(frappe.db.get_value("Bonificacion Recurrente", rec.name, "estado"), "Anulada")
		self.assertEqual(frappe.db.get_value("Bonificacion Arancel", arancel.name, "estado"), "Anulada")
		self.assertEqual(self._listar(socio), [])

	def test_no_cancela_bonificacion_de_otro_socio(self) -> None:
		socio_a = insert_socio(dni="75101005", email="bonif.act.5@example.com").name
		socio_b = insert_socio(dni="75101006", email="bonif.act.6@example.com").name
		rec = self._recurrente(socio_a)
		with self.assertRaises(frappe.ValidationError):
			self._cancelar("Bonificacion Recurrente", rec.name, socio_b)
		self.assertEqual(frappe.db.get_value("Bonificacion Recurrente", rec.name, "estado"), "Activa")

	def test_rechaza_doctype_no_permitido(self) -> None:
		socio = insert_socio(dni="75101007", email="bonif.act.7@example.com").name
		with self.assertRaises(frappe.ValidationError):
			self._cancelar("Socio", socio, socio)
		self.assertNotEqual(frappe.db.get_value("Socio", socio, "estado"), "Cancelada")

	def test_sin_rol_secretaria_rechazado(self) -> None:
		socio = insert_socio(dni="75101008", email="bonif.act.8@example.com").name
		rec = self._recurrente(socio)
		user = "sin.rol.bonif@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "Sin rol", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				list_bonificaciones_activas_socio(socio)
			with self.assertRaises(frappe.PermissionError):
				cancelar_bonificacion_socio("Bonificacion Recurrente", rec.name, socio)
		finally:
			frappe.set_user("Administrator")

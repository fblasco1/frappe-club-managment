"""Tests canal guest reservas externas (token / SP-3).

Spec: `club_management/specs/reservas_espacio_externo.md`
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

import frappe
from frappe.utils import add_days, flt, today

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import get_occupancy
from club_management.spaces.helpers import insert_espacio
from club_management.spaces.services import externo_tokens
from club_management.spaces.tests.test_portal_reservas import (
	_ensure_alquiler_item,
	as_user,
)

API_MODULE = "club_management.spaces.api.externo_reservas"
ITEM_ALQUILER = "ICDPE-ALQ-ARS-TEMP"


def externo_api() -> ModuleType:
	return importlib.import_module(API_MODULE)


class TestExternoReservas(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		_ensure_alquiler_item(rate=20000.0)
		self.espacio = insert_espacio(
			"Cancha Externo Token",
			tipo="Cancha",
			alquilable=1,
			habilitado=1,
		)
		frappe.db.set_value(
			"Espacio",
			self.espacio,
			{"tarifa_externo": 25000.0, "tarifa_socio": 15000.0},
			update_modified=False,
		)
		self.fecha = str(add_days(today(), 14))
		frappe.db.set_single_value("Club Settings", "espacios_reserva_externa_habilitada", 0)

	def _enable_canal(self, enabled: int = 1) -> None:
		frappe.db.set_single_value(
			"Club Settings",
			"espacios_reserva_externa_habilitada",
			enabled,
		)

	def _abrir_sesion(self) -> str:
		with as_user("Guest"):
			out = externo_api().abrir_sesion_reserva_externa()
		return out["sesion_token"]

	def _solicitar(
		self,
		sesion_token: str,
		*,
		hora_inicio: str = "18:00:00",
		hora_fin: str = "19:00:00",
		espacio: str | None = None,
	) -> dict[str, Any]:
		with as_user("Guest"):
			return externo_api().solicitar_reserva_externa(
				sesion_token=sesion_token,
				espacio=espacio or self.espacio,
				fecha=self.fecha,
				hora_inicio=hora_inicio,
				hora_fin=hora_fin,
				arrendatario_nombre="Club Visitante SA",
				arrendatario_contacto="externo@example.com",
			)

	def test_canal_deshabilitado_permission_error(self) -> None:
		from club_management.spaces.services.externo_reservas import CHANNEL_DISABLED_BODY

		self._enable_canal(0)
		with as_user("Guest"), self.assertRaises(frappe.PermissionError) as ctx:
			externo_api().abrir_sesion_reserva_externa()
		self.assertIn(CHANNEL_DISABLED_BODY["message"], str(ctx.exception))
		self.assertEqual(
			frappe.local.response.get("channel_disabled_body"),
			CHANNEL_DISABLED_BODY,
		)
		self.assertFalse(
			frappe.db.exists(
				"Reserva Espacio",
				{"tipo": "Alquiler externo", "espacio": self.espacio, "fecha": self.fecha},
			)
		)

	def test_sesion_invalida_y_vencida_permission_error(self) -> None:
		self._enable_canal(1)
		with as_user("Guest"), self.assertRaises(frappe.PermissionError):
			externo_api().get_espacios_disponibles_externo(
				sesion_token="token-basura",
				fecha=self.fecha,
			)

		expired = externo_tokens.sign_sesion_token(ttl_seconds=-60)
		with as_user("Guest"), self.assertRaises(frappe.PermissionError):
			externo_api().get_espacios_disponibles_externo(
				sesion_token=expired,
				fecha=self.fecha,
			)

	def test_solicitar_crea_pendiente_token_y_ocupa(self) -> None:
		self._enable_canal(1)
		token = self._abrir_sesion()
		result = self._solicitar(token)

		self.assertEqual(result["status"], "ok")
		self.assertTrue(result["reserva"])
		self.assertTrue(result["token_acceso"])
		doc = frappe.get_doc("Reserva Espacio", result["reserva"])
		self.assertEqual(doc.tipo, "Alquiler externo")
		self.assertEqual(doc.modalidad_alquiler, "Temporal")
		self.assertEqual(doc.estado, "Pendiente")
		self.assertEqual(doc.arrendatario_nombre, "Club Visitante SA")
		self.assertEqual(doc.arrendatario_contacto, "externo@example.com")
		self.assertEqual(doc.token_acceso, result["token_acceso"])
		self.assertEqual(flt(doc.monto_arancel), 25000.0)
		self.assertTrue(doc.slot_key)

		occ = get_occupancy(self.espacio, self.fecha)
		self.assertTrue(any(o.get("name") == doc.name for o in occ))

		with as_user("Guest"):
			disp = externo_api().get_espacios_disponibles_externo(
				sesion_token=token,
				fecha=self.fecha,
			)
		esp = next(e for e in disp["espacios"] if e["espacio"] == self.espacio)
		self.assertEqual(flt(esp["monto_arancel"]), 25000.0)
		slot = next(
			s
			for s in esp["slots"]
			if str(s["hora_inicio"])[:5] == "18:00" and str(s["hora_fin"])[:5] == "19:00"
		)
		self.assertEqual(slot["estado"], "ocupado")

	def test_get_y_adjuntar_token_propio_ok_ajeno_falla(self) -> None:
		self._enable_canal(1)
		token = self._abrir_sesion()
		created = self._solicitar(token)
		acceso = created["token_acceso"]

		with as_user("Guest"):
			detalle = externo_api().get_reserva_externa(acceso)
		self.assertEqual(detalle["reserva"], created["reserva"])
		self.assertEqual(detalle["estado"], "Pendiente")
		self.assertEqual(flt(detalle["monto_arancel"]), 25000.0)

		with as_user("Guest"):
			adj = externo_api().adjuntar_comprobante_externo(
				token_acceso=acceso,
				file_url="/files/comprobante-externo.pdf",
			)
		self.assertEqual(adj["status"], "ok")
		doc = frappe.get_doc("Reserva Espacio", created["reserva"])
		self.assertEqual(doc.comprobante, "/files/comprobante-externo.pdf")
		self.assertTrue(doc.fecha_comprobante)
		self.assertEqual(doc.estado, "Pendiente")

		otro = self._solicitar(token, hora_inicio="19:00:00", hora_fin="20:00:00")
		with as_user("Guest"), self.assertRaises(frappe.PermissionError):
			externo_api().get_reserva_externa("token-inexistente-xyz")
		with as_user("Guest"), self.assertRaises(frappe.PermissionError):
			externo_api().adjuntar_comprobante_externo(
				token_acceso=otro["token_acceso"] + "-tampered",
				file_url="/files/otro.pdf",
			)

	def test_solape_validation_error(self) -> None:
		self._enable_canal(1)
		token = self._abrir_sesion()
		self._solicitar(token)
		with self.assertRaises(frappe.ValidationError):
			self._solicitar(token)
		count = frappe.db.count(
			"Reserva Espacio",
			{
				"espacio": self.espacio,
				"fecha": self.fecha,
				"tipo": "Alquiler externo",
				"estado": "Pendiente",
				"hora_desde": "18:00:00",
			},
		)
		self.assertEqual(count, 1)

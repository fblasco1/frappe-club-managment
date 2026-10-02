"""Quincena y Entrenamiento por hora del gimnasio (spec gimnasio_cobro_socios_no_socios.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO,
	ITEM_GYM_NO_SOCIO,
	ITEM_GYM_PASE_DIARIO_LEGACY,
	ITEM_GYM_QUINCENA_NO_SOCIO,
	ITEM_GYM_SOCIO,
)
from club_management.members.doctype.socio.socio import CATEGORIA_NO_SOCIO
from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.gimnasio_pases import (
	TIPO_ENTRENAMIENTO_HORA,
	TIPO_PASE_DIARIO_LEGACY,
	TIPO_QUINCENA,
	ensure_gimnasio_pases_items,
	generar_cargo_gimnasio,
	migrar_pase_diario_a_entrenamiento_hora,
	sincronizar_precios_gimnasio,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)


class TestGimnasioPaseQuincena(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		ensure_gimnasio_pases_items()
		sincronizar_precios_gimnasio()
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)

	def _no_socio(self, dni: str, email: str) -> str:
		socio = insert_socio(dni=dni, email=email, categoria=CATEGORIA_NO_SOCIO)
		cambiar_estado(socio.name, "Activo", motivo="Test pase gimnasio")
		return socio.name

	def test_entrenamiento_hora_con_pago_inmediato(self) -> None:
		ns = self._no_socio("79001001", "gym.pase.pago@example.com")
		result = generar_cargo_gimnasio(ns, TIPO_ENTRENAMIENTO_HORA, registrar_pago=True, mode_of_payment="Cash")
		cargo = frappe.get_doc("Cargo Socio", result["cargo"])
		self.assertEqual(cargo.estado, "Facturado")
		self.assertEqual(cargo.modo_cobro, "Unico")
		self.assertEqual(cargo.tipo_cargo, "Entrenamiento por Hora Gimnasio")
		self.assertEqual(cargo.item, ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO)
		self.assertEqual(flt(cargo.monto), 5000)
		self.assertTrue(result["payment_entry"])
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice", result["sales_invoice"], "outstanding_amount")), 0
		)

	def test_quincena_sin_pago_queda_impaga(self) -> None:
		ns = self._no_socio("79001002", "gym.quin@example.com")
		result = generar_cargo_gimnasio(ns, TIPO_QUINCENA, registrar_pago=False)
		self.assertIsNone(result["payment_entry"])
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice", result["sales_invoice"], "outstanding_amount")), 31000
		)

	def test_socio_tambien_compra_entrenamiento_hora(self) -> None:
		socio = insert_socio(dni="79001003", email="gym.pase.socio@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test pase gimnasio socio")
		result = generar_cargo_gimnasio(socio.name, TIPO_ENTRENAMIENTO_HORA, registrar_pago=True, mode_of_payment="Cash")
		cargo = frappe.get_doc("Cargo Socio", result["cargo"])
		self.assertEqual(cargo.estado, "Facturado")
		self.assertEqual(flt(cargo.monto), 5000)
		self.assertTrue(result["payment_entry"])

	def test_cargo_socio_directo_acepta_socio_y_fuerza_unico(self) -> None:
		socio = insert_socio(dni="79001004", email="gym.cargo.socio@example.com")
		frappe.flags.skip_cargo_auto_invoice = True
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Cargo Socio",
					"socio": socio.name,
					"titulo": "Quincena",
					"tipo_cargo": TIPO_QUINCENA,
					"modo_cobro": "Recurrente",
					"item": ITEM_GYM_QUINCENA_NO_SOCIO,
					"monto": 31000,
					"fecha_desde": "2026-10-01",
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.flags.skip_cargo_auto_invoice = False
		self.assertEqual(doc.modo_cobro, "Unico")

	def test_tipo_gimnasio_fuerza_unico(self) -> None:
		ns = self._no_socio("79001005", "gym.recurrente@example.com")
		frappe.flags.skip_cargo_auto_invoice = True
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Cargo Socio",
					"socio": ns,
					"titulo": "Quincena",
					"tipo_cargo": TIPO_QUINCENA,
					"modo_cobro": "Recurrente",
					"item": ITEM_GYM_QUINCENA_NO_SOCIO,
					"monto": 31000,
					"fecha_desde": "2026-10-01",
					"fecha_hasta": "2026-12-31",
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.flags.skip_cargo_auto_invoice = False
		self.assertEqual(doc.modo_cobro, "Unico")

	def test_precio_cero_rechazado(self) -> None:
		frappe.db.set_value("Item", ITEM_GYM_QUINCENA_NO_SOCIO, "standard_rate", 0)
		frappe.db.delete("Item Price", {"item_code": ITEM_GYM_QUINCENA_NO_SOCIO})
		ns = self._no_socio("79001006", "gym.precio0@example.com")
		with self.assertRaises(frappe.ValidationError):
			generar_cargo_gimnasio(ns, TIPO_QUINCENA, registrar_pago=False)

	def test_monto_explicito(self) -> None:
		ns = self._no_socio("79001007", "gym.explicito@example.com")
		result = generar_cargo_gimnasio(ns, TIPO_QUINCENA, registrar_pago=False, monto=18000)
		self.assertEqual(flt(frappe.db.get_value("Cargo Socio", result["cargo"], "monto")), 18000)

	def test_api_requiere_secretaria(self) -> None:
		from club_management.members.api.gimnasio_desk import generar_cargo_gimnasio_desk

		ensure_role_socio_exists()
		ns = self._no_socio("79001008", "gym.api.perm@example.com")
		user = "socio.sin.permiso.pase@example.com"
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
				generar_cargo_gimnasio_desk(socio=ns, tipo=TIPO_ENTRENAMIENTO_HORA)
		finally:
			frappe.set_user(previous)


class TestSincronizarPreciosGimnasio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext no instalado")
		ensure_gimnasio_pases_items()

	def test_actualiza_standard_rate_item_price_y_plan(self) -> None:
		from club_management.activities.services.gestion_actividades_panel import (
			_upsert_item_selling_price,
		)
		from club_management.setup.suscripciones_cobro_mensual import (
			ensure_subscription_plan_for_item,
		)

		frappe.db.set_value("Item", ITEM_GYM_SOCIO, "standard_rate", 22000)
		_upsert_item_selling_price(ITEM_GYM_SOCIO, 22000)
		plan = ensure_subscription_plan_for_item(ITEM_GYM_SOCIO, rate=22000)
		if plan:
			frappe.db.set_value("Subscription Plan", plan, "cost", 22000)

		sincronizar_precios_gimnasio()

		self.assertEqual(flt(frappe.db.get_value("Item", ITEM_GYM_SOCIO, "standard_rate")), 24000)
		for rate in frappe.get_all("Item Price", filters={"item_code": ITEM_GYM_SOCIO}, pluck="price_list_rate"):
			self.assertEqual(flt(rate), 24000)
		if plan:
			self.assertEqual(flt(frappe.db.get_value("Subscription Plan", plan, "cost")), 24000)

		esperados = {
			ITEM_GYM_NO_SOCIO: 49000,
			ITEM_GYM_QUINCENA_NO_SOCIO: 31000,
			ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO: 5000,
		}
		for item_code, rate in esperados.items():
			self.assertEqual(flt(frappe.db.get_value("Item", item_code, "standard_rate")), rate, item_code)

	def test_migra_pase_diario_a_entrenamiento_hora(self) -> None:
		frappe.db.delete("Item Default", {"parent": ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO})
		frappe.db.delete("Item", ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM_GYM_PASE_DIARIO_LEGACY,
				"item_name": "GIMNASIO FITNESS - PASE DIARIO NO SOCIO",
				"item_group": frappe.db.get_value("Item", ITEM_GYM_QUINCENA_NO_SOCIO, "item_group"),
				"is_stock_item": 0,
				"stock_uom": "Servicio",
			}
		).insert(ignore_permissions=True)

		socio = insert_socio(dni="79001020", email="gym.migra@example.com", categoria=CATEGORIA_NO_SOCIO)
		frappe.flags.skip_cargo_auto_invoice = True
		try:
			cargo = frappe.get_doc(
				{
					"doctype": "Cargo Socio",
					"socio": socio.name,
					"titulo": "Pase",
					"tipo_cargo": TIPO_QUINCENA,
					"modo_cobro": "Unico",
					"item": ITEM_GYM_QUINCENA_NO_SOCIO,
					"monto": 5000,
					"fecha_desde": "2026-10-01",
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.flags.skip_cargo_auto_invoice = False
		frappe.db.set_value(
			"Cargo Socio",
			cargo.name,
			{"tipo_cargo": TIPO_PASE_DIARIO_LEGACY, "item": ITEM_GYM_PASE_DIARIO_LEGACY},
		)

		migrar_pase_diario_a_entrenamiento_hora()

		self.assertFalse(frappe.db.exists("Item", ITEM_GYM_PASE_DIARIO_LEGACY))
		self.assertTrue(frappe.db.exists("Item", ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO))
		row = frappe.db.get_value("Cargo Socio", cargo.name, ["tipo_cargo", "item"], as_dict=True)
		self.assertEqual(row.tipo_cargo, TIPO_ENTRENAMIENTO_HORA)
		self.assertEqual(row.item, ITEM_GYM_ENTRENAMIENTO_HORA_NO_SOCIO)

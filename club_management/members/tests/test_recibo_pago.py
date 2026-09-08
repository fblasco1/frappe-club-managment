"""Tests recibo de pago térmico ESC/POS — spec `recibo_pago_escpos.md`."""

from __future__ import annotations

import base64

import frappe

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.api.cobranza_desk import get_recibo_pago, registrar_cobro
from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.recibo_pago import (
	ANCHO_CARACTERES,
	build_recibo_pago,
	format_monto_ar,
	render_recibo_escpos,
	render_recibo_texto,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user

_ESC_INIT = b"\x1b\x40"
_ESC_CUT = b"\x1d\x56"


class TestReciboPagoFormato(MembersTestCase):
	def test_format_monto_argentino(self) -> None:
		self.assertEqual(format_monto_ar(29000), "$29.000")
		self.assertEqual(format_monto_ar(50500), "$50.500")

	def test_ancho_papel(self) -> None:
		self.assertEqual(ANCHO_CARACTERES[58], 32)
		self.assertEqual(ANCHO_CARACTERES[80], 48)

	def test_render_texto_incluye_encabezado_y_total(self) -> None:
		data = {
			"encabezado": {
				"institucion_nombre": "INSTITUCION CULTURAL Y DEPORTIVA PEDRO ECHAGUE",
				"institucion_direccion": "PORTELA 836 - CABA",
				"cuit": "30-12345678-9",
				"condicion_iva": "IVA RESPONSABLE",
			},
			"comprobante": "ACC-PAY-2026-00001",
			"fecha": "01/07/2026",
			"hora": "17:49",
			"lineas": [
				{"concepto": "CUOTA SOCIAL ACTIVO", "monto": 29000},
				{"concepto": "ARANCEL BASQUET FEMENINO", "monto": 21500},
			],
			"total": 50500,
			"mensaje_pie": "SOMOS ECHAGUE, SOMOS FAMILIA !!",
			"ancho_papel_mm": 58,
		}
		texto = render_recibo_texto(data)
		self.assertIn("INSTITUCION CULTURAL Y DEPORTIVA", texto)
		self.assertIn("PEDRO ECHAGUE", texto)
		self.assertIn("PORTELA 836 - CABA", texto)
		self.assertIn("CUIT: 30-12345678-9", texto)
		self.assertIn("COMPROBANTE", texto)
		self.assertIn("ACC-PAY-2026-00001", texto)
		self.assertIn("CUOTA SOCIAL ACTIVO", texto)
		self.assertIn("$29.000", texto)
		self.assertIn("TOTAL: $50.500", texto)
		self.assertIn("SOMOS ECHAGUE, SOMOS FAMILIA !!", texto)

	def test_render_escpos_bytes_validos(self) -> None:
		data = {
			"encabezado": {
				"institucion_nombre": "CLUB TEST",
				"institucion_direccion": "CALLE 123",
				"cuit": "30-11111111-1",
				"condicion_iva": "IVA RESPONSABLE",
			},
			"comprobante": "PE-001",
			"fecha": "01/07/2026",
			"hora": "10:00",
			"lineas": [{"concepto": "CUOTA", "monto": 1000}],
			"total": 1000,
			"mensaje_pie": "GRACIAS",
			"ancho_papel_mm": 58,
		}
		raw = render_recibo_escpos(data)
		self.assertTrue(raw.startswith(_ESC_INIT))
		self.assertIn(_ESC_CUT, raw)
		decoded = raw.decode("latin-1", errors="ignore")
		self.assertIn("CLUB TEST", decoded)
		self.assertIn("CUOTA", decoded)


class TestReciboPagoIntegracion(MembersTestCase):
	_GEN = "2026-06-01"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		if frappe.db.db_type == "postgres":
			apply_patch()
		self._secretaria = make_secretaria_user("secretaria.recibo@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.recibo_institucion_nombre = "INSTITUCION CULTURAL Y DEPORTIVA PEDRO ECHAGUE"
		settings.recibo_institucion_direccion = "PORTELA 836 - CABA"
		settings.recibo_cuit = "30-12345678-9"
		settings.recibo_condicion_iva = "IVA RESPONSABLE"
		settings.recibo_mensaje_pie = "SOMOS ECHAGUE, SOMOS FAMILIA !!"
		settings.recibo_ancho_papel_mm = "58"
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.save(ignore_permissions=True)

	def test_build_recibo_desde_payment_entry(self) -> None:
		socio = insert_socio(dni="99004001", email="recibo@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test recibo")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)
		self.assertTrue(invoice_name)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro(socio.name, invoice_name, mode_of_payment="Cash")
		finally:
			frappe.set_user("Administrator")

		self.assertIn("recibo", result)
		recibo = result["recibo"]
		self.assertEqual(recibo["comprobante"], result["payment_entry"])
		self.assertGreater(recibo["total"], 0)
		self.assertTrue(recibo["lineas"])
		self.assertTrue(recibo["texto"])
		raw = base64.b64decode(recibo["escpos_base64"])
		self.assertTrue(raw.startswith(_ESC_INIT))

	def test_get_recibo_pago_permiso(self) -> None:
		socio = insert_socio(dni="99004002", email="recibo2@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test recibo perm")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro(socio.name, invoice_name, mode_of_payment="Cash")
			recibo = get_recibo_pago(result["payment_entry"])
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(recibo["comprobante"], result["payment_entry"])

	def test_get_recibo_pago_sin_permiso(self) -> None:
		socio = insert_socio(dni="99004003", email="recibo3@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test recibo deny")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro(socio.name, invoice_name, mode_of_payment="Cash")
		finally:
			frappe.set_user("Administrator")

		guest = "guest.recibo@example.com"
		if not frappe.db.exists("User", guest):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": guest,
					"first_name": "Guest",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)

		frappe.set_user(guest)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_recibo_pago(result["payment_entry"])
		finally:
			frappe.set_user("Administrator")

	def test_build_recibo_pago_funcion_directa(self) -> None:
		socio = insert_socio(dni="99004004", email="recibo4@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test build recibo")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro(socio.name, invoice_name, mode_of_payment="Cash")
			recibo = build_recibo_pago(result["payment_entry"])
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(recibo["ancho_papel_mm"], 58)
		self.assertIn("INSTITUCION CULTURAL", recibo["texto"])

	def test_recibo_incluye_periodo_en_concepto(self) -> None:
		socio = insert_socio(dni="99004005", email="recibo.periodo@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test recibo periodo")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)
		self.assertTrue(invoice_name)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro(socio.name, invoice_name, mode_of_payment="Cash")
			recibo = build_recibo_pago(result["payment_entry"])
		finally:
			frappe.set_user("Administrator")

		conceptos = " | ".join(row["concepto"] for row in recibo["lineas"])
		self.assertIn("06/2026", conceptos)

	def test_recibo_mora_incluye_composicion(self) -> None:
		from club_management.members.services.mora_al_cobro import preparar_facturas_cobro_con_mora

		settings = frappe.get_single("Club Settings")
		settings.dia_primer_vencimiento = 10
		settings.recargo_mes_vencido_pct = 5
		settings.recargo_post_vencimiento_pct = 10
		item_code = "TEST-ITEM-MORA-RECIBO"
		if not frappe.db.exists("Item", item_code):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": "Mora recibo test",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 0,
				}
			).insert(ignore_permissions=True)
		settings.item_recargo_mora = item_code
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.monto = 10000
		settings.save(ignore_permissions=True)

		socio = insert_socio(dni="99004006", email="recibo.mora@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test recibo mora")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date="2026-03-01")
		settings = frappe.get_single("Club Settings")
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.monto = 12000
		settings.save(ignore_permissions=True)

		frappe.set_user(self._secretaria)
		try:
			preparar_facturas_cobro_con_mora(
				socio.name, [invoice_name], posting_date="2026-04-15"
			)
			result = registrar_cobro(socio.name, invoice_name, mode_of_payment="Cash", posting_date="2026-04-15")
			recibo = build_recibo_pago(result["payment_entry"])
		finally:
			frappe.set_user("Administrator")

		conceptos = " | ".join(row["concepto"] for row in recibo["lineas"])
		self.assertIn("03/2026", conceptos)
		self.assertTrue(
			any(
				"5%" in (row["concepto"] or "") or "MORA" in (row["concepto"] or "").upper()
				for row in recibo["lineas"]
			),
			msg=conceptos,
		)

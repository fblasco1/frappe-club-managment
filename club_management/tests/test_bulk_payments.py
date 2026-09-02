"""Tests de carga masiva de cobranzas.

Spec: `club_management/specs/carga_masiva_cobranzas.md`
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import frappe
from frappe.utils import add_days, flt, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user
from club_management.scripts.bulk_io import parse_fecha, parse_monto
from club_management.scripts.bulk_payments import (
	_excedente_saldo_favor_informe,
	_tolerancia_menor_error_cobranza_500,
	_tolerar_cobrador_mora10_en_lugar_15,
	clasificar_cobro_cuota_informe,
	map_medio_pago,
	run as run_bulk_payments,
)


def _write_csv(header: str, *lines: str) -> str:
	handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
	handle.write(header + "\n")
	for line in lines:
		handle.write(line + "\n")
	handle.close()
	return handle.name


class TestBulkPaymentsHelpers(MembersTestCase):
	def test_clasificar_cuota_acepta_tarifa_hermano_en_concepto_menor(self) -> None:
		"""Informe «Menor» con monto 2° hermano (+15 %) debe clasificarse como cobro válido."""
		result = clasificar_cobro_cuota_informe(
			"Cuota Social Menor",
			31625.0,
			"07/2026",
			"2026-08-10",
			"12042",
		)
		self.assertIsNotNone(result)
		self.assertEqual(result[0], "cobrar")
		self.assertEqual(result[1], 31625.0)

	def test_clasificar_cuota_acepta_base_menor_sobre_socio_segundo_hermano(self) -> None:
		result = clasificar_cobro_cuota_informe(
			"Cuota Social Menor",
			28500.0,
			"08/2026",
			"2026-08-05",
			"10949",
		)
		self.assertIsNotNone(result)
		self.assertEqual(result[0], "cobrar")

	def test_tolerancia_menor_menos_500_pre_agosto(self) -> None:
		self.assertTrue(
			_tolerancia_menor_error_cobranza_500(
				"Cuota Social Menor", 32275.0, 32775.0, "07/2026"
			)
		)
		self.assertFalse(
			_tolerancia_menor_error_cobranza_500(
				"Cuota Social Menor", 32275.0, 32775.0, "08/2026"
			)
		)

	def test_tolerar_cobrador_mora10(self) -> None:
		self.assertTrue(
			_tolerar_cobrador_mora10_en_lugar_15(29150.0, 30475.0, 26500.0)
		)

	def test_excedente_saldo_favor_hasta_500(self) -> None:
		self.assertEqual(_excedente_saldo_favor_informe(32920.0, 32775.0), 145.0)
		self.assertIsNone(_excedente_saldo_favor_informe(35000.0, 32775.0))

	def test_map_medio_pago_aliases(self) -> None:
		self.assertEqual(map_medio_pago("Efectivo"), "Cash")
		self.assertEqual(map_medio_pago("Transferencia"), "Wire Transfer")
		self.assertEqual(map_medio_pago("Cheque"), "Cheque")
		self.assertIsNone(map_medio_pago("trueque"))

	def test_premini_a_es_u9_azul_minibasquet_no_escuelita(self) -> None:
		from club_management.scripts.informe_concepto_cobranza import (
			concepto_desde_comprobante,
			resolver_item_codes_concepto,
		)

		codes = resolver_item_codes_concepto("PRE-MINI A U9")
		self.assertEqual(codes, ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",))
		self.assertNotIn("ICDPE-BASQUET-ESCUELITA", codes)
		self.assertEqual(
			concepto_desde_comprobante("INF-2710-10800-08/2026-29000.0-PRE-MINI A U9"),
			"PRE-MINI A U9",
		)

	def test_parse_monto_y_fecha(self) -> None:
		self.assertEqual(parse_monto("12.500,50"), 12500.50)
		self.assertEqual(str(parse_fecha("15/08/2026")), "2026-08-15")
		self.assertEqual(str(parse_fecha("2026-08-15")), "2026-08-15")


class TestBulkPaymentsRun(MembersTestCase):
	_GEN = "2026-08-01"

	def setUp(self) -> None:
		super().setUp()
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.bulk.pay@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)

	def _socio_con_factura(self, dni: str, email: str) -> tuple[str, str, float]:
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test bulk pay")
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)
		if not invoice_name:
			self.skipTest("No se pudo generar deuda mensual de prueba")
		outstanding = flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount"))
		return socio.name, invoice_name, outstanding

	def test_dry_run_no_crea_payment_entry(self) -> None:
		socio_name, invoice_name, monto = self._socio_con_factura("88904101", "bulk.dry@example.com")
		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante",
			f"{socio_name},{monto},2026-08-05,Efectivo,REC-DRY-88904101",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(
				csv_path=path,
				dry_run=True,
				periodo="08/2026",
			)
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)

		self.assertEqual(result["simuladas"], 1)
		self.assertEqual(result["procesadas"], 0)
		self.assertFalse(frappe.db.exists("Payment Entry", {"reference_no": "REC-DRY-88904101"}))
		self.assertGreater(flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")), 0)

	def test_socio_no_encontrado(self) -> None:
		path = _write_csv(
			"nro_socio,dni,monto_abonado,fecha_pago,medio_pago,referencia_comprobante",
			"99999999,,100,2026-08-05,Efectivo,REC-X",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(csv_path=path, dry_run=True, periodo="08/2026")
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)
		self.assertEqual(result["inconsistencias"][0]["codigo"], "socio_no_encontrado")

	def test_monto_discordante(self) -> None:
		socio_name, _, monto = self._socio_con_factura("88904102", "bulk.disc@example.com")
		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante",
			f"{socio_name},{monto + 9999},2026-08-05,Efectivo,REC-DISC",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(csv_path=path, dry_run=True, periodo="08/2026")
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)
		self.assertEqual(result["inconsistencias"][0]["codigo"], "monto_discordante")

	def test_apply_crea_pe_e_idempotencia(self) -> None:
		socio_name, invoice_name, monto = self._socio_con_factura("88904103", "bulk.apply@example.com")
		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante",
			f"{socio_name},{monto},2026-08-05,Transferencia,REC-APPLY-88904103",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(
				csv_path=path,
				dry_run=False,
				periodo="08/2026",
				confirm="local-dev",
			)
			again = run_bulk_payments(
				csv_path=path,
				dry_run=False,
				periodo="08/2026",
				confirm="local-dev",
			)
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)

		self.assertEqual(result["procesadas"], 1)
		self.assertEqual(again["ya_procesado"], 1)
		pe_name = result["payment_entries"][0]
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "mode_of_payment"), "Wire Transfer")
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")), 0)

	def test_fecha_futura(self) -> None:
		socio_name, _, monto = self._socio_con_factura("88904104", "bulk.fut@example.com")
		futura = add_days(today(), 3)
		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante",
			f"{socio_name},{monto},{futura},Efectivo,REC-FUT",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(csv_path=path, dry_run=True, periodo="08/2026")
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)
		self.assertEqual(result["inconsistencias"][0]["codigo"], "fecha_invalida")

	def test_concepto_arancel_en_factura_multilinea(self) -> None:
		"""Informe por «Adicional Basquet Escuelita» debe matchear solo la línea de arancel."""
		from club_management.members.services.cobranza_manual import (
			SALES_INVOICE_DOCTYPE,
			_campo_periodo_cobro,
			_campo_socio_en,
			_default_company,
			ensure_customer_for_socio,
		)
		from club_management.members.services.mora_al_cobro import calcular_exigido_linea_factura
		from club_management.members.services.socio_transitions import cambiar_estado

		socio = insert_socio(dni="88904105", email="bulk.concept@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test concepto bulk")
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		item_cuota = frappe.db.get_value("Club Settings", None, "item_cuota_social") or "ICDPE-CUOTA-SOCIAL"
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio.name),
			"company": _default_company(),
			"posting_date": "2026-08-01",
			"due_date": "2026-08-01",
			"set_posting_time": 1,
			campo: socio.name,
			"items": [
				{"item_code": item_cuota, "qty": 1, "rate": 28500, "description": "Cuota social"},
				{
					"item_code": "ICDPE-BASQUET-ESCUELITA",
					"qty": 1,
					"rate": 21000,
					"description": "Arancel escuelita",
				},
			],
		}
		if campo_periodo:
			payload[campo_periodo] = "08/2026"
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()

		info = calcular_exigido_linea_factura(
			doc.name,
			"ICDPE-BASQUET-ESCUELITA",
			socio.name,
			posting_date="2026-08-05",
		)
		self.assertAlmostEqual(info["monto_exigido"], 21000.0, places=2)

		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante,concepto,periodo",
			f"{socio.name},21000,2026-08-05,Efectivo,REC-CONC-88904105,Adicional Basquet Escuelita,08/2026",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(csv_path=path, dry_run=True, periodo="08/2026")
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)

		self.assertEqual(result["simuladas"], 1)
		self.assertEqual(result["procesadas"], 0)
		self.assertGreater(flt(frappe.db.get_value("Sales Invoice", doc.name, "outstanding_amount")), 0)

	def test_concepto_cuota_con_mora_post_segundo(self) -> None:
		"""Informe con mora (+15 %) debe matchear la línea facturada, no solo el neto."""
		from club_management.members.services.cobranza_manual import (
			SALES_INVOICE_DOCTYPE,
			_campo_periodo_cobro,
			_campo_socio_en,
			_default_company,
			ensure_customer_for_socio,
		)
		from club_management.members.services.socio_transitions import cambiar_estado

		socio = insert_socio(dni="88904106", email="bulk.mora@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test mora bulk")
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		item_cuota = frappe.db.get_value("Club Settings", None, "item_cuota_social") or "ICDPE-CUOTA-SOCIAL"
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio.name),
			"company": _default_company(),
			"posting_date": "2026-06-01",
			"due_date": "2026-06-10",
			"set_posting_time": 1,
			campo: socio.name,
			"items": [{"item_code": item_cuota, "qty": 1, "rate": 31000, "description": "Cuota social"}],
		}
		if campo_periodo:
			payload[campo_periodo] = "06/2026"
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()

		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante,concepto,periodo",
			f"{socio.name},35650,2026-08-06,Efectivo,REC-MORA-88904106,Cuota Social Activo,06/2026",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(csv_path=path, dry_run=True, periodo="06/2026")
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)

		self.assertEqual(result["simuladas"], 1, result.get("inconsistencias"))
		self.assertEqual(result["inconsistencias"], [])

	def _ensure_item(self, code: str, rate: float) -> str:
		if frappe.db.exists("Item", code):
			return code
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": rate,
			}
		).insert(ignore_permissions=True)
		return code

	def _factura_cuota_y_arancel(
		self,
		*,
		dni: str,
		email: str,
		item_arancel: str,
		rate_cuota: float = 28500,
		rate_arancel: float = 28500,
		desc_arancel: str = "Arancel actividad",
	) -> tuple[str, str]:
		from club_management.members.services.cobranza_manual import (
			SALES_INVOICE_DOCTYPE,
			_campo_periodo_cobro,
			_campo_socio_en,
			_default_company,
			ensure_customer_for_socio,
		)

		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test bulk multilinea")
		self._ensure_item(item_arancel, rate_arancel)
		item_cuota = frappe.db.get_value("Club Settings", None, "item_cuota_social") or "ICDPE-CUOTA-SOCIAL"
		if not frappe.db.exists("Item", item_cuota):
			self._ensure_item(item_cuota, rate_cuota)
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio.name),
			"company": _default_company(),
			"posting_date": "2026-08-01",
			"due_date": "2026-08-01",
			"set_posting_time": 1,
			campo: socio.name,
			"items": [
				{"item_code": item_cuota, "qty": 1, "rate": rate_cuota, "description": "Cuota social"},
				{
					"item_code": item_arancel,
					"qty": 1,
					"rate": rate_arancel,
					"description": desc_arancel,
				},
			],
		}
		if campo_periodo:
			payload[campo_periodo] = "08/2026"
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return socio.name, doc.name

	def test_cuota_y_premini_misma_factura_multilinea(self) -> None:
		"""Cuota + PRE-MINI A no reserva la SI completa; imputa el arancel (minibasquet)."""
		socio_name, invoice_name = self._factura_cuota_y_arancel(
			dni="88904111",
			email="bulk.premini@example.com",
			item_arancel="ICDPE-BASQUET-MASCULINO-MINIBASQUET",
		)
		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante,concepto,periodo",
			f"{socio_name},28500,2026-08-03,Efectivo,REC-CUOTA-88904111,Cuota Social Menor,08/2026",
			f"{socio_name},29000,2026-08-03,Efectivo,REC-PREMINI-88904111,PRE-MINI A U9,08/2026",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(
				csv_path=path,
				dry_run=False,
				periodo="08/2026",
				confirm="local-dev",
			)
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)

		self.assertEqual(result["procesadas"], 2, result.get("inconsistencias"))
		self.assertEqual(result["inconsistencias"], [])
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")), 0)

	def test_concepto_sin_linea_no_es_ya_saldada_por_otra_factura(self) -> None:
		socio_name, _invoice_name = self._factura_cuota_y_arancel(
			dni="88904112",
			email="bulk.yasald@example.com",
			item_arancel="ICDPE-BASQUET-MASCULINO-MINIBASQUET",
		)
		path = _write_csv(
			"nro_socio,monto_abonado,fecha_pago,medio_pago,referencia_comprobante,concepto,periodo",
			f"{socio_name},2000,2026-08-03,Efectivo,REC-FED-88904112,C FED U9/U11 MASC/FEM,08/2026",
		)
		frappe.set_user(self._secretaria)
		try:
			result = run_bulk_payments(csv_path=path, dry_run=True, periodo="08/2026")
		finally:
			frappe.set_user("Administrator")
			Path(path).unlink(missing_ok=True)

		self.assertTrue(result["inconsistencias"])
		self.assertEqual(result["inconsistencias"][0]["codigo"], "sin_factura_impaga")

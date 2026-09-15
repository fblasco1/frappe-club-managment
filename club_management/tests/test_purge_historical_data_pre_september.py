"""Tests de purga / migración histórica pre-septiembre.

Spec: `club_management/specs/purga_migracion_historica_pre_septiembre.md`
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import frappe
from frappe.utils import flt, getdate

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	registrar_cobro_parcial_factura,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user
from club_management.scripts.purge_historical_data_pre_september import (
	CONFIRM_PURGE_PROD,
	SEPT_START,
	assert_pre_september,
	combos_a_facturar,
	inventariar_purga,
	periodo_leq,
	run as run_purge,
	snapshot_septiembre,
)

_HEADER = "nro_socio,monto_abonado,fecha_pago,medio_pago,periodo,concepto,referencia_comprobante"


class TestPurgeHistoricalDataPreSeptember(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.purge.hist@example.com")
		sync_cuotas_sociales_club()
		self._tmp: list[str] = []

	def tearDown(self) -> None:
		for path in self._tmp:
			Path(path).unlink(missing_ok=True)
			Path(f"{path}.purga_migracion.json").unlink(missing_ok=True)
			Path(f"{path}.purga_migracion.auditoria.json").unlink(missing_ok=True)
		super().tearDown()

	def _csv(self, *lines: str) -> str:
		handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
		handle.write(_HEADER + "\n")
		for line in lines:
			handle.write(line + "\n")
		handle.close()
		self._tmp.append(handle.name)
		return handle.name

	def _socio(self, dni: str, email: str) -> str:
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test purge hist")
		return socio.name

	def _factura(
		self,
		socio_name: str,
		*,
		periodo: str,
		posting_date: str,
		rate: float = 28500.0,
		item_code: str = "ICDPE-BASQUET-ESCUELITA",
		description: str = "Arancel",
	) -> str:
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		payload: dict[str, Any] = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio_name),
			"company": _default_company(),
			"posting_date": posting_date,
			"due_date": posting_date,
			"set_posting_time": 1,
			campo: socio_name,
			"items": [
				{"item_code": item_code, "qty": 1, "rate": rate, "description": description},
			],
		}
		if campo_periodo:
			payload[campo_periodo] = periodo
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _cobrar(self, socio_name: str, invoice: str, monto: float, fecha: str, ref: str) -> str:
		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro_parcial_factura(
				socio_name,
				invoice,
				monto,
				mode_of_payment="Cash",
				posting_date=fecha,
				reference_no=ref,
				auto_submit=True,
			)
		finally:
			frappe.set_user("Administrator")
		pes = result.get("payment_entries") or []
		return pes[0] if pes else ""

	def test_periodo_leq(self) -> None:
		self.assertTrue(periodo_leq("07/2026", "08/2026"))
		self.assertTrue(periodo_leq("08/2026", "08/2026"))
		self.assertFalse(periodo_leq("09/2026", "08/2026"))

	def test_safety_guard_rechaza_septiembre(self) -> None:
		socio = self._socio("88908001", "purge.safety@example.com")
		inv_sep = self._factura(socio, periodo="09/2026", posting_date="2026-09-01")
		with self.assertRaises(frappe.ValidationError):
			assert_pre_september(SALES_INVOICE_DOCTYPE, inv_sep)

	def test_dry_run_no_cancela_ni_crea(self) -> None:
		socio = self._socio("88908002", "purge.dry@example.com")
		inv = self._factura(socio, periodo="08/2026", posting_date="2026-08-01")
		pe = self._cobrar(socio, inv, 28500, "2026-08-12", f"INF-1-{socio}-08/2026-28500-U13")
		path = self._csv(f"{socio},28500,2026-08-12,Efectivo,08/2026,INFA A U13,")
		antes = snapshot_septiembre()
		result = run_purge(
			csv_path=path,
			dry_run=True,
			enforce_csv_totales=False,
			solo_pe=[pe],
			solo_si=[inv],
		)
		self.assertTrue(result["septiembre_ok"])
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 1)
		self.assertEqual(snapshot_septiembre(), antes)
		self.assertIn(inv, result["purga"]["sales_invoices"])
		self.assertIn(pe, result["purga"]["payment_entries"])

	def test_purga_preserva_septiembre(self) -> None:
		socio = self._socio("88908003", "purge.sep@example.com")
		inv_ago = self._factura(socio, periodo="08/2026", posting_date="2026-08-01")
		pe = self._cobrar(socio, inv_ago, 28500, "2026-08-12", f"INF-1-{socio}-08/2026-28500-U13")
		inv_sep = self._factura(socio, periodo="09/2026", posting_date="2026-09-01", rate=30000)
		path = self._csv(f"{socio},28500,2026-08-12,Efectivo,08/2026,INFA A U13,")
		antes = snapshot_septiembre()
		result = run_purge(
			csv_path=path,
			dry_run=False,
			confirm="local-dev",
			enforce_csv_totales=False,
			skip_cobros=True,
			solo_pe=[pe],
			solo_si=[inv_ago],
		)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_ago, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_sep, "docstatus"), 1)
		self.assertEqual(snapshot_septiembre(), antes)
		self.assertTrue(result["septiembre_ok"])
		self.assertGreaterEqual(
			getdate(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_sep, "posting_date")), SEPT_START
		)

	def test_gate_apply_exige_confirm(self) -> None:
		path = self._csv("1,100,2026-08-01,Efectivo,08/2026,U17 FLEX,")
		with self.assertRaises(frappe.ValidationError):
			run_purge(
				csv_path=path,
				dry_run=False,
				confirm="",
				enforce_csv_totales=False,
				solo_pe=[],
				solo_si=[],
			)

	def test_combos_excluye_adelantados_y_carnet(self) -> None:
		socio = self._socio("88908004", "purge.combos@example.com")
		path = self._csv(
			f"{socio},21000,2026-08-05,Transferencia,08/2026,Adicional Basquet Escuelita,",
			f"{socio},21000,2026-08-05,Transferencia,09/2026,Adicional Basquet Escuelita,",
			f"{socio},5000,2026-08-05,Efectivo,08/2026,CARNET,",
		)
		from club_management.scripts.purge_historical_data_pre_september import _filas_csv

		filas = _filas_csv(path)
		combos = combos_a_facturar(filas)
		self.assertEqual(len(combos), 1)
		self.assertEqual(combos[0]["periodo"], "08/2026")

	def test_anticipo_periodo_septiembre(self) -> None:
		socio = self._socio("88908005", "purge.adv@example.com")
		# Necesita al menos una SI submitted para armar PE anticipo (helper ERPNext)
		inv_sep = self._factura(socio, periodo="09/2026", posting_date="2026-09-01", rate=21000)
		path = self._csv(
			f"{socio},21000,2026-08-15,Transferencia,09/2026,Adicional Basquet Escuelita,",
		)
		antes = snapshot_septiembre()
		result = run_purge(
			csv_path=path,
			dry_run=False,
			confirm="local-dev",
			enforce_csv_totales=False,
			skip_purge=True,
			skip_facturas=True,
			solo_pe=[],
			solo_si=[],
		)
		self.assertEqual(result["estados"].get("anticipo"), 1)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_sep, "docstatus"), 1)
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_sep, "outstanding_amount")), 21000)
		self.assertEqual(snapshot_septiembre(), antes)

	def test_inventario_no_incluye_septiembre(self) -> None:
		socio = self._socio("88908006", "purge.inv@example.com")
		inv_ago = self._factura(socio, periodo="08/2026", posting_date="2026-08-01")
		inv_sep = self._factura(socio, periodo="09/2026", posting_date="2026-09-01")
		inv = inventariar_purga(solo_si=[inv_ago, inv_sep], solo_pe=[])
		self.assertIn(inv_ago, inv["sales_invoices"])
		self.assertNotIn(inv_sep, inv["sales_invoices"])

	def test_gate_prod_token(self) -> None:
		path = self._csv("1,100,2026-08-01,Efectivo,08/2026,U17 FLEX,")
		with patch(
			"club_management.scripts.purge_historical_data_pre_september.is_production_site",
			return_value=True,
		):
			with self.assertRaises(frappe.ValidationError):
				run_purge(
					csv_path=path,
					dry_run=False,
					confirm="local-dev",
					enforce_csv_totales=False,
					solo_pe=[],
					solo_si=[],
				)
			ok = run_purge(
				csv_path=path,
				dry_run=False,
				confirm=CONFIRM_PURGE_PROD,
				enforce_csv_totales=False,
				skip_purge=True,
				skip_facturas=True,
				skip_cobros=True,
				solo_pe=[],
				solo_si=[],
			)
			self.assertTrue(ok["septiembre_ok"])

	def test_cto_comp_emite_si_historica_dia_1(self) -> None:
		"""CTO COMP no usa prepago (today); posting = día 1 del período."""
		from club_management.scripts.informe_concepto_cobranza import ITEM_CUOTA_COMPLEMENTARIA
		from club_management.scripts.purge_historical_data_pre_september import (
			emitir_facturas_historicas,
		)

		socio = self._socio("88908007", "purge.cto@example.com")
		combo = {
			"socio": socio,
			"nro_socio": socio,
			"concepto": "CTO COMP BASQ ESC/FEM",
			"periodo": "08/2026",
			"monto_csv": 4000.0,
			"fecha_pago": getdate("2026-08-20"),
		}
		antes = snapshot_septiembre()
		result = emitir_facturas_historicas([combo], dry_run=False, commit_every=0)
		self.assertEqual(result["errores_count"], 0, result.get("errores"))
		self.assertEqual(result["creadas_count"], 1)
		name = result["creadas"][0]["sales_invoice"]
		self.assertTrue(name)
		posting = getdate(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "posting_date"))
		self.assertEqual(posting, getdate("2026-08-01"))
		item = frappe.db.get_value("Sales Invoice Item", {"parent": name}, "item_code")
		self.assertEqual(item, ITEM_CUOTA_COMPLEMENTARIA)
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "grand_total")), 4000)
		self.assertEqual(snapshot_septiembre(), antes)

	def test_mora_ajuste_misma_fecha_que_cobro(self) -> None:
		"""SI de mora y PE llevan posting_date = fecha_pago (no today/septiembre)."""
		from club_management.scripts.bulk_payments import _registrar_cobro_concepto_informe

		socio = self._socio("88908008", "purge.mora@example.com")
		inv = self._factura(
			socio,
			periodo="07/2026",
			posting_date="2026-07-01",
			rate=10000.0,
			item_code="ICDPE-CUOTA-SOCIAL",
			description="Cuota Social Activo (07/2026)",
		)
		fecha_pago = "2026-08-25"
		antes = snapshot_septiembre()
		frappe.set_user(self._secretaria)
		try:
			result = _registrar_cobro_concepto_informe(
				socio,
				inv,
				11500.0,
				mode_of_payment="Cash",
				posting_date=fecha_pago,
				reference_no=f"INF-test-mora-{socio}",
				auto_submit=True,
				concepto="Cuota Social Activo",
				periodo_fila="07/2026",
			)
		finally:
			frappe.set_user("Administrator")
		pes = result.get("payment_entries") or []
		self.assertTrue(pes)
		for pe_name in pes:
			self.assertEqual(
				getdate(frappe.db.get_value("Payment Entry", pe_name, "posting_date")),
				getdate(fecha_pago),
			)
		mora_item = frappe.db.get_single_value("Club Settings", "item_recargo_mora")
		mora_sis = frappe.get_all(
			"Payment Entry Reference",
			filters={
				"parent": ["in", pes],
				"reference_doctype": "Sales Invoice",
			},
			fields=["reference_name"],
		)
		for ref in mora_sis:
			si_name = ref.reference_name
			has_mora = frappe.db.exists(
				"Sales Invoice Item", {"parent": si_name, "item_code": mora_item}
			)
			if not has_mora:
				continue
			posting = getdate(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_name, "posting_date"))
			self.assertEqual(posting, getdate(fecha_pago))
			self.assertLess(posting, SEPT_START)
		self.assertEqual(snapshot_septiembre(), antes)

	def test_cancelar_mora_huerfana_origen_pagado(self) -> None:
		"""Mora impaga sin PE, con origen Paid → se cancela."""
		from club_management.scripts.purge_historical_data_pre_september import (
			cancelar_mora_huerfanas,
			inventariar_mora_huerfanas,
		)

		socio = self._socio("88908009", "purge.mora.huerfana@example.com")
		origen = self._factura(
			socio,
			periodo="07/2026",
			posting_date="2026-07-01",
			rate=10000.0,
			item_code="ICDPE-CUOTA-SOCIAL",
			description="Cuota Social Activo (07/2026)",
		)
		# Saldar origen sin crear mora vía flujo normal
		self._cobrar(socio, origen, 10000.0, "2026-07-05", f"INF-huerfana-{socio}")
		mora_item = frappe.db.get_single_value("Club Settings", "item_recargo_mora") or "RECARGO-MORA"
		if not frappe.db.exists("Item", mora_item):
			self.skipTest("Sin item de mora configurado")
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		payload: dict[str, Any] = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio),
			"company": _default_company(),
			"posting_date": "2026-08-15",
			"due_date": "2026-08-15",
			"set_posting_time": 1,
			campo: socio,
			"remarks": f"Mora al cobro {origen}",
			"items": [
				{"item_code": mora_item, "qty": 1, "rate": 1500.0, "description": "Mora test"},
			],
		}
		if campo_periodo:
			payload[campo_periodo] = "07/2026-MORA"
		mora = frappe.get_doc(payload)
		mora.insert(ignore_permissions=True)
		mora.submit()

		cands = inventariar_mora_huerfanas(socio_name=socio)
		self.assertTrue(any(c["name"] == mora.name for c in cands))
		result = cancelar_mora_huerfanas(
			socio_name=socio, dry_run=False, confirm="local-dev", commit_every=0
		)
		self.assertGreaterEqual(result["canceladas_count"], 1)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, mora.name, "docstatus"), 2)

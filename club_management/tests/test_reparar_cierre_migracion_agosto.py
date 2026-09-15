"""Tests reparación cierre migración agosto.

Spec: `club_management/specs/reparacion_cierre_migracion_agosto.md`
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import frappe
from frappe.utils import flt

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
	cancelar_mora_huerfanas,
	inventariar_mora_huerfanas,
)
from club_management.scripts.reparar_cierre_migracion_agosto import (
	SOCIO_ALIAS_PADRON,
	_procesar_fila_imputacion,
	resolve_socio_csv,
)

_HEADER = "nro_socio,monto_abonado,fecha_pago,medio_pago,periodo,concepto,referencia_comprobante"


class TestRepararCierreMigracionAgosto(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.reparar.cierre@example.com")
		sync_cuotas_sociales_club()

	def _socio(self, dni: str, email: str) -> str:
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test reparar cierre")
		return socio.name

	def _factura(
		self,
		socio_name: str,
		*,
		periodo: str,
		posting_date: str,
		rate: float,
		item_code: str = "CLUB-Cuota-Social-Base",
		description: str = "Cuota",
		remarks: str = "",
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
		if remarks:
			payload["remarks"] = remarks
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

	def test_resolve_socio_alias(self) -> None:
		canonico = self._socio("88909101", "alias.9484@example.com")
		with patch.dict(SOCIO_ALIAS_PADRON, {"12009": canonico}, clear=False):
			self.assertEqual(resolve_socio_csv("12009"), canonico)
		self.assertIsNone(resolve_socio_csv("99999991"))

	def test_mora_residual_con_pe_parcial_se_limpia_con_cn(self) -> None:
		"""Origen Paid + mora con PE parcial → CN deja outstanding≈0."""
		socio = self._socio("88909102", "mora.residual@example.com")
		item_cuota = frappe.db.get_single_value("Club Settings", "item_cuota_social") or "CLUB-Cuota-Social-Base"
		if not frappe.db.exists("Item", item_cuota):
			self.skipTest("Sin ítem cuota social")
		mora_item = frappe.db.get_single_value("Club Settings", "item_recargo_mora") or "RECARGO-MORA"
		if not frappe.db.exists("Item", mora_item):
			self.skipTest("Sin item de mora configurado")

		origen = self._factura(
			socio,
			periodo="07/2026",
			posting_date="2026-07-01",
			rate=10000.0,
			item_code=item_cuota,
			description="Cuota 07",
		)
		self._cobrar(socio, origen, 10000.0, "2026-07-05", f"INF-base-{socio}")

		mora = self._factura(
			socio,
			periodo="07/2026-MORA",
			posting_date="2026-08-14",
			rate=9000.0,
			item_code=mora_item,
			description="Mora test residual",
			remarks=f"Mora al cobro {origen}",
		)
		self._cobrar(socio, mora, 3000.0, "2026-08-14", f"INF-mora-parcial-{socio}")
		out_antes = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, mora, "outstanding_amount"))
		self.assertGreater(out_antes, 5000)

		cands = inventariar_mora_huerfanas(socio_name=socio)
		self.assertTrue(any(c["name"] == mora and c.get("accion") == "credit_note" for c in cands))

		result = cancelar_mora_huerfanas(
			socio_name=socio, dry_run=False, confirm="local-dev", commit_every=0
		)
		self.assertGreaterEqual(result["canceladas_count"], 1)
		out_despues = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, mora, "outstanding_amount"))
		self.assertLessEqual(out_despues, 0.05)

	def test_procesar_adelantado_09_contra_si_existente(self) -> None:
		socio = self._socio("88909103", "adelantado.09@example.com")
		item_cuota = frappe.db.get_single_value("Club Settings", "item_cuota_social") or "CLUB-Cuota-Social-Base"
		if not frappe.db.exists("Item", item_cuota):
			self.skipTest("Sin ítem cuota social")
		si = self._factura(
			socio,
			periodo="09/2026",
			posting_date="2026-08-31",
			rate=28500.0,
			item_code=item_cuota,
			description="Cuota Social Menor (09/2026)",
		)
		fila = {
			"fila": 99,
			"nro_socio": socio,
			"socio": socio,
			"periodo": "09/2026",
			"concepto": "Cuota Social Menor",
			"monto_csv": 28500.0,
			"fecha_pago": getdate_safe("2026-08-31"),
			"medio_pago": "Efectivo",
		}
		reg = _procesar_fila_imputacion(fila, dry_run=False, allow_adelantado=True)
		self.assertIn(reg["estado"], ("imputado", "imputado_con_facturacion"))
		self.assertEqual(reg["sales_invoice"], si)
		self.assertTrue(reg.get("payment_entry"))
		self.assertLessEqual(
			flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si, "outstanding_amount")), 0.05
		)


def getdate_safe(value: str):
	from frappe.utils import getdate

	return getdate(value)

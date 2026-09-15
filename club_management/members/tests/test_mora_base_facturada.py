"""Tests de mora con base sobre el valor facturado (spec carga_masiva_cobranzas.md).

El importer consolidado valida la mora esperada sobre el `rate` facturado de la
línea de la SI, no sobre el valor vigente del ítem.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.mora_al_cobro import calcular_exigido_linea_factura
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio

ITEM_ARANCEL = "ICDPE-BASQUET-ESCUELITA"


class TestMoraBaseFacturada(MembersTestCase):
	_FROZEN_TODAY = "2026-08-10"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		if not frappe.db.exists("Item", ITEM_ARANCEL):
			self.skipTest("Ítem de arancel de prueba no disponible")
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
		self._today_patch = patch("frappe.utils.today", return_value=self._FROZEN_TODAY)
		self._today_patch.start()
		sync_cuotas_sociales_club()

	def tearDown(self) -> None:
		self._today_patch.stop()
		super().tearDown()

	def _factura_arancel(self, socio_name: str, *, periodo: str, rate: float) -> str:
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		payload: dict[str, Any] = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio_name, skip_permission_check=True),
			"company": _default_company(),
			"posting_date": self._FROZEN_TODAY,
			"due_date": self._FROZEN_TODAY,
			"set_posting_time": 1,
			campo: socio_name,
			"items": [
				{"item_code": ITEM_ARANCEL, "qty": 1, "rate": rate, "description": "Arancel escuelita"},
			],
		}
		if campo_periodo:
			payload[campo_periodo] = periodo
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def test_base_facturada_usa_rate_de_linea(self) -> None:
		"""Con `base='facturado'` la mora 15 % se calcula sobre el rate de la línea."""
		socio = insert_socio(dni="88906001", email="mora.base@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test mora base")
		frappe.db.set_value("Item", ITEM_ARANCEL, "standard_rate", 25000)
		invoice = self._factura_arancel(socio.name, periodo="07/2026", rate=21000)

		info = calcular_exigido_linea_factura(
			invoice,
			ITEM_ARANCEL,
			socio.name,
			posting_date="2026-08-10",
			base="facturado",
		)
		self.assertEqual(info["tramo"], "post_segundo")
		self.assertAlmostEqual(flt(info["monto_exigido"]), flt(21000 * 1.15, 2), places=2)

	def test_base_default_sigue_usando_valor_vigente(self) -> None:
		socio = insert_socio(dni="88906002", email="mora.vigente@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test mora vigente")
		frappe.db.set_value("Item", ITEM_ARANCEL, "standard_rate", 25000)
		invoice = self._factura_arancel(socio.name, periodo="07/2026", rate=21000)

		info = calcular_exigido_linea_factura(
			invoice,
			ITEM_ARANCEL,
			socio.name,
			posting_date="2026-08-10",
		)
		self.assertAlmostEqual(flt(info["monto_exigido"]), flt(25000 * 1.15, 2), places=2)

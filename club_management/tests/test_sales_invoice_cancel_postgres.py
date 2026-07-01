"""Tests cancelación Sales Invoice en PostgreSQL (spec sales_invoice_cancel_postgres.md)."""

from __future__ import annotations

import frappe
from frappe.utils import today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
    _campo_socio_en,
    _default_company,
    ensure_customer_for_socio,
    erpnext_cobranza_disponible,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestSalesInvoiceCancelPostgres(MembersTestCase):
    def setUp(self) -> None:
        super().setUp()
        if frappe.db.db_type != "postgres":
            self.skipTest("Solo PostgreSQL")
        if not erpnext_cobranza_disponible():
            self.skipTest("ERPNext Sales Invoice no instalado")
        apply_patch()
        self._secretaria = make_secretaria_user("secretaria.cancel.si@example.com")
        self._item_code = frappe.db.get_value("Item", {"is_sales_item": 1}, "name")
        if not self._item_code:
            self.skipTest("Sin ítem de venta en el sitio de prueba")

    def _socio_activo(self, *, dni: str, email: str):
        socio = insert_socio(dni=dni, email=email)
        cambiar_estado(socio.name, "Activo", motivo="Test cancel SI")
        return socio

    def _crear_factura(self, socio_name: str) -> frappe.model.document.Document:
        customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
        campo_socio = _campo_socio_en("Sales Invoice")
        inv = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "customer": customer,
                "company": _default_company(),
                "posting_date": today(),
                "due_date": today(),
                campo_socio: socio_name,
                "items": [{"item_code": self._item_code, "qty": 1, "rate": 1}],
            }
        )
        inv.insert(ignore_permissions=True)
        inv.submit()
        return inv

    def test_cancelar_sales_invoice_sin_pagos(self) -> None:
        socio = self._socio_activo(dni="99002001", email="cancel.si.test@example.com")
        inv = self._crear_factura(socio.name)

        frappe.set_user(self._secretaria)
        try:
            inv.cancel()
        finally:
            frappe.set_user("Administrator")

        inv.reload()
        self.assertEqual(inv.docstatus, 2)
        self.assertEqual(inv.status, "Cancelled")

        ple_delinked = frappe.db.sql(
            """
            SELECT COUNT(*) FROM "tabPayment Ledger Entry"
            WHERE voucher_type = %s AND voucher_no = %s AND delinked = 1
            """,
            (inv.doctype, inv.name),
        )[0][0]
        self.assertGreater(ple_delinked, 0)

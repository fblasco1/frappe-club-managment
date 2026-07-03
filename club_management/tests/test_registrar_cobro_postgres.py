"""Tests registrar cobro manual en PostgreSQL (bug B2 payment_entry)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
    erpnext_cobranza_disponible,
    registrar_cobro_manual,
)
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestRegistrarCobroPostgres(MembersTestCase):
    _GEN = "2026-06-01"

    def setUp(self) -> None:
        super().setUp()
        if frappe.db.db_type != "postgres":
            self.skipTest("Solo PostgreSQL")
        if not erpnext_cobranza_disponible():
            self.skipTest("ERPNext Sales Invoice no instalado")
        apply_patch()
        self._secretaria = make_secretaria_user("secretaria.cobro.pg@example.com")
        sync_cuotas_sociales_club()
        settings = frappe.get_single("Club Settings")
        if not settings.company:
            company = frappe.db.get_value("Company", {}, "name")
            if company:
                settings.company = company
                settings.save(ignore_permissions=True)

    def test_registrar_cobro_manual_crea_payment_entry(self) -> None:
        socio = insert_socio(dni="99003001", email="cobro.pg@example.com")
        cambiar_estado(socio.name, "Activo", motivo="Test cobro PG")
        invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)
        self.assertTrue(invoice_name)

        frappe.set_user(self._secretaria)
        try:
            pe_name = registrar_cobro_manual(socio.name, invoice_name)
        finally:
            frappe.set_user("Administrator")

        self.assertTrue(pe_name)
        self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)
        self.assertEqual(
            flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")),
            0,
        )

    def test_registrar_cobro_manual_respeta_modo_pago(self) -> None:
        socio = insert_socio(dni="99003002", email="cobro.mop@example.com")
        cambiar_estado(socio.name, "Activo", motivo="Test modo pago")
        invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._GEN)
        self.assertTrue(invoice_name)

        frappe.set_user(self._secretaria)
        try:
            pe_name = registrar_cobro_manual(
                socio.name,
                invoice_name,
                mode_of_payment="Wire Transfer",
            )
        finally:
            frappe.set_user("Administrator")

        self.assertEqual(
            frappe.db.get_value("Payment Entry", pe_name, "mode_of_payment"),
            "Wire Transfer",
        )

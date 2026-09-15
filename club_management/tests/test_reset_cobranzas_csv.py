"""Tests del reset limpio de cobranzas del CSV.

Spec: `club_management/specs/reset_cobranzas_csv.md`
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import frappe
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
from club_management.scripts.informe_concepto_cobranza import (
	referencia_informe,
	resolver_item_codes_concepto,
)
from club_management.scripts.reset_cobranzas_csv import (
	TARIFAS_PATIN_AGOSTO_2026,
	run as run_reset,
)

_HEADER = "nro_socio,monto_abonado,fecha_pago,medio_pago,periodo,concepto,referencia_comprobante"


class TestResetCobranzasCsv(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.reset.csv@example.com")
		sync_cuotas_sociales_club()
		self._tmp: list[str] = []

	def tearDown(self) -> None:
		for path in self._tmp:
			Path(path).unlink(missing_ok=True)
			Path(f"{path}.revision_manual.csv").unlink(missing_ok=True)
			Path(f"{path}.reset_inventario.json").unlink(missing_ok=True)
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
		cambiar_estado(socio.name, "Activo", motivo="Test reset csv")
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

	def _run(self, path: str, **kwargs: Any) -> dict[str, Any]:
		kwargs.setdefault("incluir_todo_periodo_cierre", False)
		return run_reset(csv_path=path, **kwargs)

	def test_dry_run_no_cancela(self) -> None:
		socio = self._socio("88907001", "reset.dry@example.com")
		inv = self._factura(socio, periodo="08/2026", posting_date="2026-08-01")
		pe = self._cobrar(socio, inv, 28500, "2026-08-12", f"INF-1-{socio}-08/2026-28500-INFA A U13")
		path = self._csv(f"{socio},28500,2026-08-12,Efectivo,08/2026,INFA A U13,")
		result = self._run(path, dry_run=True)
		self.assertIn(inv, result["sales_invoices"])
		self.assertIn(pe, result["payment_entries"])
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 1)

	def test_cancelar_agosto_preserva_septiembre(self) -> None:
		socio = self._socio("88907002", "reset.sep@example.com")
		inv_ago = self._factura(socio, periodo="08/2026", posting_date="2026-08-01")
		pe = self._cobrar(socio, inv_ago, 28500, "2026-08-12", f"INF-1-{socio}-08/2026-28500-U13")
		inv_mora = self._factura(
			socio,
			periodo="08/2026",
			posting_date="2026-09-01",
			rate=2850,
			description="Mora",
			remarks=f"Mora al cobro {inv_ago}",
		)
		inv_sep = self._factura(socio, periodo="09/2026", posting_date="2026-09-01", rate=28500)
		path = self._csv(f"{socio},28500,2026-08-12,Efectivo,08/2026,INFA A U13,")
		self._run(path, dry_run=False, confirm="local-dev", fase="cancelar")
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_ago, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_mora, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_sep, "docstatus"), 1)

	def test_julio_cobrado_en_agosto_entra_otro_julio_impago_no(self) -> None:
		pagado = self._socio("88907003", "reset.jul.pago@example.com")
		impago = self._socio("88907004", "reset.jul.impago@example.com")
		inv_jul = self._factura(pagado, periodo="07/2026", posting_date="2026-07-01")
		pe = self._cobrar(pagado, inv_jul, 28500, "2026-08-12", f"INF-2-{pagado}-07/2026-28500-Cuota")
		inv_jul_impago = self._factura(impago, periodo="07/2026", posting_date="2026-07-01")
		path = self._csv(f"{pagado},28500,2026-08-12,Efectivo,07/2026,Cuota Social Menor,")
		self._run(path, dry_run=False, confirm="local-dev", fase="cancelar")
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_jul, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_jul_impago, "docstatus"), 1)

	def test_cto_comp_agosto_entra(self) -> None:
		socio = self._socio("88907005", "reset.cto@example.com")
		item = "ICDPE-CARGO-VARIOS"
		if not frappe.db.exists("Item", item):
			item = "ICDPE-BASQUET-ESCUELITA"
		inv = self._factura(
			socio,
			periodo="08/2026",
			posting_date="2026-08-01",
			rate=6000,
			item_code=item,
			description="CTO COMP BASQ TIRA A/B/FLEX (08/2026)",
		)
		path = self._csv(f"{socio},6000,2026-08-12,Efectivo,08/2026,CTO COMP BASQ TIRA A/B/FLEX,")
		self._run(path, dry_run=False, confirm="local-dev", fase="cancelar")
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv, "docstatus"), 2)

	def test_apply_sin_confirm_falla(self) -> None:
		socio = self._socio("88907006", "reset.gate@example.com")
		path = self._csv(f"{socio},100,2026-08-12,Efectivo,08/2026,Cuota Social Menor,")
		with self.assertRaises(frappe.ValidationError):
			self._run(path, dry_run=False, confirm="", fase="cancelar")

	def test_referencia_informe_no_trunca_concepto_a_24(self) -> None:
		ref = referencia_informe(
			fila=1,
			numero_socio="8762",
			periodo="08/2026",
			monto=31350,
			concepto="ADICIONAL BASQUET ESCUELITA",
		)
		self.assertIn("ADICIONAL BASQUET ESCUELITA", ref)
		self.assertLessEqual(len(ref), 140)

	def test_cuota_hijo_2_y_3_mapean_categoria_hermano(self) -> None:
		hijo2 = resolver_item_codes_concepto("Cuota Social Menor Hijo 2º")
		hijo3 = resolver_item_codes_concepto("Cuota Social Menor Hijo 3")
		menor = resolver_item_codes_concepto("Cuota Social Menor")
		self.assertTrue(hijo2)
		self.assertEqual(hijo2, menor)
		self.assertEqual(hijo3, menor)

	def test_tarifas_patin_agosto_congeladas(self) -> None:
		self.assertEqual(TARIFAS_PATIN_AGOSTO_2026["ICDPE-PATIN-MINI"], 20500.0)
		self.assertEqual(TARIFAS_PATIN_AGOSTO_2026["ICDPE-PATIN-TEENS"], 20500.0)
		self.assertEqual(TARIFAS_PATIN_AGOSTO_2026["ICDPE-PATIN-INTERMEDIO"], 36000.0)
		self.assertEqual(TARIFAS_PATIN_AGOSTO_2026["ICDPE-PATIN-AVANZADO"], 42000.0)
		self.assertEqual(TARIFAS_PATIN_AGOSTO_2026["ICDPE-PATIN-DANZA"], 29500.0)
		self.assertEqual(TARIFAS_PATIN_AGOSTO_2026["ICDPE-PATIN-ADULTO"], 26500.0)

	def test_carnet_en_inventario_no_cancela_si(self) -> None:
		socio = self._socio("88907007", "reset.carnet@example.com")
		inv_carnet = self._factura(
			socio,
			periodo="08/2026",
			posting_date="2026-08-01",
			rate=3000,
			description="CARNET",
		)
		path = self._csv(f"{socio},3000,2026-08-12,Efectivo,08/2026,CARNET,")
		result = self._run(path, dry_run=True)
		self.assertEqual(result["carnet"]["filas"], 1)
		self.assertEqual(result["carnet"]["detalle"][0]["socio"], socio)
		self.assertNotIn(inv_carnet, result["sales_invoices"])
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_carnet, "docstatus"), 1)

	def test_aplicar_cancelacion_restaura_parche_delinked(self) -> None:
		import erpnext.accounts.utils as accounts_utils
		from club_management.integrations.payment_ledger_postgres import (
			_delink_original_entry_postgres,
		)
		from club_management.scripts.reset_cobranzas_csv import _aplicar_cancelacion

		accounts_utils._club_delink_original_entry_pg_patch = False
		accounts_utils.delink_original_entry = lambda *a, **k: None
		_aplicar_cancelacion({"payment_entries": [], "sales_invoices": []})
		self.assertIs(accounts_utils.delink_original_entry, _delink_original_entry_postgres)

	def test_adelantado_entra_al_reset_y_al_log(self) -> None:
		socio = self._socio("88907008", "reset.adelantado@example.com")
		inv_oct = self._factura(socio, periodo="10/2026", posting_date="2026-08-01", rate=21000)
		pe = self._cobrar(
			socio, inv_oct, 21000, "2026-08-12", f"INF-1-{socio}-10/2026-21000-INFA A U13"
		)
		inv_sep = self._factura(socio, periodo="09/2026", posting_date="2026-09-01", rate=28500)
		path = self._csv(f"{socio},21000,2026-08-12,Efectivo,10/2026,INFA A U13,")
		result = self._run(path, dry_run=False, confirm="local-dev", fase="cancelar")
		self.assertIn(inv_oct, result["sales_invoices"])
		self.assertNotIn(inv_sep, result["sales_invoices"])
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_oct, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_sep, "docstatus"), 1)
		motivos = {r["motivo"] for r in result["revision_manual"]}
		self.assertIn("excluido_adelantado", motivos)

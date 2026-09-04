"""Tests del importer consolidado de cobranzas con invariante de no-pérdida.

Spec: `club_management/specs/carga_masiva_cobranzas.md`
(sección «Importer consolidado con invariante de no-pérdida»)
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import Any

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
)
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user
from club_management.scripts.cobranzas_bulk_importer import run as run_importer

_HEADER = "nro_socio,monto_abonado,fecha_pago,medio_pago,periodo,concepto,referencia_comprobante"


def _write_csv(*lines: str) -> str:
	handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
	handle.write(_HEADER + "\n")
	for line in lines:
		handle.write(line + "\n")
	handle.close()
	return handle.name


def _leer_auditoria(path: str) -> list[dict[str, str]]:
	with open(path, encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


class TestCobranzasBulkImporter(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.importer@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)
		self._tmp_files: list[str] = []

	def tearDown(self) -> None:
		for path in self._tmp_files:
			Path(path).unlink(missing_ok=True)
			Path(f"{path}.auditoria.csv").unlink(missing_ok=True)
			Path(f"{path}.resumen.json").unlink(missing_ok=True)
		super().tearDown()

	def _csv(self, *lines: str) -> str:
		path = _write_csv(*lines)
		self._tmp_files.append(path)
		return path

	def _socio_activo(self, dni: str, email: str) -> str:
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test importer")
		return socio.name

	def _socio_con_cuota(self, dni: str, email: str, *, reference_date: str) -> tuple[str, str, float]:
		socio_name = self._socio_activo(dni, email)
		invoice_name = generar_deuda_mensual_socio(socio_name, reference_date=reference_date)
		if not invoice_name:
			self.skipTest("No se pudo generar deuda mensual de prueba")
		outstanding = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"))
		return socio_name, invoice_name, outstanding

	def _factura_arancel(
		self,
		socio_name: str,
		*,
		periodo: str,
		posting_date: str,
		rate: float = 21000.0,
		item_code: str = "ICDPE-BASQUET-ESCUELITA",
		description: str = "Arancel escuelita",
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

	def _run(self, path: str, **kwargs: Any) -> dict[str, Any]:
		frappe.set_user(self._secretaria)
		try:
			return run_importer(csv_path=path, **kwargs)
		finally:
			frappe.set_user("Administrator")

	# ------------------------------------------------------------------
	# Invariante de no-pérdida
	# ------------------------------------------------------------------

	def test_invariante_no_perdida_toda_fila_en_log(self) -> None:
		"""Filas inválidas (socio inexistente, sin mapeo) también quedan en el log."""
		socio_name, _inv, monto = self._socio_con_cuota(
			"88905001", "imp.invariante@example.com", reference_date="2026-08-01"
		)
		path = self._csv(
			f"{socio_name},{monto},2026-08-05,Efectivo,08/2026,Cuota Social Activo,",
			"99999999,5000,2026-08-05,Efectivo,08/2026,Cuota Social Activo,",
			f"{socio_name},7777,2026-08-05,Efectivo,08/2026,CONCEPTO INVENTADO XYZ,",
		)
		result = self._run(path, dry_run=True)

		self.assertEqual(result["filas"], 3)
		self.assertEqual(flt(result["total_csv"], 2), flt(monto + 5000 + 7777, 2))

		registros = _leer_auditoria(result["auditoria_path"])
		self.assertEqual(len(registros), 3)
		suma_log = sum(flt(r["monto_csv"]) for r in registros)
		self.assertAlmostEqual(suma_log, flt(monto + 5000 + 7777, 2), places=2)
		estados = [r["estado"] for r in registros]
		self.assertIn("error_socio_no_encontrado", estados)
		self.assertIn("error_concepto_sin_mapeo", estados)
		for registro in registros:
			self.assertTrue(registro["estado"], "toda fila debe tener estado terminal")

	# ------------------------------------------------------------------
	# Mora por tramos según fecha de pago vs mes del período
	# ------------------------------------------------------------------

	def test_periodo_anterior_pagado_con_mora_15(self) -> None:
		"""Arancel de julio pagado en agosto: tramo post_segundo, mora 15 % sobre facturado."""
		socio_name = self._socio_activo("88905002", "imp.mora15@example.com")
		self._factura_arancel(socio_name, periodo="07/2026", posting_date="2026-07-01", rate=21000.0)
		monto_con_mora = flt(21000.0 * 1.15, 2)  # 24150
		path = self._csv(
			f"{socio_name},{monto_con_mora},2026-08-10,Transferencia,07/2026,Adicional Basquet Escuelita,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")

		registros = _leer_auditoria(result["auditoria_path"])
		self.assertEqual(len(registros), 1)
		registro = registros[0]
		self.assertIn(registro["estado"], ("imputado", "imputado_con_saldo_favor"))
		self.assertEqual(flt(registro["mora_pct_esperado"]), 15.0)
		self.assertAlmostEqual(
			flt(registro["monto_imputado"]) + flt(registro["saldo_favor"]),
			monto_con_mora,
			places=2,
		)
		self.assertTrue(registro["payment_entry"])

	def test_periodo_adelantado_excluido_revision_manual(self) -> None:
		"""Arancel de septiembre pagado en agosto: no se imputa; va a revisión."""
		socio_name = self._socio_activo("88905003", "imp.adelantado@example.com")
		self._factura_arancel(
			socio_name, periodo="09/2026", posting_date="2026-08-01", rate=21000.0
		)
		path = self._csv(
			f"{socio_name},21000,2026-08-05,Efectivo,09/2026,Adicional Basquet Escuelita,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")

		registros = _leer_auditoria(result["auditoria_path"])
		registro = registros[0]
		self.assertEqual(registro["estado"], "excluido_adelantado")
		self.assertEqual(result["estados"].get("excluido_adelantado"), 1)
		motivos = {r["motivo"] for r in result["revision_manual"]}
		self.assertIn("excluido_adelantado", motivos)

	# ------------------------------------------------------------------
	# Auto-facturación inline
	# ------------------------------------------------------------------

	def test_auto_facturacion_concepto_sin_factura(self) -> None:
		"""Cuota de un período sin SI: se factura inline y se cobra en la misma corrida."""
		socio_name = self._socio_activo("88905004", "imp.autofact@example.com")
		path = self._csv(
			f"{socio_name},31000,2026-08-05,Efectivo,08/2026,Cuota Social Activo,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")

		registros = _leer_auditoria(result["auditoria_path"])
		registro = registros[0]
		self.assertEqual(registro["estado"], "imputado_con_facturacion")
		self.assertTrue(registro["sales_invoice_emitida"])
		self.assertTrue(registro["payment_entry"])
		self.assertAlmostEqual(flt(registro["monto_imputado"]), 31000.0, places=2)
		outstanding = flt(
			frappe.db.get_value(
				SALES_INVOICE_DOCTYPE, registro["sales_invoice_emitida"], "outstanding_amount"
			)
		)
		self.assertEqual(outstanding, 0.0)

	def test_auto_facturacion_rate_sin_mora_embebida(self) -> None:
		"""CSV con mora 10%: SI se emite a la base; la mora nace al cobro."""
		socio_name = self._socio_activo("88905011", "imp.autofact.mora@example.com")
		monto_con_mora = flt(28500.0 * 1.10, 2)  # 31350, día 12 → post_primer
		path = self._csv(
			f"{socio_name},{monto_con_mora},2026-08-12,Efectivo,08/2026,Adicional Basquet Escuelita,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev", reconcile=False)

		registros = _leer_auditoria(result["auditoria_path"])
		registro = registros[0]
		self.assertEqual(registro["estado"], "imputado_con_facturacion")
		self.assertEqual(flt(registro["mora_pct_esperado"]), 10.0)
		inv = registro["sales_invoice_emitida"]
		self.assertTrue(inv)
		rate = flt(
			frappe.db.get_value("Sales Invoice Item", {"parent": inv}, "rate"),
			2,
		)
		self.assertAlmostEqual(rate, 28500.0, places=2)
		self.assertNotIn("incluye mora", frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv, "remarks") or "")
		self.assertTrue(registro["payment_entry"])
		self.assertAlmostEqual(
			flt(registro["monto_imputado"]) + flt(registro["saldo_favor"]),
			monto_con_mora,
			places=2,
		)

	def test_monto_base_sin_mora_detecta_csv_ya_en_base(self) -> None:
		from club_management.scripts.cobranzas_bulk_importer import _monto_base_sin_mora

		# CSV con mora 10 % incluida
		self.assertEqual(_monto_base_sin_mora(31350.0, 10.0), 28500.0)
		# CSV ya en base (día con tramo mora pero cobraron tarifa pura)
		self.assertEqual(_monto_base_sin_mora(28500.0, 10.0), 28500.0)
		self.assertEqual(_monto_base_sin_mora(21000.0, 0.0), 21000.0)

	def test_rate_patin_agosto_congelado(self) -> None:
		from club_management.scripts.cobranzas_bulk_importer import _rate_factura_concepto

		self.assertEqual(
			_rate_factura_concepto(
				"ICDPE-PATIN-MINI", "08/2026", monto_csv=26000.0, mora_pct=0
			),
			20500.0,
		)
		self.assertEqual(
			_rate_factura_concepto(
				"ICDPE-PATIN-MINI", "09/2026", monto_csv=26000.0, mora_pct=0
			),
			26000.0,
		)

	def test_resolve_cost_center_item_nunca_grupo(self) -> None:
		from club_management.members.services.cobranza_manual import (
			_default_company,
			resolve_cost_center_item,
		)

		company = _default_company()
		if not company:
			self.skipTest("Sin Company")
		group = frappe.db.get_value("Cost Center", {"company": company, "is_group": 1}, "name")
		leaf = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
		if not group or not leaf:
			self.skipTest("Sin cost centers de prueba")
		item_code = "TEST-CC-GROUP-SKIP"
		if not frappe.db.exists("Item", item_code):
			ig = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": ig,
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		existing = frappe.db.exists("Item Default", {"parent": item_code, "company": company})
		if existing:
			frappe.db.set_value("Item Default", existing, "selling_cost_center", group)
		else:
			frappe.get_doc(
				{
					"doctype": "Item Default",
					"parent": item_code,
					"parenttype": "Item",
					"parentfield": "item_defaults",
					"company": company,
					"selling_cost_center": group,
				}
			).insert(ignore_permissions=True)
		resolved = resolve_cost_center_item(item_code, company)
		self.assertTrue(resolved)
		self.assertEqual(int(frappe.db.get_value("Cost Center", resolved, "is_group") or 0), 0)

	# ------------------------------------------------------------------
	# Saldo a favor: el CSV manda el monto
	# ------------------------------------------------------------------

	def test_excedente_queda_como_saldo_favor(self) -> None:
		socio_name = self._socio_activo("88905005", "imp.sf@example.com")
		self._factura_arancel(socio_name, periodo="08/2026", posting_date="2026-08-01", rate=21000.0)
		path = self._csv(
			f"{socio_name},25000,2026-08-05,Efectivo,08/2026,Adicional Basquet Escuelita,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")

		registros = _leer_auditoria(result["auditoria_path"])
		registro = registros[0]
		self.assertEqual(registro["estado"], "imputado_con_saldo_favor")
		self.assertAlmostEqual(flt(registro["monto_imputado"]), 21000.0, places=2)
		self.assertAlmostEqual(flt(registro["saldo_favor"]), 4000.0, places=2)
		self.assertAlmostEqual(
			flt(registro["monto_imputado"]) + flt(registro["saldo_favor"]), 25000.0, places=2
		)

	# ------------------------------------------------------------------
	# Idempotencia y reconciliación
	# ------------------------------------------------------------------

	def test_recorrida_idempotente(self) -> None:
		socio_name = self._socio_activo("88905006", "imp.idem@example.com")
		self._factura_arancel(socio_name, periodo="08/2026", posting_date="2026-08-01", rate=21000.0)
		path = self._csv(
			f"{socio_name},21000,2026-08-05,Efectivo,08/2026,Adicional Basquet Escuelita,",
		)
		primera = self._run(path, dry_run=False, confirm="local-dev")
		segunda = self._run(path, dry_run=False, confirm="local-dev")

		self.assertEqual(primera["estados"].get("imputado"), 1)
		self.assertEqual(segunda["estados"].get("ya_imputado"), 1)
		registros = _leer_auditoria(segunda["auditoria_path"])
		self.assertEqual(registros[0]["estado"], "ya_imputado")
		pes = frappe.get_all(
			"Payment Entry",
			filters={"party": ensure_customer_for_socio(socio_name), "docstatus": 1},
			pluck="name",
		)
		self.assertEqual(len(pes), 1)

	def test_reconcile_corrige_referencia_existente(self) -> None:
		"""PE existente con referencia INF equivocada: se corrige, no se duplica."""
		socio_name = self._socio_activo("88905007", "imp.reconcile@example.com")
		invoice = self._factura_arancel(
			socio_name, periodo="08/2026", posting_date="2026-08-01", rate=21000.0
		)
		from club_management.members.services.cobranza_manual import registrar_cobro_parcial_factura

		ref_mala = f"INF-999-{socio_name}-08/2026-21000.0-Cuota Social Menor"
		registrar_cobro_parcial_factura(
			socio_name,
			invoice,
			21000.0,
			mode_of_payment="Cash",
			posting_date="2026-08-05",
			reference_no=ref_mala,
			auto_submit=True,
		)

		path = self._csv(
			f"{socio_name},21000,2026-08-05,Efectivo,08/2026,Adicional Basquet Escuelita,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev", reconcile=True)

		registros = _leer_auditoria(result["auditoria_path"])
		registro = registros[0]
		self.assertEqual(registro["estado"], "ya_imputado")
		self.assertIn("referencia_corregida", registro["mensaje"])
		pes = frappe.get_all(
			"Payment Entry",
			filters={"party": ensure_customer_for_socio(socio_name), "docstatus": 1},
			fields=["name", "reference_no"],
		)
		self.assertEqual(len(pes), 1)
		self.assertIn("Adicional Basquet Escuel", pes[0].reference_no)

	# ------------------------------------------------------------------
	# CTO COMP (cuota complementaria)
	# ------------------------------------------------------------------

	def test_cto_comp_factura_via_cargo(self) -> None:
		socio_name = self._socio_activo("88905008", "imp.ctocomp@example.com")
		path = self._csv(
			f"{socio_name},6100,2026-08-05,Efectivo,08/2026,CTO COMP VOLEY,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")

		registros = _leer_auditoria(result["auditoria_path"])
		registro = registros[0]
		self.assertEqual(registro["estado"], "imputado_con_facturacion")
		self.assertTrue(registro["sales_invoice_emitida"])
		self.assertAlmostEqual(flt(registro["monto_imputado"]), 6100.0, places=2)

	# ------------------------------------------------------------------
	# Resumen / cuadratura interna
	# ------------------------------------------------------------------

	def test_resumen_cuadra_totales(self) -> None:
		socio_name = self._socio_activo("88905009", "imp.resumen@example.com")
		self._factura_arancel(socio_name, periodo="08/2026", posting_date="2026-08-01", rate=21000.0)
		path = self._csv(
			f"{socio_name},21000,2026-08-05,Efectivo,08/2026,Adicional Basquet Escuelita,",
			"99999999,5000,2026-08-05,Efectivo,08/2026,Cuota Social Activo,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")

		self.assertAlmostEqual(
			flt(result["total_imputado"])
			+ flt(result["total_saldo_favor"])
			+ flt(result["total_error"])
			+ flt(result.get("total_excluido") or 0),
			flt(result["total_csv"]),
			places=2,
		)
		self.assertEqual(result["filas"], 2)
		self.assertTrue(Path(result["resumen_path"]).is_file())

	def test_carnet_excluido_no_crea_pe(self) -> None:
		socio_name = self._socio_activo("88905010", "imp.carnet@example.com")
		path = self._csv(
			f"{socio_name},3000,2026-08-12,Efectivo,08/2026,CARNET,",
		)
		result = self._run(path, dry_run=False, confirm="local-dev")
		self.assertEqual(result["estados"].get("excluido_carnet"), 1)
		self.assertEqual(result["carnet"]["filas"], 1)
		self.assertEqual(result["carnet"]["detalle"][0]["socio"], socio_name)
		pes = frappe.get_all(
			"Payment Entry",
			filters={"party": ensure_customer_for_socio(socio_name), "docstatus": 1},
			pluck="name",
		)
		self.assertEqual(pes, [])

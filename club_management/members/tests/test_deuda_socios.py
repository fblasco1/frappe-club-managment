"""Tests informe Deuda de socios (spec deuda_socios.md)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.utils import flt, today

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.deuda_socios import get_deuda_socios
from club_management.members.test_helpers import MembersTestCase, insert_socio

ARANCEL = "DSOC-TEST-ARANCEL"
ARANCEL_PATIN = "DSOC-TEST-ARANCEL-PATIN"
FEDERATIVA = "DSOC-TEST-FEDERATIVA"
IMPUTACION = "club_management.members.services.deuda_socios._cobros_imputados_por_linea"
PKG = Path(__file__).resolve().parents[2]


def _ensure_item(code: str, rate: float) -> None:
	if frappe.db.exists("Item", code):
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": rate,
		}
	).insert(ignore_permissions=True)


class TestDeudaSocios(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
		for code, rate in ((CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000), (ARANCEL_PATIN, 3_000), (FEDERATIVA, 7_000)):
			_ensure_item(code, rate)
		self.actividad = frappe.get_doc(
			{"doctype": "Actividad", "titulo": "DSoc Basket", "habilitada": 1, "usa_grupos": 1}
		).insert(ignore_permissions=True).name
		self.grupo = frappe.get_doc(
			{"doctype": "Grupo Actividad", "actividad": self.actividad, "titulo": "DSoc Tira", "habilitada": 1}
		).insert(ignore_permissions=True).name
		self.equipo = frappe.get_doc(
			{
				"doctype": "Equipo Actividad",
				"grupo_actividad": self.grupo,
				"titulo": "DSoc U15",
				"habilitada": 1,
				"item": ARANCEL,
			}
		).insert(ignore_permissions=True).name
		self.equipo_b = frappe.get_doc(
			{
				"doctype": "Equipo Actividad",
				"grupo_actividad": self.grupo,
				"titulo": "DSoc U17",
				"habilitada": 1,
				"item": ARANCEL,
			}
		).insert(ignore_permissions=True).name
		self.patin = frappe.get_doc(
			{"doctype": "Actividad", "titulo": "DSoc Patin", "habilitada": 1, "usa_grupos": 0, "item": ARANCEL_PATIN}
		).insert(ignore_permissions=True).name

	# --- helpers ---------------------------------------------------------

	def _socio(self, dni: str, **kwargs):
		return insert_socio(dni=dni, email=f"dsoc.{dni}@example.com", **kwargs)

	def _inscribir(self, socio: str, *, actividad: str | None = None, equipo: str | None = None, estado: str = "Activa") -> None:
		actividad = actividad or self.actividad
		payload = {"doctype": "Inscripcion Actividad", "socio": socio, "actividad": actividad, "estado": estado}
		if actividad == self.actividad:
			payload["grupo_actividad"] = self.grupo
			payload["equipo_actividad"] = equipo or self.equipo
		frappe.get_doc(payload).insert(ignore_permissions=True)

	def _factura(self, socio: str, periodo: str, items: list[tuple[str, float]]) -> str:
		customer = ensure_customer_for_socio(socio, skip_permission_check=True)
		inv = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": today(),
				"due_date": today(),
				_campo_socio_en(SALES_INVOICE_DOCTYPE): socio,
				_campo_periodo_cobro(): periodo,
				"items": [{"item_code": code, "qty": 1, "rate": rate} for code, rate in items],
			}
		)
		inv.insert(ignore_permissions=True)
		inv.submit()
		return inv.name

	def _run(self, **filters):
		return get_deuda_socios(filters)

	def _lista(self, **filters) -> tuple[list[dict], list[dict], list[dict]]:
		columns, data, _msg, _chart, summary = self._run(vista="Lista de socios", **filters)
		return columns, data, summary

	def _arbol(self, **filters) -> list[dict]:
		_columns, data, *_rest = self._run(vista="Por actividad", **filters)
		return data

	@staticmethod
	def _fila(data: list[dict], socio: str) -> dict | None:
		return next((row for row in data if row.get("socio") == socio), None)

	# --- lista -----------------------------------------------------------

	def test_lista_una_fila_por_socio_con_cuota_y_arancel(self) -> None:
		socio = self._socio("76001001")
		self._inscribir(socio.name)
		self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])
		self._factura(socio.name, "09/2026", [(CUOTA_SOCIAL_ITEM_CODE, 9_000)])

		columns, data, summary = self._lista()
		fila = self._fila(data, socio.name)
		self.assertIsNotNone(fila)
		self.assertEqual(fila["periodos"], "09/2026, 10/2026")
		self.assertEqual(fila["cantidad_periodos"], 2)
		self.assertEqual(flt(fila["deuda_cuota_social"]), 19_000.0)
		self.assertEqual(flt(fila["deuda_arancel"]), 5_000.0)
		self.assertEqual(flt(fila["deuda_total"]), 24_000.0)
		self.assertIn("DSoc Basket", fila["actividades"])
		self.assertEqual(fila["telefono"], socio.telefono_movil)
		fieldnames = {c["fieldname"] for c in columns}
		self.assertTrue({"nombre", "categoria", "estado", "telefono", "periodos", "deuda_total"} <= fieldnames)
		labels = {row["label"] for row in summary}
		self.assertTrue({"Socios con deuda", "Períodos adeudados", "Total adeudado"} <= labels)

	def test_otros_cargos_no_suman(self) -> None:
		socio = self._socio("76001002")
		self._inscribir(socio.name)
		self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (FEDERATIVA, 7_000)])
		_columns, data, _summary = self._lista()
		self.assertEqual(flt(self._fila(data, socio.name)["deuda_total"]), 10_000.0)

	def test_cobro_parcial_imputado_por_linea(self) -> None:
		socio = self._socio("76001003")
		self._inscribir(socio.name)
		name = self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, name, "outstanding_amount", 10_000)
		imputado = [
			{"item_code": CUOTA_SOCIAL_ITEM_CODE, "restante": 10_000.0},
			{"item_code": ARANCEL, "restante": 0.0},
		]
		with patch(IMPUTACION, return_value=imputado) as mocked:
			_columns, data, _summary = self._lista()
		mocked.assert_any_call(name)
		fila = self._fila(data, socio.name)
		self.assertEqual(flt(fila["deuda_cuota_social"]), 10_000.0)
		self.assertEqual(flt(fila["deuda_arancel"]), 0.0)

	# --- concepto --------------------------------------------------------

	def test_concepto_solo_cuota_social(self) -> None:
		ambos = self._socio("76001004")
		solo_arancel = self._socio("76001005")
		for s in (ambos, solo_arancel):
			self._inscribir(s.name)
		self._factura(ambos.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])
		self._factura(solo_arancel.name, "10/2026", [(ARANCEL, 5_000)])

		columns, data, _summary = self._lista(concepto="Solo cuota social")
		fieldnames = {c["fieldname"] for c in columns}
		self.assertIn("deuda_cuota_social", fieldnames)
		self.assertNotIn("deuda_arancel", fieldnames)
		self.assertNotIn("deuda_total", fieldnames)
		self.assertEqual(flt(self._fila(data, ambos.name)["deuda_cuota_social"]), 10_000.0)
		self.assertIsNone(self._fila(data, solo_arancel.name))

	def test_concepto_solo_arancel(self) -> None:
		ambos = self._socio("76001006")
		solo_cuota = self._socio("76001007")
		for s in (ambos, solo_cuota):
			self._inscribir(s.name)
		self._factura(ambos.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])
		self._factura(solo_cuota.name, "09/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000)])

		columns, data, _summary = self._lista(concepto="Solo arancel")
		fieldnames = {c["fieldname"] for c in columns}
		self.assertIn("deuda_arancel", fieldnames)
		self.assertNotIn("deuda_cuota_social", fieldnames)
		self.assertEqual(flt(self._fila(data, ambos.name)["deuda_arancel"]), 5_000.0)
		self.assertIsNone(self._fila(data, solo_cuota.name))

	# --- filtros ---------------------------------------------------------

	def test_filtro_periodo(self) -> None:
		socio = self._socio("76001008")
		self._factura(socio.name, "08/2026", [(CUOTA_SOCIAL_ITEM_CODE, 8_000)])
		self._factura(socio.name, "09/2026", [(CUOTA_SOCIAL_ITEM_CODE, 9_000)])
		self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000)])
		_columns, data, _summary = self._lista(periodo_desde="09/2026", periodo_hasta="09/2026")
		fila = self._fila(data, socio.name)
		self.assertEqual(fila["periodos"], "09/2026")
		self.assertEqual(flt(fila["deuda_total"]), 9_000.0)

	def test_periodo_invalido_lanza_error(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			self._lista(periodo_desde="septiembre")

	def test_filtros_categoria_estado_socio(self) -> None:
		activo = self._socio("76001009", categoria="Activo")
		menor = self._socio("76001010", categoria="Menor")
		for s in (activo, menor):
			self._factura(s.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000)])

		_c, data, _s = self._lista(categoria="Menor")
		self.assertIsNone(self._fila(data, activo.name))
		self.assertIsNotNone(self._fila(data, menor.name))

		_c, data, _s = self._lista(socio=activo.name)
		self.assertEqual([r["socio"] for r in data], [activo.name])

		estado = frappe.db.get_value("Socio", activo.name, "estado")
		_c, data, _s = self._lista(estado=estado, socio=activo.name)
		self.assertIsNotNone(self._fila(data, activo.name))

	def test_baja_solo_con_filtro_estado_y_en_su_actividad(self) -> None:
		socio = self._socio("76001011")
		self._inscribir(socio.name, estado="Baja")
		frappe.db.set_value("Socio", socio.name, "estado", "Baja")
		self._factura(socio.name, "09/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])

		_c, data, _s = self._lista()
		self.assertIsNone(self._fila(data, socio.name))

		_c, data, _s = self._lista(estado="Baja", socio=socio.name)
		self.assertEqual(flt(self._fila(data, socio.name)["deuda_arancel"]), 5_000.0)

		rows = self._arbol(estado="Baja", socio=socio.name)
		socio_row = self._fila(rows, socio.name)
		self.assertEqual(socio_row["actividad"], self.actividad)

	def test_filtro_equipo(self) -> None:
		u15 = self._socio("76001012")
		u17 = self._socio("76001013")
		self._inscribir(u15.name, equipo=self.equipo)
		self._inscribir(u17.name, equipo=self.equipo_b)
		for s in (u15, u17):
			self._factura(s.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])

		_c, data, _s = self._lista(actividad=self.actividad, grupo_actividad=self.grupo, equipo_actividad=self.equipo)
		self.assertIsNotNone(self._fila(data, u15.name))
		self.assertIsNone(self._fila(data, u17.name))

		rows = self._arbol(actividad=self.actividad, equipo_actividad=self.equipo_b)
		self.assertIsNotNone(self._fila(rows, u17.name))
		self.assertIsNone(self._fila(rows, u15.name))

	# --- árbol -----------------------------------------------------------

	def test_arbol_total_actividad_grupo_equipo_socio(self) -> None:
		deudor = self._socio("76001014")
		al_dia = self._socio("76001015")
		for s in (deudor, al_dia):
			self._inscribir(s.name)
		self._factura(deudor.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])

		rows = self._arbol(actividad=self.actividad)
		self.assertEqual(rows[0]["nivel"], "Total")
		self.assertEqual(int(rows[0]["indent"]), 0)
		self.assertEqual(flt(rows[0]["deuda_total"]), 15_000.0)
		self.assertEqual(rows[0]["socios_deudores"], "1 (50%)")
		indents = [int(r["indent"]) for r in rows]
		self.assertEqual(indents, [0, 1, 2, 3, 4])
		socio_row = rows[-1]
		self.assertEqual(socio_row["socio"], deudor.name)
		self.assertEqual(socio_row["periodos"], "10/2026")
		self.assertEqual(socio_row["telefono"], deudor.telefono_movil)
		self.assertEqual(flt(socio_row["deuda_cuota_social"]), 10_000.0)
		self.assertEqual(flt(socio_row["deuda_arancel"]), 5_000.0)

	def test_arbol_multiactividad(self) -> None:
		socio = self._socio("76001016")
		self._inscribir(socio.name)
		self._inscribir(socio.name, actividad=self.patin)
		self._factura(
			socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000), (ARANCEL_PATIN, 3_000)]
		)
		rows = self._arbol(socio=socio.name)
		multi = next(r for r in rows if r["nivel"] == "Multiactividad")
		self.assertEqual(int(multi["indent"]), 1)
		self.assertEqual(flt(multi["deuda_arancel"]), 8_000.0)
		socio_row = self._fila(rows, socio.name)
		self.assertEqual(int(socio_row["indent"]), 2)
		self.assertIn("DSoc Basket", socio_row["actividades"])
		self.assertIn("DSoc Patin", socio_row["actividades"])
		self.assertFalse([r for r in rows if r["nivel"].startswith("Subtotal")])

	def test_arbol_dos_inscripciones_misma_actividad_cuota_una_vez(self) -> None:
		socio = self._socio("76001017")
		self._inscribir(socio.name, equipo=self.equipo)
		self._inscribir(socio.name, equipo=self.equipo_b)
		self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 10_000), (ARANCEL, 5_000)])
		rows = self._arbol(socio=socio.name)
		self.assertNotIn("Multiactividad", [r["nivel"] for r in rows])
		self.assertEqual(flt(rows[0]["deuda_cuota_social"]), 10_000.0)
		self.assertEqual(flt(rows[0]["deuda_arancel"]), 5_000.0)

	def test_arbol_sin_actividad_solo_sin_filtro_de_actividad(self) -> None:
		socio = self._socio("76001018")
		self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 9_000)])
		rows = self._arbol(socio=socio.name)
		sin_act = next(r for r in rows if r["nivel"] == "Sin actividad")
		self.assertEqual(int(sin_act["indent"]), 1)
		self.assertEqual(int(self._fila(rows, socio.name)["indent"]), 2)

		rows = self._arbol(socio=socio.name, actividad=self.actividad)
		self.assertNotIn("Sin actividad", [r["nivel"] for r in rows])

	def test_vista_por_defecto_es_arbol(self) -> None:
		socio = self._socio("76001019")
		self._factura(socio.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 9_000)])
		_columns, data, *_rest = get_deuda_socios({"socio": socio.name})
		self.assertEqual(data[0]["nivel"], "Total")

	def test_no_consulta_facturas_socio_por_socio(self) -> None:
		for dni in ("76001020", "76001021"):
			s = self._socio(dni)
			self._factura(s.name, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 9_000)])
		target = "club_management.members.services.liquidacion_equipo.get_facturas_pendientes_socio_en_rango"
		with patch(target) as mocked:
			self._arbol()
			self._lista()
		mocked.assert_not_called()

	# --- artefactos / menú -----------------------------------------------

	def test_report_y_filtros_desk(self) -> None:
		folder = PKG / "members" / "report" / "deuda_de_socios"
		meta = json.loads((folder / "deuda_de_socios.json").read_text(encoding="utf-8"))
		self.assertEqual(meta["name"], "Deuda de socios")
		self.assertEqual(meta["ref_doctype"], "Socio")
		self.assertEqual({r["role"] for r in meta["roles"]}, {"Secretaria", "System Manager"})
		self.assertEqual(meta["prepared_report"], 0)
		js = (folder / "deuda_de_socios.js").read_text(encoding="utf-8")
		for fieldname in (
			"vista",
			"concepto",
			"periodo_desde",
			"periodo_hasta",
			"categoria",
			"estado",
			"socio",
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
		):
			self.assertIn(f'fieldname: "{fieldname}"', js)
		self.assertIn("get_query", js)
		self.assertIn("bind_tree_row_toggle", js)
		self.assertTrue((folder / "deuda_de_socios.html").is_file())

	def test_menu_reemplaza_informes_anteriores(self) -> None:
		from club_management.activities.setup.actividades_workspace_sidebar import (
			SIDEBAR_ITEMS as ACTIVIDADES_ITEMS,
		)
		from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS, CLUB_DESK_REPORTS_LEGACY
		from club_management.members.setup.secretaria_workspace_sidebar import SIDEBAR_ITEMS

		for items in (SIDEBAR_ITEMS, ACTIVIDADES_ITEMS):
			links = {row.get("link_to") for row in items}
			self.assertIn("Deuda de socios", links)
			self.assertNotIn("Deuda cuotas sociales", links)
			self.assertNotIn("Deuda por actividad", links)
		self.assertIn("Deuda de socios", CLUB_DESK_REPORTS)
		self.assertIn("Deuda por actividad", CLUB_DESK_REPORTS_LEGACY)
		self.assertIn("Deuda cuotas sociales", CLUB_DESK_REPORTS_LEGACY)
		for js_name in ("secretaria_sidebar_boot.js", "actividades_sidebar_boot.js"):
			js = (PKG / "public" / "js" / js_name).read_text(encoding="utf-8")
			self.assertIn('link_to: "Deuda de socios"', js)
			self.assertNotIn('link_to: "Deuda por actividad"', js)
			self.assertNotIn('link_to: "Deuda cuotas sociales"', js)

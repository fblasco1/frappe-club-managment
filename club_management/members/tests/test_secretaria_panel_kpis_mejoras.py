"""Mejoras KPIs y tendencia del panel Secretaría.

Spec: `club_management/specs/secretaria_workspace_panel_kpis.md`
"""

from __future__ import annotations

from pathlib import Path

import frappe
from frappe.utils import getdate, today

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.secretaria_panel_kpis import (
	contar_meses_vencidos,
	get_actividades_movimientos,
	get_mora_clasificacion_payload,
	get_recaudacion_tendencia_payload,
	get_socio_metricas_payload,
	tramo_mora_por_meses,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio

_HOY = "2026-10-06"


def _setup_cobranza() -> None:
	sync_cuotas_sociales_club()
	settings = frappe.get_single("Club Settings")
	settings.dia_generacion_deuda = 1
	settings.dia_primer_vencimiento = 10
	settings.dia_segundo_vencimiento = "20"
	if not settings.company:
		company = frappe.db.get_value("Company", {}, "name")
		if company:
			settings.company = company
	settings.save(ignore_permissions=True)
	if not frappe.db.exists("Item", CUOTA_SOCIAL_ITEM_CODE):
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": CUOTA_SOCIAL_ITEM_CODE,
				"item_name": "Cuota Social Base",
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 10_000,
			}
		).insert(ignore_permissions=True)


class TestMoraMesesVencidos(MembersTestCase):
	def _contar(self, periodos: list[str], as_of: str = _HOY) -> int:
		return contar_meses_vencidos(
			periodos,
			as_of=getdate(as_of),
			dia_primer_vencimiento=10,
			dia_segundo_vencimiento="20",
		)

	def test_mes_en_curso_antes_del_segundo_vencimiento_no_cuenta(self) -> None:
		self.assertEqual(self._contar(["10/2026"]), 0)

	def test_mes_en_curso_despues_del_segundo_vencimiento_cuenta(self) -> None:
		self.assertEqual(self._contar(["10/2026"], as_of="2026-10-21"), 1)

	def test_el_dia_del_segundo_vencimiento_todavia_no_cuenta(self) -> None:
		self.assertEqual(self._contar(["10/2026"], as_of="2026-10-20"), 0)

	def test_sufijos_mora_y_rec_cuentan_como_su_mes_base(self) -> None:
		self.assertEqual(self._contar(["09/2026", "09/2026-MORA", "07/2026-REC"]), 2)

	def test_ignora_periodos_invalidos(self) -> None:
		self.assertEqual(self._contar(["", "sin-periodo", "09/2026"]), 1)

	def test_cuenta_meses_distintos(self) -> None:
		periodos = ["10/2026", "09/2026", "08/2026", "07/2026", "06/2026"]
		self.assertEqual(self._contar(periodos), 4)

	def test_tramo_por_cantidad_de_meses(self) -> None:
		self.assertIsNone(tramo_mora_por_meses(0))
		self.assertEqual(tramo_mora_por_meses(1), "1")
		self.assertEqual(tramo_mora_por_meses(2), "2")
		self.assertEqual(tramo_mora_por_meses(3), "3")
		self.assertEqual(tramo_mora_por_meses(4), "4_mas")
		self.assertEqual(tramo_mora_por_meses(9), "4_mas")

	def test_clasificacion_expone_cuatro_tramos(self) -> None:
		data = get_mora_clasificacion_payload(reference_date=_HOY)
		self.assertEqual([t["key"] for t in data["tramos"]], ["1", "2", "3", "4_mas"])
		self.assertEqual(
			[t["label"] for t in data["tramos"]],
			["1 mes", "2 meses", "3 meses", "+4 meses"],
		)
		for tramo in data["tramos"]:
			self.assertGreaterEqual(tramo["cantidad"], 0)
			self.assertIn("monto_label", tramo)


class TestMoraClasificacionIntegracion(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		_setup_cobranza()

	def test_socio_con_dos_meses_vencidos_cae_en_tramo_2(self) -> None:
		from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio

		antes = {
			t["key"]: t["cantidad"]
			for t in get_mora_clasificacion_payload(reference_date=_HOY)["tramos"]
		}
		socio = insert_socio(dni="73201001", email="mora.dos@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test mora meses")
		generar_deuda_mensual_socio(socio.name, reference_date="2026-07-01")
		generar_deuda_mensual_socio(socio.name, reference_date="2026-08-01")
		generar_deuda_mensual_socio(socio.name, reference_date="2026-10-01")

		despues = {
			t["key"]: t["cantidad"]
			for t in get_mora_clasificacion_payload(reference_date=_HOY)["tramos"]
		}
		self.assertEqual(despues["2"], antes["2"] + 1)
		self.assertEqual(despues["3"], antes["3"])


class TestActividadesMovimientos(MembersTestCase):
	def _actividad(self, titulo: str) -> str:
		if not frappe.db.exists("Actividad", titulo):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": titulo, "habilitada": 1, "usa_grupos": 0}
			).insert(ignore_permissions=True)
		return titulo

	def _inscripcion(self, socio: str, actividad: str, fecha: str) -> "frappe.model.document.Document":
		return frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio,
				"actividad": actividad,
				"estado": "Activa",
				"fecha_inscripcion": fecha,
			}
		).insert(ignore_permissions=True)

	def _baja(self, inscripcion: "frappe.model.document.Document", creation: str) -> None:
		inscripcion.estado = "Baja"
		inscripcion.save(ignore_permissions=True, ignore_version=False)
		version = frappe.get_all(
			"Version",
			filters={"ref_doctype": "Inscripcion Actividad", "docname": inscripcion.name},
			pluck="name",
			order_by="creation desc",
			limit=1,
		)
		self.assertTrue(version)
		frappe.db.set_value("Version", version[0], "creation", creation, update_modified=False)

	def test_top_3_actividades_por_altas_y_bajas(self) -> None:
		socios = [
			insert_socio(dni=f"7330100{i}", email=f"mov.act{i}@example.com").name for i in range(1, 6)
		]
		a = self._actividad("KPI Mov A")
		b = self._actividad("KPI Mov B")
		c = self._actividad("KPI Mov C")
		d = self._actividad("KPI Mov D")

		for socio in socios[:3]:
			self._inscripcion(socio, a, "2026-10-01")
		ins_b = self._inscripcion(socios[0], b, "2026-08-01")
		self._baja(ins_b, "2026-09-20 10:00:00")
		self._inscripcion(socios[1], b, "2026-09-15")
		self._inscripcion(socios[2], c, "2026-09-10")
		ins_d = self._inscripcion(socios[3], d, "2026-07-01")
		self._baja(ins_d, "2026-08-01 10:00:00")
		self._inscripcion(socios[4], d, "2026-08-15")

		data = get_actividades_movimientos(reference_date=_HOY, dias=30, limit=None)
		self.assertEqual(data["desde"], "2026-09-07")
		self.assertEqual(data["hasta"], _HOY)
		por_nombre = {row["actividad"]: row for row in data["actividades"]}
		self.assertEqual(por_nombre[a]["altas"], 3)
		self.assertEqual(por_nombre[a]["bajas"], 0)
		self.assertEqual(por_nombre[b]["altas"], 1)
		self.assertEqual(por_nombre[b]["bajas"], 1)
		self.assertEqual(por_nombre[b]["total"], 2)
		self.assertEqual(por_nombre[c]["total"], 1)
		self.assertNotIn(d, por_nombre)
		totales = [row["total"] for row in data["actividades"]]
		self.assertEqual(totales, sorted(totales, reverse=True))

		top = get_actividades_movimientos(reference_date=_HOY, dias=30, limit=3)
		self.assertLessEqual(len(top["actividades"]), 3)
		self.assertEqual(top["actividades"], data["actividades"][: len(top["actividades"])])

	def test_fecha_de_corte_por_actividad_ignora_carga_masiva(self) -> None:
		socios = [
			insert_socio(dni=f"7330200{i}", email=f"mov.corte{i}@example.com").name for i in range(1, 6)
		]
		gym = self._actividad("KPI Corte Gym")
		otra = self._actividad("KPI Corte Otra")
		frappe.db.set_value("Actividad", gym, "contar_movimientos_desde", "2026-10-02")

		for socio in socios[:3]:
			self._inscripcion(socio, gym, "2026-10-01")
		self._inscripcion(socios[3], gym, "2026-10-03")
		baja_previa = self._inscripcion(socios[0], otra, "2026-06-01")
		self._baja(baja_previa, "2026-09-20 10:00:00")
		self._inscripcion(socios[1], otra, "2026-09-25")

		ins_gym_baja = self._inscripcion(socios[4], gym, "2026-05-01")
		self._baja(ins_gym_baja, "2026-09-30 10:00:00")

		data = get_actividades_movimientos(reference_date=_HOY, dias=30, limit=None)
		por_nombre = {row["actividad"]: row for row in data["actividades"]}
		self.assertEqual(por_nombre[gym]["altas"], 1)
		self.assertEqual(por_nombre[gym]["bajas"], 0)
		self.assertEqual(por_nombre[otra]["altas"], 1)
		self.assertEqual(por_nombre[otra]["bajas"], 1)

	def test_metricas_socios_incluye_movimientos_actividades(self) -> None:
		data = get_socio_metricas_payload(reference_date=_HOY)
		self.assertIn("actividades_movimientos", data)
		self.assertIn("actividades", data["actividades_movimientos"])


class TestTendenciaResumen(MembersTestCase):
	def test_mes_pasado_se_dibuja_completo(self) -> None:
		data = get_recaudacion_tendencia_payload(reference_date="2099-06-01")
		self.assertEqual(data["hasta_dia"], 30)
		resumen = data["resumen"]
		for key in ("emitido", "recaudado", "porcentaje", "saldo"):
			self.assertIn(key, resumen)
		for key in ("emitido_label", "recaudado_label", "saldo_label"):
			self.assertIn(key, resumen)

	def test_mes_en_curso_corta_en_hoy(self) -> None:
		hoy = getdate(today())
		data = get_recaudacion_tendencia_payload(reference_date=str(hoy))
		self.assertEqual(data["hasta_dia"], hoy.day)

	def test_resumen_coincide_con_la_serie(self) -> None:
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		_setup_cobranza()
		from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio

		socio = insert_socio(dni="73401001", email="tend.res@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test resumen tendencia")
		generar_deuda_mensual_socio(socio.name, reference_date="2099-06-01")

		data = get_recaudacion_tendencia_payload(reference_date="2099-06-01")
		resumen = data["resumen"]
		self.assertGreater(resumen["emitido"], 0)
		self.assertEqual(resumen["recaudado"], data["dias"][-1]["recaudado"])
		self.assertEqual(resumen["saldo"], data["dias"][-1]["deuda"])
		esperado = round(resumen["recaudado"] / resumen["emitido"] * 100, 1)
		self.assertEqual(resumen["porcentaje"], esperado)


class TestPanelJsMejoras(MembersTestCase):
	def test_panel_js_renderiza_mejoras(self) -> None:
		js = (
			Path(__file__).resolve().parents[2] / "public" / "js" / "secretaria_workspace_panel.js"
		).read_text(encoding="utf-8")
		self.assertIn("render_socios_categorias", js)
		self.assertIn("render_actividades_movimientos", js)
		self.assertIn("render_tendencia_resumen", js)
		self.assertIn("hasta_dia", js)
		self.assertIn("club-secretaria-segmented", js)
		self.assertIn("club-portal-field", js)

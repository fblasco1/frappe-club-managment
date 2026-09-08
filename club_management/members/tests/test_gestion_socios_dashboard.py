"""Tests dashboard Gestión de Socios (spec gestion_socios_dashboard.md)."""

from __future__ import annotations

import frappe

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
)
from club_management.members.services.cobranza_periodica import (
	format_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.recibo_pago import format_monto_ar
from club_management.members.services.secretaria_panel_kpis import (
	count_altas_bajas_mes,
	get_medios_pago_payload,
	get_mora_1_3_meses_payload,
	get_panel_metricas_payload,
	get_recaudacion_tendencia_payload,
	get_socios_por_categoria,
)
from club_management.members.services.secretaria_workspace_panel import (
	get_panel_lists_payload,
	get_solicitudes_pendientes_preview,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import (
	MembersTestCase,
	adult_birthdate,
	insert_socio,
	insert_solicitud_asociacion,
	minor_birthdate,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_SOLICITAR_CORRECCION,
	STATE_PENDIENTE,
	STATE_REQUIERE_CORRECCION,
)


class TestGestionSociosDashboardCategorias(MembersTestCase):
	_REFERENCE = "2026-06-15"

	def test_socios_por_categoria(self) -> None:
		insert_socio(dni="74001001", email="seg.act@example.com", categoria="Activo", estado="Activo")
		insert_socio(
			dni="74001002",
			email="seg.men@example.com",
			categoria="Menor",
			estado="Activo",
			fecha_nacimiento=minor_birthdate(12),
			tipo_tutor="Socio",
			tutor=insert_socio(
				dni="74001009",
				email="seg.tutor.men@example.com",
				categoria="Activo",
				estado="Activo",
			).name,
		)
		insert_socio(dni="74001003", email="seg.adh@example.com", categoria="Adherente", estado="Activo")
		insert_socio(dni="74001004", email="seg.jub@example.com", categoria="Jubilado", estado="Activo")
		insert_socio(dni="74001005", email="seg.vit@example.com", categoria="Vitalicio", estado="Activo")
		insert_socio(
			dni="74001006",
			email="seg.her.ad@example.com",
			categoria="2° Hermano",
			estado="Activo",
			fecha_nacimiento=adult_birthdate(25),
		)
		insert_socio(
			dni="74001008",
			email="seg.her.men@example.com",
			categoria="3° Hermano",
			estado="Activo",
			fecha_nacimiento=minor_birthdate(12),
		)
		insert_socio(dni="74001007", email="seg.baja@example.com", categoria="Activo", estado="Baja")

		data = get_socios_por_categoria(reference_date=self._REFERENCE)
		self.assertGreaterEqual(data["total"], 7)
		self.assertGreaterEqual(data["Activo"], 2)
		self.assertGreaterEqual(data["Menor"], 2)
		self.assertGreaterEqual(data["Adherente"], 1)
		self.assertGreaterEqual(data["Jubilado"], 1)
		self.assertGreaterEqual(data["Vitalicio"], 1)
		self.assertEqual(
			data["Activo"]
			+ data["Menor"]
			+ data["Adherente"]
			+ data["Jubilado"]
			+ data["Vitalicio"],
			data["total"],
		)

	def test_altas_bajas_mes(self) -> None:
		socio = insert_socio(dni="74002001", email="alt.baj@example.com", estado="Activo")
		frappe.db.set_value("Socio", socio.name, "fecha_alta", "2026-06-10")
		baja = insert_socio(dni="74002002", email="baja.mes@example.com", estado="Activo")
		cambiar_estado(baja.name, "Baja", motivo="Test dashboard")
		frappe.db.set_value("Socio", baja.name, "ultimo_cambio_estado_en", "2026-06-12 10:00:00")

		data = count_altas_bajas_mes(reference_date=self._REFERENCE)
		self.assertGreaterEqual(data["altas"], 1)
		self.assertGreaterEqual(data["bajas"], 1)

	def test_panel_metricas_incluye_dashboard(self) -> None:
		data = get_panel_metricas_payload(reference_date=self._REFERENCE)
		socios = data["socios"]
		self.assertIn("segmentos", socios)
		self.assertIn("altas_bajas", socios)
		self.assertIn("mora_1_3", socios)
		self.assertIn("tendencia_recaudacion", data)
		self.assertIn("medios_pago", data)


class TestGestionSociosDashboardSolicitudes(MembersTestCase):
	def test_solicitudes_incluye_pendiente_y_correccion(self) -> None:
		insert_solicitud_asociacion(
			dni="74003001",
			email="sol.pend@example.com",
			nombre="Ana",
			workflow_state=STATE_PENDIENTE,
		)
		correccion = insert_solicitud_asociacion(
			dni="74003002",
			email="sol.corr@example.com",
			nombre="Luis",
			workflow_state=STATE_PENDIENTE,
		)
		frappe.model.workflow.apply_workflow(
			frappe.get_doc(correccion.doctype, correccion.name),
			ACTION_SOLICITAR_CORRECCION,
		)
		validada = insert_solicitud_asociacion(
			dni="74003003",
			email="sol.val@example.com",
			nombre="María",
			workflow_state=STATE_PENDIENTE,
		)
		frappe.model.workflow.apply_workflow(
			frappe.get_doc(validada.doctype, validada.name),
			"Validar",
		)

		rows = get_solicitudes_pendientes_preview(limit=10)
		dnis = {row["dni"] for row in rows}
		self.assertIn("74003001", dnis)
		self.assertIn("74003002", dnis)
		self.assertNotIn("74003003", dnis)

	def test_panel_lists_incluye_solicitudes(self) -> None:
		data = get_panel_lists_payload()
		self.assertIn("solicitudes_pendientes", data)
		self.assertIn("solicitudes_doctype", data["metricas"]["ver_mas"])


class TestGestionSociosDashboardRecaudacion(MembersTestCase):
	_REFERENCE = "2026-06-01"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()

	def test_tendencia_recaudacion_deuda_y_recaudado_acumulados(self) -> None:
		socio = insert_socio(dni="74003001", email="tend.rec@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test tendencia")
		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		campo_socio = "socio" if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field("socio") else "custom_socio"
		invoice_name = frappe.db.get_value(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
			"name",
		)
		self.assertTrue(invoice_name)
		registrar_cobro_manual(socio.name, invoice_name, mode_of_payment="Cash")

		data = get_recaudacion_tendencia_payload(reference_date=self._REFERENCE)
		self.assertEqual(data["periodo"], format_periodo_cobro(self._REFERENCE))
		self.assertEqual(len(data["dias"]), 30)
		for row in data["dias"]:
			self.assertIn("dia", row)
			self.assertIn("label", row)
			self.assertIn("deuda", row)
			self.assertIn("recaudado", row)

		last = data["dias"][-1]
		self.assertGreater(last["recaudado"], 0)
		self.assertEqual(last["deuda"], 0)

	def test_tendencia_incluye_cuotas_y_aranceles(self) -> None:
		"""Spec: vista Total suma cuotas + aranceles; filtros por vista aíslan cada tipo."""
		from club_management.activities.services.inscripcion_socio import (
			inscribir_socio_selecciones,
		)
		from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
		from frappe.utils import flt

		settings = frappe.get_single("Club Settings")
		settings.incluir_aranceles_en_deuda_mensual = 1
		settings.save(ignore_permissions=True)

		actividad = "Tendencia Natación KPI"
		socio = insert_socio(dni="74003011", email="tend.ar@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test tendencia arancel")
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": actividad, "habilitada": 1, "usa_grupos": 0}
			).insert(ignore_permissions=True)
		item_code = f"AR-TEND-{frappe.generate_hash(length=6)}"
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": f"Arancel {actividad}",
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 5_000,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Actividad", actividad, "item", item_code)
		inscribir_socio_selecciones(socio.name, [{"actividad": actividad}])
		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)

		campo_socio = "socio" if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field("socio") else "custom_socio"
		invoice_name = frappe.db.get_value(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
			"name",
		)
		self.assertTrue(invoice_name)
		self.assertTrue(
			frappe.db.exists("Sales Invoice Item", {"parent": invoice_name, "item_code": item_code})
		)
		arancel_amt = flt(
			frappe.db.get_value(
				"Sales Invoice Item",
				{"parent": invoice_name, "item_code": item_code},
				"amount",
			)
		)
		cuota_amt = flt(
			frappe.db.get_value(
				"Sales Invoice Item",
				{"parent": invoice_name, "item_code": CUOTA_SOCIAL_ITEM_CODE},
				"amount",
			)
			or 0
		)
		# Si la cuota usa otro item de categoría, sumar todas las líneas no-arancel de cuota
		if cuota_amt <= 0:
			cuota_amt = sum(
				flt(r.amount)
				for r in frappe.get_all(
					"Sales Invoice Item",
					filters={"parent": invoice_name},
					fields=["item_code", "amount"],
				)
				if r.item_code != item_code
			)
		esperado_emitido = flt(cuota_amt + arancel_amt, 2)
		self.assertGreater(arancel_amt, 0)

		data = get_recaudacion_tendencia_payload(reference_date=self._REFERENCE)
		self.assertEqual(data["vista"], "total")
		self.assertTrue(any(v["value"] == "arancel" for v in data.get("vistas") or []))
		# Día 1 (emisión): emitido acumulado = deuda + recaudado (aún 0 de cobro nuestro)
		day1 = data["dias"][0]
		emitido_total = flt(day1["deuda"] + day1["recaudado"], 2)
		self.assertGreaterEqual(emitido_total, esperado_emitido)

		data_arancel = get_recaudacion_tendencia_payload(
			reference_date=self._REFERENCE, vista="arancel"
		)
		self.assertEqual(data_arancel["vista"], "arancel")
		day1_ar = data_arancel["dias"][0]
		emitido_arancel = flt(day1_ar["deuda"] + day1_ar["recaudado"], 2)
		self.assertGreaterEqual(emitido_arancel, arancel_amt)
		self.assertLess(emitido_arancel, emitido_total)

		data_cuota = get_recaudacion_tendencia_payload(
			reference_date=self._REFERENCE, vista="cuota"
		)
		self.assertEqual(data_cuota["vista"], "cuota")
		day1_cu = data_cuota["dias"][0]
		emitido_cuota = flt(day1_cu["deuda"] + day1_cu["recaudado"], 2)
		self.assertGreaterEqual(emitido_cuota, cuota_amt)
		self.assertLess(emitido_cuota, emitido_total)

		# La cuota de arancel de esta SI figura como deuda pendiente en la vista arancel
		last_ar_before = data_arancel["dias"][-1]
		self.assertGreaterEqual(flt(last_ar_before["deuda"], 2), arancel_amt)

		registrar_cobro_manual(socio.name, invoice_name, mode_of_payment="Cash")
		data_paid = get_recaudacion_tendencia_payload(reference_date=self._REFERENCE)
		last = data_paid["dias"][-1]
		self.assertGreaterEqual(flt(last["recaudado"], 2), esperado_emitido)

		data_ar_paid = get_recaudacion_tendencia_payload(
			reference_date=self._REFERENCE, vista="arancel"
		)
		last_ar_after = data_ar_paid["dias"][-1]
		self.assertLessEqual(
			flt(last_ar_after["deuda"], 2),
			flt(last_ar_before["deuda"] - arancel_amt, 2) + 0.01,
		)

	def test_mora_1_3_monto_label_pesos(self) -> None:
		data = get_mora_1_3_meses_payload()
		self.assertEqual(data["monto_label"], format_monto_ar(data["monto"]))
		if data["monto"] > 0:
			self.assertTrue(str(data["monto_label"]).startswith("$"))

	def test_medios_pago_agrupa_efectivo(self) -> None:
		from frappe.utils import today

		ref = today()
		socio = insert_socio(dni="74004001", email="med.pago@example.com", categoria="Activo")
		cambiar_estado(socio.name, "Activo", motivo="Test medios pago")
		generar_deuda_mensual_socio(socio.name, reference_date=ref)
		campo_socio = "socio" if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field("socio") else "custom_socio"
		invoice_name = frappe.db.get_value(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
			"name",
		)
		self.assertTrue(invoice_name)
		registrar_cobro_manual(socio.name, invoice_name, mode_of_payment="Cash")

		data = get_medios_pago_payload(reference_date=ref)
		self.assertTrue(data["disponible"])
		self.assertEqual(data["periodo"], format_periodo_cobro(ref))
		self.assertGreater(data["efectivo"], 0)

	def test_medios_pago_sin_cobros_payload_disponible_con_ceros(self) -> None:
		"""Spec: sin Payment Entry del mes → disponible True y montos en cero."""
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext cobranza no disponible")
		from frappe.utils import add_months, get_first_day, today

		# Mes sin cobros tipicamente: usar un mes futuro lejano
		ref = get_first_day(add_months(today(), 24))
		data = get_medios_pago_payload(reference_date=ref)
		self.assertTrue(data["disponible"])
		self.assertEqual(data["efectivo"], 0.0)
		self.assertEqual(data["tarjeta"], 0.0)
		self.assertEqual(data["transferencia"], 0.0)
		self.assertEqual(data["otro"], 0.0)

	def test_panel_js_medios_pago_estado_vacio_sin_desaparecer(self) -> None:
		"""Spec: tarjeta visible con mensaje 'Sin cobros del mes' si montos = 0."""
		from pathlib import Path

		js_path = (
			Path(__file__).resolve().parents[2]
			/ "public"
			/ "js"
			/ "secretaria_workspace_panel.js"
		)
		js = js_path.read_text(encoding="utf-8")
		self.assertIn(
			"Sin cobros del mes",
			js,
			"El panel debe mostrar estado vacío 'Sin cobros del mes'",
		)
		self.assertIn(
			"has_medios_chart",
			js,
			"Debe existir has_medios_chart para mostrar la tarjeta aunque no haya montos",
		)
		# No ocultar la tarjeta por montos en cero (patrón anterior)
		self.assertNotRegex(
			js,
			r"showMedios\s*=\s*medios\.disponible\s*&&\s*\(\s*medios\.efectivo",
			"No debe exigir montos > 0 para mostrar la tarjeta de medios de pago",
		)

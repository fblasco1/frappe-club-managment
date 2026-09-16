"""Tests del reporte PDF de ocupación de espacios (Épica 4 — solo download)."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase, make_secretaria_user
from club_management.spaces.helpers import insert_espacio, make_socio_portal_user
from club_management.spaces.services.ocupacion_reporte_pdf import (
	build_ocupacion_reporte_html_from_payloads,
	build_ocupacion_reporte_pdf_bytes,
)


class TestOcupacionReportePdf(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_secretaria_genera_pdf_con_magic_bytes(self) -> None:
		espacio = insert_espacio(
			"GIM PDF Report Test",
			horarios=[
				{
					"dia_semana": "Sabado",
					"hora_desde": "10:00:00",
					"hora_hasta": "12:00:00",
					"tipo_sesion": "Entrenamiento",
					"titulo": "Basquet PDF",
				}
			],
		)
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-05",
				"hora_desde": "14:00:00",
				"hora_hasta": "16:00:00",
				"tipo": "Evento club",
				"estado": "Confirmada",
				"motivo": "Partido PDF",
			}
		).insert(ignore_permissions=True)

		user = make_secretaria_user("secretaria.ocupacion.pdf@example.com")
		frappe.set_user(user)
		try:
			pdf = build_ocupacion_reporte_pdf_bytes(fecha="2026-09-05")
		finally:
			frappe.set_user("Administrator")

		self.assertIsInstance(pdf, (bytes, bytearray))
		self.assertTrue(bytes(pdf).startswith(b"%PDF"), "PDF debe empezar con %PDF")
		self.assertGreater(len(pdf), 100)

	def test_rango_dos_dias_produce_pdf_no_vacio(self) -> None:
		insert_espacio("Salon PDF Rango", tipo="Salon")
		user = make_secretaria_user("secretaria.ocupacion.rango@example.com")
		frappe.set_user(user)
		try:
			pdf = build_ocupacion_reporte_pdf_bytes(
				fecha_desde="2026-09-05",
				fecha_hasta="2026-09-06",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(bytes(pdf).startswith(b"%PDF"))
		self.assertGreater(len(pdf), 100)

	def test_socio_y_guest_permission_error(self) -> None:
		from club_management.spaces.api.ocupacion_reporte import download_ocupacion_pdf

		socio = make_socio_portal_user("socio.ocupacion.pdf@example.com")
		frappe.set_user(socio)
		try:
			with self.assertRaises(frappe.PermissionError):
				download_ocupacion_pdf(fecha="2026-09-05")
		finally:
			frappe.set_user("Administrator")

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				download_ocupacion_pdf(fecha="2026-09-05")
		finally:
			frappe.set_user("Administrator")

	def test_html_escapa_script_en_titulos(self) -> None:
		payload = {
			"fecha": "2026-09-05",
			"dia_semana": "Sabado",
			"slots": ["08:00", "08:30"],
			"espacios": [
				{
					"name": "Cancha XSS",
					"titulo": "Cancha XSS",
					"titulo_planilla": "Cancha XSS",
					"tipo": "Cancha",
				}
			],
			"bloques": [
				{
					"espacio": "Cancha XSS",
					"titulo": "<script>alert(1)</script>",
					"arrendatario_nombre": "<script>evil()</script>",
					"tipo": "Alquiler externo",
					"categoria": "Alquiler externo",
					"estado": "Pendiente",
					"inicio": "08:00",
					"fin": "08:30",
					"inicio_min": 8 * 60,
					"fin_min": 8 * 60 + 30,
					"color": "#7ec8e3",
					"source": "reserva",
				}
			],
			"leyenda": [],
			"ventana": {"desde": "08:00", "hasta": "04:00", "slot_minutos": 30},
		}
		html = build_ocupacion_reporte_html_from_payloads([payload])
		self.assertNotIn("<script>alert(1)</script>", html)
		self.assertNotIn("<script>evil()</script>", html)
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
		self.assertIn("&lt;script&gt;evil()&lt;/script&gt;", html)
		self.assertIn("Pendiente", html)

	def test_html_y_opciones_pdf_landscape_sin_margenes(self) -> None:
		from club_management.spaces.services.ocupacion_reporte_pdf import (
			ocupacion_pdf_wkhtml_options,
		)

		payload = {
			"fecha": "2026-09-05",
			"dia_semana": "Sabado",
			"slots": ["08:00", "08:30"],
			"espacios": [
				{"name": f"Esp {i}", "titulo_planilla": f"Col {i}", "titulo": f"Col {i}"}
				for i in range(10)
			],
			"bloques": [],
			"leyenda": [{"label": "Entrenamiento", "color": "#f5a3c7"}],
			"ventana": {"desde": "08:00", "hasta": "04:00", "slot_minutos": 30},
		}
		html = build_ocupacion_reporte_html_from_payloads([payload])
		self.assertIn("size: A4 landscape", html)
		self.assertIn("margin: 0", html)
		self.assertIn("table-layout: fixed", html)
		self.assertIn('class="print-format"', html)

		opts = ocupacion_pdf_wkhtml_options()
		self.assertEqual(opts["orientation"], "Landscape")
		self.assertEqual(opts["page-size"], "A4")
		for side in ("margin-top", "margin-bottom", "margin-left", "margin-right"):
			self.assertEqual(opts[side], "0mm", msg=side)

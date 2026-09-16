"""Tests del dashboard de ocupación de espacios."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.helpers import insert_espacio, make_socio_portal_user
from club_management.spaces.services.ocupacion_dashboard import (
	WINDOW_END_MIN,
	WINDOW_START_MIN,
	build_time_slots,
	get_ocupacion_dashboard_payload,
)


class TestOcupacionDashboard(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_slots_cubren_ventana_08_a_04(self) -> None:
		slots = build_time_slots()
		self.assertEqual(slots[0], "08:00")
		self.assertEqual(slots[-1], "03:30")
		# 20 horas * 2 = 40 franjas
		self.assertEqual(len(slots), 40)
		self.assertEqual(WINDOW_START_MIN, 8 * 60)
		self.assertEqual(WINDOW_END_MIN, 28 * 60)

	def test_payload_incluye_grilla_y_reserva_mismo_espacio(self) -> None:
		# 2026-09-05 = sábado
		espacio = insert_espacio(
			"GIM Dashboard Test",
			horarios=[
				{
					"dia_semana": "Sabado",
					"hora_desde": "10:00:00",
					"hora_hasta": "12:00:00",
					"tipo_sesion": "Entrenamiento",
					"titulo": "Basquet Escuela",
				},
				{
					"dia_semana": "Sabado",
					"hora_desde": "10:30:00",
					"hora_hasta": "11:30:00",
					"tipo_sesion": "Preparacion Fisica",
					"titulo": "PF Solape",
				},
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
				"motivo": "Partido externo",
			}
		).insert(ignore_permissions=True)

		payload = get_ocupacion_dashboard_payload(fecha="2026-09-05")
		self.assertEqual(payload["dia_semana"], "Sabado")
		self.assertTrue(any(e["name"] == espacio for e in payload["espacios"]))
		bloques_esp = [b for b in payload["bloques"] if b["espacio"] == espacio]
		self.assertGreaterEqual(len(bloques_esp), 3)
		titulos = {b["titulo"] for b in bloques_esp}
		self.assertTrue(any("Basquet" in t or "Escuela" in t for t in titulos) or any(bloques_esp))
		sources = {b["source"] for b in bloques_esp}
		self.assertIn("horario", sources)
		self.assertIn("reserva", sources)
		# Solape de dos horarios
		self.assertEqual(sum(1 for b in bloques_esp if b["source"] == "horario"), 2)
		# Color presente
		self.assertTrue(all(b.get("color") for b in bloques_esp))

	def test_payload_orden_columnas_planilla(self) -> None:
		from club_management.spaces.planilla import CANCHA_1, CANCHA_2, CANCHA_3

		for titulo, tipo in (
			(CANCHA_1, "Cancha"),
			(CANCHA_2, "Cancha"),
			(CANCHA_3, "Cancha"),
			("GIMNASIO BAJO TRIBUNA", "Gimnasio"),
			("SALON P.B.", "Salon"),
			("LA CASONA", "Salon"),
		):
			if not frappe.db.exists("Espacio", titulo):
				insert_espacio(titulo, tipo=tipo)

		payload = get_ocupacion_dashboard_payload(fecha="2026-09-05")
		names = [e["name"] for e in payload["espacios"]]
		self.assertEqual(names[:3], [CANCHA_1, CANCHA_2, CANCHA_3])
		self.assertEqual(payload["espacios"][0]["titulo_planilla"], "Cancha 1")
		labels = {item["label"] for item in payload["leyenda"]}
		self.assertIn("Alquiler socio", labels)
		self.assertNotIn("Uso interno", labels)

	def test_madrugada_del_dia_siguiente(self) -> None:
		espacio = insert_espacio(
			"Salon Madrugada",
			tipo="Salon",
			horarios=[
				{
					"dia_semana": "Domingo",
					"hora_desde": "01:00:00",
					"hora_hasta": "03:00:00",
					"tipo_sesion": "Entrenamiento",
					"titulo": "U21 Madrugada",
				}
			],
		)
		# Vista del sábado debe incluir ocupación del domingo 01–03
		payload = get_ocupacion_dashboard_payload(fecha="2026-09-05")
		bloques = [b for b in payload["bloques"] if b["espacio"] == espacio]
		self.assertEqual(len(bloques), 1)
		self.assertGreaterEqual(bloques[0]["inicio_min"], 24 * 60)
		self.assertLessEqual(bloques[0]["fin_min"], WINDOW_END_MIN)

	def test_api_deniega_socio(self) -> None:
		from club_management.spaces.api.ocupacion_dashboard import get_ocupacion_dashboard

		user = make_socio_portal_user("socio.ocupacion.deny@example.com")
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_ocupacion_dashboard(fecha="2026-09-05")
		finally:
			frappe.set_user("Administrator")

	def test_etiqueta_planilla_entrenamiento_y_alquiler(self) -> None:
		from club_management.spaces.helpers import ensure_actividad_tree
		from club_management.spaces.services.ocupacion_dashboard import (
			format_etiqueta_planilla,
		)

		# Formato puro (sin DB)
		label = format_etiqueta_planilla(
			{
				"etiqueta": "U15 AZUL — TOMAS CURI",
				"hora_desde": "16:00:00",
				"hora_hasta": "18:30:00",
			},
			inicio="16:00",
			fin="18:30",
		)
		self.assertEqual(label, "U15 AZUL\n16:00 - 18:30\nTOMAS CURI")

		act, grupo, equipo = ensure_actividad_tree(
			"Basquet Etiqueta Dash",
			"Basquet Etiqueta Dash / U15",
			"Basquet Etiqueta Dash / U15 / Azul",
		)
		espacio = insert_espacio(
			"Cancha Etiqueta Dash",
			alquilable=1,
			horarios=[
				{
					"dia_semana": "Sabado",
					"hora_desde": "16:00:00",
					"hora_hasta": "18:30:00",
					"tipo_sesion": "Entrenamiento",
					"actividad": act,
					"grupo_actividad": grupo,
					"equipo_actividad": equipo,
					"etiqueta": "U15 AZUL — TOMAS CURI",
				}
			],
		)
		frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": espacio,
				"fecha": "2026-09-05",
				"hora_desde": "19:00:00",
				"hora_hasta": "21:00:00",
				"tipo": "Alquiler externo",
				"modalidad_alquiler": "Temporal",
				"estado": "Confirmada",
				"motivo": "Alquiler cancha",
				"arrendatario_nombre": "Club Visitante SA",
			}
		).insert(ignore_permissions=True)

		payload = get_ocupacion_dashboard_payload(fecha="2026-09-05")
		bloques = [b for b in payload["bloques"] if b["espacio"] == espacio]
		ent = next(b for b in bloques if b["source"] == "horario")
		self.assertEqual(
			ent["etiqueta_planilla"],
			"U15 AZUL\n16:00 - 18:30\nTOMAS CURI",
		)
		# Sin prefijo de tipo de sesión en la etiqueta visible
		self.assertNotIn("Entrenamiento", ent["etiqueta_planilla"].split("\n")[0])

		alq = next(b for b in bloques if b["source"] == "reserva")
		self.assertEqual(
			alq["etiqueta_planilla"],
			"Alquiler cancha\n19:00 - 21:00\nClub Visitante SA",
		)

	def test_etiqueta_planilla_excepcion_usa_titulo_origen(self) -> None:
		from club_management.spaces.services.excepcion_horario import upsert_excepcion_horario_dia
		from club_management.spaces.services.ocupacion_dashboard import (
			format_etiqueta_planilla,
		)

		# Motivo operativo no debe reemplazar el título original
		label = format_etiqueta_planilla(
			{
				"source": "excepcion",
				"titulo_origen": "Entrenamiento — U15 AZUL — TOMAS CURI",
				"titulo": "Entrenamiento — U15 AZUL — TOMAS CURI",
				"motivo": "Ajuste por superposición / cronograma del día",
				"etiqueta": "U15 AZUL — TOMAS CURI",
			},
			inicio="18:00",
			fin="19:30",
		)
		self.assertEqual(label, "U15 AZUL\n18:00 - 19:30\nTOMAS CURI")
		self.assertNotIn("Ajuste", label)

		origen = insert_espacio(
			"Cancha Exc Origen Label",
			horarios=[
				{
					"dia_semana": "Sabado",
					"hora_desde": "16:00:00",
					"hora_hasta": "18:00:00",
					"tipo_sesion": "Entrenamiento",
					"etiqueta": "U17 ROJO — MARIA LOPEZ",
				}
			],
		)
		destino = insert_espacio("Cancha Exc Destino Label")
		doc = frappe.get_doc("Espacio", origen)
		row = doc.horarios[0].name
		upsert_excepcion_horario_dia(
			fecha="2026-09-05",
			espacio_origen=origen,
			horario_row=row,
			espacio_destino=destino,
			hora_desde="17:00:00",
			hora_hasta="18:30:00",
			motivo="Partido local — no usar como etiqueta",
		)

		payload = get_ocupacion_dashboard_payload(fecha="2026-09-05")
		exc_bloques = [
			b
			for b in payload["bloques"]
			if b["espacio"] == destino and b["source"] == "excepcion"
		]
		self.assertEqual(len(exc_bloques), 1)
		self.assertEqual(
			exc_bloques[0]["etiqueta_planilla"],
			"U17 ROJO\n17:00 - 18:30\nMARIA LOPEZ",
		)
		self.assertNotIn("Partido local", exc_bloques[0]["etiqueta_planilla"])

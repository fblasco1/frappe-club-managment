"""UAT smoke SP-3: externo + confirmación Coordinación + portal socio API.

  bench --site dev.localhost execute club_management.spaces.qa.uat_spaces_smoke.run
"""

from __future__ import annotations

import base64
import importlib
from typing import Any

import frappe
from frappe.utils import add_days, today
from frappe.utils.file_manager import save_file

from club_management.spaces.helpers import insert_espacio
from club_management.spaces.tests.test_portal_reservas import _ensure_alquiler_item


def _ok(msg: str) -> None:
	print("PASS|" + msg)


def _fail(msg: str) -> None:
	print("FAIL|" + msg)
	raise RuntimeError(msg)


def smoke_externo() -> str:
	frappe.set_user("Administrator")
	_ensure_alquiler_item(rate=25000.0)
	frappe.db.set_single_value("Club Settings", "espacios_reserva_externa_habilitada", 1)
	esp = insert_espacio("UAT Externo Smoke", tipo="Cancha", alquilable=1, habilitado=1)
	frappe.db.set_value("Espacio", esp, "tarifa_externo", 30000)

	api = importlib.import_module("club_management.spaces.api.externo_reservas")
	frappe.set_user("Guest")
	ses = api.abrir_sesion_reserva_externa()
	token = ses.get("sesion_token")
	if not token:
		_fail("abrir_sesion sin token")
	_ok("externo sesion_token")

	fecha = str(add_days(today(), 3))
	disp = api.get_espacios_disponibles_externo(sesion_token=token, fecha=fecha)
	espacios = disp.get("espacios") or []
	target = next((e for e in espacios if e.get("espacio") == esp), None)
	if not target:
		_fail("espacio no en disponibilidad")
	slot = next((s for s in target["slots"] if s.get("estado") == "libre"), None)
	if not slot:
		_fail("sin slot libre")
	_ok("externo disponibilidad")

	sol = api.solicitar_reserva_externa(
		sesion_token=token,
		espacio=esp,
		fecha=fecha,
		hora_inicio=slot["hora_inicio"],
		hora_fin=slot["hora_fin"],
		arrendatario_nombre="UAT Externo",
		arrendatario_contacto="uat.externo@example.com",
	)
	reserva = sol.get("reserva")
	acceso = sol.get("token_acceso")
	if not reserva or not acceso or sol.get("estado") != "Pendiente":
		_fail("solicitar_reserva_externa invalida: " + str(sol))
	_ok("externo solicitar Pendiente " + reserva)

	# PDF mínimo válido (pypdf / File no deben fallar en UAT).
	pdf = (
		b"%PDF-1.4\n"
		b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
		b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
		b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>endobj\n"
		b"xref\n0 4\n0000000000 65535 f \n"
		b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
		b"trailer<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
	)
	up = api.upload_y_adjuntar_comprobante_externo(
		token_acceso=acceso,
		filename="uat.pdf",
		content_b64=base64.b64encode(pdf).decode(),
	)
	if not up.get("comprobante"):
		_fail("upload comprobante")
	_ok("externo PDF adjunto")

	email = "fscianca@icdpedroechague.com.ar"
	if not frappe.db.exists("User", email):
		_fail("falta usuario coordinacion")
	frappe.set_user(email)
	conf_api = importlib.import_module("club_management.spaces.api.confirmacion_reservas")
	pend = conf_api.list_reservas_pendientes_confirmacion()
	if not any(p.get("name") == reserva for p in pend):
		_fail("reserva no en cola coordinacion")
	_ok("cola coordinacion ve reserva")

	res = conf_api.confirmar_reserva_espacio(reserva)
	if res.get("estado") != "Confirmada":
		_fail("confirmacion: " + str(res))
	_ok("coordinacion confirmo " + reserva)

	frappe.set_user("Guest")
	det = api.get_reserva_externa(acceso)
	if det.get("estado") != "Confirmada":
		_fail("get_reserva post-confirm: " + str(det))
	_ok("externo ve Confirmada via token")
	return reserva


def smoke_socio() -> str:
	from club_management.members.qa.portal_reservas_qa_user import ensure as ensure_qa

	frappe.set_user("Administrator")
	info = ensure_qa()
	email = (info or {}).get("email") or "reserva.qa@icdpe.test"
	esp = insert_espacio("UAT Socio Smoke", tipo="Salon", alquilable=1, habilitado=1)
	frappe.db.set_value("Espacio", esp, "tarifa_socio", 12000)
	_ensure_alquiler_item(rate=12000.0)

	api = importlib.import_module("club_management.spaces.api.portal_reservas")
	frappe.set_user(email)
	fecha = str(add_days(today(), 4))
	disp = api.get_espacios_disponibles(fecha=fecha)
	target = next((e for e in (disp.get("espacios") or []) if e.get("espacio") == esp), None)
	if not target:
		_fail("socio: espacio no listado")
	slot = next((s for s in target["slots"] if s.get("estado") == "libre"), None)
	if not slot:
		_fail("socio: sin slot")
	sol: dict[str, Any] = api.solicitar_reserva_espacio(
		espacio=esp,
		fecha=fecha,
		hora_inicio=slot["hora_inicio"],
		hora_fin=slot["hora_fin"],
	)
	reserva = sol.get("reserva") or sol.get("name")
	if not reserva and sol.get("reservas"):
		first = sol["reservas"][0]
		reserva = first.get("reserva") or first.get("name")
	if not reserva:
		_fail("socio solicitar: " + str(sol))
	_ok("socio solicitar " + str(reserva))

	pdf = (
		b"%PDF-1.4\n"
		b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
		b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
		b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>endobj\n"
		b"xref\n0 4\n0000000000 65535 f \n"
		b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
		b"trailer<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
	)
	f = save_file(
		"socio-uat.pdf",
		pdf,
		"Reserva Espacio",
		reserva,
		is_private=1,
	)
	adj = api.adjuntar_comprobante_reserva(reserva=reserva, file_url=f.file_url)
	if not adj.get("comprobante"):
		_fail("socio adjuntar")
	_ok("socio PDF")

	frappe.set_user("fscianca@icdpedroechague.com.ar")
	conf_api = importlib.import_module("club_management.spaces.api.confirmacion_reservas")
	conf_api.confirmar_reserva_espacio(reserva)
	doc = frappe.get_doc("Reserva Espacio", reserva)
	if doc.estado != "Confirmada":
		_fail("socio confirmacion")
	_ok("socio Confirmada " + reserva)
	return str(reserva)


def run() -> dict[str, str]:
	print("=== UAT SPACES SMOKE ===")
	r1 = smoke_externo()
	r2 = smoke_socio()
	frappe.set_user("Administrator")
	frappe.db.commit()
	print("OK|externo=" + r1 + "|socio=" + r2)
	return {"externo": r1, "socio": r2}

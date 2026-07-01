"""Generación de recibo de pago térmico ESC/POS."""

from __future__ import annotations

import base64
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from club_management.members.services.cobranza_manual import SALES_INVOICE_DOCTYPE, get_club_settings

ANCHO_CARACTERES: dict[int, int] = {58: 32, 80: 48}

_ESC_INIT = b"\x1b\x40"
_ESC_ALIGN_CENTER = b"\x1b\x61\x01"
_ESC_ALIGN_LEFT = b"\x1b\x61\x00"
_ESC_BOLD_ON = b"\x1b\x45\x01"
_ESC_BOLD_OFF = b"\x1b\x45\x00"
_GS_CUT = b"\x1d\x56\x00"

_DEFAULT_ENCABEZADO = {
	"institucion_nombre": "Institucion Cultural y Deportiva Pedro Echague",
	"institucion_direccion": "PORTELA 836 - CABA",
	"cuit": "30-59845346-9",
	"condicion_iva": "IVA EXENTO",
}
_DEFAULT_PIE = "SOMOS ECHAGUE, SOMOS FAMILIA !!"


def format_monto_ar(monto: float) -> str:
	"""Formato `$29.000` (pesos argentinos, separador de miles con punto)."""
	valor = int(round(flt(monto)))
	return f"${valor:,}".replace(",", ".")


def ancho_caracteres(ancho_papel_mm: int) -> int:
	return ANCHO_CARACTERES.get(ancho_papel_mm, ANCHO_CARACTERES[58])


def _separador(ancho: int) -> str:
	return "-" * ancho


def _wrap_text(texto: str, ancho: int) -> list[str]:
	palabras = (texto or "").split()
	if not palabras:
		return [""]
	lineas: list[str] = []
	actual = palabras[0]
	for palabra in palabras[1:]:
		if len(actual) + 1 + len(palabra) <= ancho:
			actual = f"{actual} {palabra}"
		else:
			lineas.append(actual)
			actual = palabra
	lineas.append(actual)
	return lineas


def _centrar(texto: str, ancho: int) -> str:
	linea = (texto or "").strip()
	if len(linea) >= ancho:
		return linea[:ancho]
	pad = (ancho - len(linea)) // 2
	return " " * pad + linea


def _centrar_multilinea(texto: str, ancho: int) -> list[str]:
	return [_centrar(linea, ancho) for linea in _wrap_text(texto, ancho)]


def _linea_concepto_monto(concepto: str, monto: float, ancho: int) -> str:
	concepto = (concepto or _("Concepto")).strip().upper()
	monto_txt = format_monto_ar(monto)
	if len(concepto) + len(monto_txt) + 1 > ancho:
		return f"{concepto}\n{' ' * max(0, ancho - len(monto_txt))}{monto_txt}"
	espacios = ancho - len(concepto) - len(monto_txt)
	return f"{concepto}{' ' * espacios}{monto_txt}"


def get_recibo_config() -> dict[str, Any]:
	settings = get_club_settings()
	ancho = int(settings.recibo_ancho_papel_mm or 58)
	if ancho not in ANCHO_CARACTERES:
		ancho = 58
	return {
		"encabezado": {
			"institucion_nombre": (
				settings.recibo_institucion_nombre or _DEFAULT_ENCABEZADO["institucion_nombre"]
			),
			"institucion_direccion": (
				settings.recibo_institucion_direccion or _DEFAULT_ENCABEZADO["institucion_direccion"]
			),
			"cuit": (settings.recibo_cuit or "").strip(),
			"condicion_iva": (
				settings.recibo_condicion_iva or _DEFAULT_ENCABEZADO["condicion_iva"]
			),
		},
		"mensaje_pie": (settings.recibo_mensaje_pie or _DEFAULT_PIE).strip(),
		"ancho_papel_mm": ancho,
		"impresora_url": (settings.recibo_impresora_url or "").strip(),
	}


def _lineas_desde_payment_entry(payment_entry_name: str) -> list[dict[str, Any]]:
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"parent": payment_entry_name,
			"reference_doctype": SALES_INVOICE_DOCTYPE,
		},
		fields=["reference_name"],
		order_by="idx asc",
	)
	lineas: list[dict[str, Any]] = []
	for ref in refs:
		items = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": ref.reference_name},
			fields=["description", "item_code", "amount"],
			order_by="idx asc",
		)
		for item in items:
			concepto = (item.description or item.item_code or _("Concepto")).strip()
			lineas.append({"concepto": concepto, "monto": flt(item.amount)})
	return lineas


def _fecha_hora_cobro(payment_entry_name: str) -> tuple[str, str]:
	pe = frappe.db.get_value(
		"Payment Entry",
		payment_entry_name,
		["posting_date", "creation"],
		as_dict=True,
	)
	if not pe:
		frappe.throw(_("Payment Entry no encontrado."), frappe.DoesNotExistError)
	fecha_dt = get_datetime(pe.posting_date)
	fecha = fecha_dt.strftime("%d/%m/%Y")
	hora_dt = get_datetime(pe.creation or now_datetime())
	hora = hora_dt.strftime("%H:%M")
	return fecha, hora


def build_recibo_pago(payment_entry_name: str) -> dict[str, Any]:
	"""Arma el payload del recibo a partir de un Payment Entry submitted."""
	if not frappe.db.exists("Payment Entry", payment_entry_name):
		frappe.throw(_("Payment Entry no encontrado."), frappe.DoesNotExistError)
	if frappe.db.get_value("Payment Entry", payment_entry_name, "docstatus") != 1:
		frappe.throw(_("El cobro debe estar confirmado."), frappe.ValidationError)

	config = get_recibo_config()
	lineas = _lineas_desde_payment_entry(payment_entry_name)
	if not lineas:
		frappe.throw(_("No hay conceptos para el recibo."), frappe.ValidationError)

	total = sum(flt(row["monto"]) for row in lineas)
	fecha, hora = _fecha_hora_cobro(payment_entry_name)

	data: dict[str, Any] = {
		"comprobante": payment_entry_name,
		"fecha": fecha,
		"hora": hora,
		"lineas": lineas,
		"total": total,
		"mensaje_pie": config["mensaje_pie"],
		"ancho_papel_mm": config["ancho_papel_mm"],
		"impresora_url": config["impresora_url"],
		"encabezado": config["encabezado"],
	}
	data["texto"] = render_recibo_texto(data)
	data["escpos_base64"] = base64.b64encode(render_recibo_escpos(data)).decode("ascii")
	return data


def render_recibo_texto(data: dict[str, Any]) -> str:
	ancho = ancho_caracteres(int(data.get("ancho_papel_mm") or 58))
	enc = data.get("encabezado") or {}
	lineas_txt: list[str] = []

	for campo in ("institucion_nombre", "institucion_direccion"):
		valor = (enc.get(campo) or "").strip()
		if valor:
			lineas_txt.extend(_centrar_multilinea(valor, ancho))

	cuit = (enc.get("cuit") or "").strip()
	condicion = (enc.get("condicion_iva") or "").strip()
	if cuit and condicion:
		lineas_txt.extend(_centrar_multilinea(f"CUIT: {cuit} - {condicion}", ancho))
	elif cuit:
		lineas_txt.extend(_centrar_multilinea(f"CUIT: {cuit}", ancho))
	elif condicion:
		lineas_txt.extend(_centrar_multilinea(condicion, ancho))

	lineas_txt.append(_separador(ancho))
	comprobante = data.get("comprobante") or ""
	comp_label = f"COMPROBANTE Nº {comprobante}"
	for comp_linea in _wrap_text(comp_label, ancho):
		lineas_txt.append(comp_linea)
	fecha_hora = f"Fecha: {data.get('fecha', '')}  Hora: {data.get('hora', '')}"
	for fh_linea in _wrap_text(fecha_hora, ancho):
		lineas_txt.append(fh_linea)
	lineas_txt.append(_separador(ancho))
	hdr_esp = ancho - len("CONCEPTO") - len("VALOR")
	lineas_txt.append(f"CONCEPTO{' ' * hdr_esp}VALOR")
	lineas_txt.append(_separador(ancho))

	for row in data.get("lineas") or []:
		lineas_txt.append(_linea_concepto_monto(row.get("concepto", ""), flt(row.get("monto")), ancho))

	lineas_txt.append(_separador(ancho))
	total_txt = f"TOTAL: {format_monto_ar(flt(data.get('total')))}"
	lineas_txt.append(total_txt[:ancho])
	lineas_txt.append(_separador(ancho))

	pie = (data.get("mensaje_pie") or "").strip()
	if pie:
		lineas_txt.extend(_centrar_multilinea(pie, ancho))

	return "\n".join(lineas_txt)


def render_recibo_escpos(data: dict[str, Any]) -> bytes:
	"""Genera bytes ESC/POS para impresora térmica Star / compatible."""
	lineas = render_recibo_texto(data).split("\n")
	enc = data.get("encabezado") or {}
	centradas: set[str] = set()
	for campo in ("institucion_nombre", "institucion_direccion"):
		valor = (enc.get(campo) or "").strip()
		if valor:
			for linea in _centrar_multilinea(valor, ancho_caracteres(int(data.get("ancho_papel_mm") or 58))):
				centradas.add(linea.strip())
	cuit = (enc.get("cuit") or "").strip()
	condicion = (enc.get("condicion_iva") or "").strip()
	if cuit and condicion:
		for linea in _centrar_multilinea(
			f"CUIT: {cuit} - {condicion}", ancho_caracteres(int(data.get("ancho_papel_mm") or 58))
		):
			centradas.add(linea.strip())
	elif cuit:
		for linea in _centrar_multilinea(f"CUIT: {cuit}", ancho_caracteres(int(data.get("ancho_papel_mm") or 58))):
			centradas.add(linea.strip())
	elif condicion:
		for linea in _centrar_multilinea(condicion, ancho_caracteres(int(data.get("ancho_papel_mm") or 58))):
			centradas.add(linea.strip())
	pie = (data.get("mensaje_pie") or "").strip()
	if pie:
		for linea in _centrar_multilinea(pie, ancho_caracteres(int(data.get("ancho_papel_mm") or 58))):
			centradas.add(linea.strip())

	chunks: list[bytes] = [_ESC_INIT]
	for linea in lineas:
		encoded = linea.encode("latin-1", errors="replace")
		if linea.strip() in centradas:
			chunks.extend([_ESC_ALIGN_CENTER, encoded, b"\n"])
		elif linea.startswith("COMPROBANTE") or linea.startswith("TOTAL:"):
			chunks.extend([_ESC_ALIGN_LEFT, _ESC_BOLD_ON, encoded, _ESC_BOLD_OFF, b"\n"])
		else:
			chunks.extend([_ESC_ALIGN_LEFT, encoded, b"\n"])

	chunks.extend([b"\n\n", _GS_CUT])
	return b"".join(chunks)

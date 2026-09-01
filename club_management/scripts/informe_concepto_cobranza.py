"""Cruce concepto del informe Excel ↔ ítem / línea en Sales Invoice.

Spec: `club_management/specs/informe_concepto_cobranza.md`
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import frappe
from frappe.utils import flt

from club_management.activities.services.inscripcion_socio import resolve_item_arancel_inscripcion
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	get_club_settings,
)

# Expediente FEBAMBA: cargo extra / multa (ICDPE-MULTA u otro ítem puntual).
FEBAMBA_MONTO_CUOTA = 83333.0
FEBAMBA_MONTO_TOTAL = 250000.0

# Ítem habitual de Cuota Complementaria (cargo extra temporal por actividad/grupo).
ITEM_CUOTA_COMPLEMENTARIA = "ICDPE-CARGO-VARIOS"

# Alias informe → item_code(s) explícitos (normalizado sin acentos).
# «CTO COMP …» NO va aquí: es Cuota Complementaria (cargo extra), cruce por descripción.
_INFORME_ITEM_EXACTO: dict[str, tuple[str, ...]] = {
	"EXPEDIENTE FEBAMBA": ("ICDPE-MULTA", "EXPEDIENTE-FEBAMBA", "ICDPE-FEBAMBA", "ICDPE-EXPEDIENTE-FEBAMBA"),
	"CUOTA FEDER VOLEY": ("ICDPE-CUOTA-FEDERATIVA-voley",),
	"CUOTA FEDERATIVA VOLEY": ("ICDPE-CUOTA-FEDERATIVA-voley",),
	"ADICIONAL BASQUET ESCUELITA": ("ICDPE-BASQUET-ESCUELITA",),
	"ADICIONAL PATIN 1 NIVEL": ("ICDPE-PATIN-MINI",),
	"ADICIONAL PATIN 1° NIVEL": ("ICDPE-PATIN-MINI",),
	"ADICIONAL VOLEY ESCUELA": ("ICDPE-VOLEY-ESCUELA",),
	"ADICIONAL VOLEY MAYOR Y VOLEY MENOR": ("ICDPE-VOLEY-FEDERADO",),
	"ADICIONAL VOLEY MENOR": ("ICDPE-VOLEY-FEDERADO",),
	"FUNCIONAL GAP": ("ICDPE-FUNCIONAL-1-CLASE", "ICDPE-FUNCIONAL-2-CLASES"),
	"ARANCEL DANZA": ("ICDPE-DANZA",),
	"ARANCEL TAE KWON-DO": ("ICDPE-TAEKWONDO",),
	"ARANCEL TAEKWONDO": ("ICDPE-TAEKWONDO",),
	"AVANZADO 3": ("ICDPE-PATIN-AVANZADO",),
	"ARTISTICA 1 CLASE": ("ICDPE-GIMNASIA-ARTISTICA-1-CLASE",),
	"GIMNASIA ARTISTICA": ("ICDPE-GIMNASIA-ARTISTICA-2-CLASES",),
	"FUTBOL FAFI": ("ICDPE-FUTBOL-FAFI",),
	"FUTBOL TABI": ("ICDPE-FUTBOL-TABI-A", "ICDPE-FUTBOL-TABI-B"),
	"FUTBOL ESCUELITA": ("ICDPE-FUTBOL-TABI-B",),
	"BOXEO 3 VECES": ("ICDPE-BOXEO-3-CLASES",),
	"BASQ SUP FEM": ("ICDPE-BASQUET-FEMENINO-SUP",),
	"PATIN INTERMEDIO": ("ICDPE-PATIN-INTERMEDIO",),
}

# Etiquetas de equipo / tira → arancel (cuando no hay «Adicional»).
_ARANCEL_EQUIPO_ALIAS: dict[str, tuple[str, ...]] = {
	"U17 FLEX": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",),
	"U15 FLEX": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",),
	"PRIMERA FLEX": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",),
	"U17 MASC": (
		"ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",
		"ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",
	),
	"JUVENILES A U17": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL", "ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX"),
	"JUVENILES B U17": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",),
	"CADETES A U15": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
	"CADETES B U15": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",),
	"INFANTILES B U13": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"INFA A U13": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"MINI A U11": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"MINI B U11": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"PRE-MINI A U9": ("ICDPE-BASQUET-ESCUELITA",),
	"PRE-MINI B U9": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"LIGA APROX A U21": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
	"LIGA APROX B U21": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",),
}

_CUOTA_CATEGORIA_KEYWORDS: tuple[tuple[str, str], ...] = (
	("HIJO 2", "Menor Hijo 2"),
	("MENOR HIJO", "Menor Hijo 2"),
	("MENOR", "Menor"),
	("ACTIVO", "Activo"),
	("ADHERENTE", "Adherente"),
	("JUBILADO", "Jubilado"),
	("VITALICIO", "Vitalicio"),
)

_FED_BASQUET_MASC_RE = re.compile(
	r"(C\.?\s*FED|CUOTA\s+FEDER)\b.*(MASC|FLEX|U9|U11|U13|U15|U17|U21|SUPERIOR)",
	re.I,
)
_FED_BASQUET_FEM_RE = re.compile(
	r"(C\.?\s*FED|CUOTA\s+FEDER)\b.*(FEM|FEMENIN)",
	re.I,
)
_PERIODO_EN_TEXTO_RE = re.compile(r"\(\d{2}/\d{4}\)")


def es_cuota_complementaria(concepto: str | None) -> bool:
	"""True si el renglón del informe es Cuota Complementaria (CTO COMP …)."""
	return normalizar_concepto_informe(concepto).startswith("CTO COMP")


def normalizar_clave_cuota_complementaria(raw: str | None) -> str:
	"""Clave canónica para comparar informe vs descripción/título de cargo extra."""
	t = normalizar_concepto_informe(raw)
	t = _PERIODO_EN_TEXTO_RE.sub("", t).strip()
	idx = t.find("CTO COMP")
	if idx > 0:
		t = t[idx:]
	t = t.replace("BASQUET", "BASQ")
	t = t.replace("BASQUE", "BASQ")
	t = re.sub(r"\bTIA\b", "TIRA", t)
	t = t.replace(" TIRA A Y B", " TIRA A/B/FLEX")
	t = re.sub(r"CTO COMP BASQ/FEM\b", "CTO COMP BASQ ESC/FEM", t)
	t = re.sub(r"\bFUTBOL\b", "FUT", t)
	if "FAFI" in t and "TABI" in t:
		t = re.sub(r"CTO COMP FUT\s+(FAFI/TABI|TABI/FAFI)", "CTO COMP FUT FAFI TABI", t)
	if re.search(r"CTO COMP FUT\s+ESC", t):
		t = re.sub(r"CTO COMP FUT\s+ESC\b.*", "CTO COMP FUT ESC", t)
	t = re.sub(r"\s+", " ", t).strip()
	return t


def cuotas_complementarias_equivalentes(informe: str | None, descripcion: str | None) -> bool:
	"""True si descripción de SI/cargo corresponde al concepto CTO COMP del informe."""
	clave_a = normalizar_clave_cuota_complementaria(informe)
	clave_b = normalizar_clave_cuota_complementaria(descripcion)
	if not clave_a.startswith("CTO COMP") or not clave_b.startswith("CTO COMP"):
		return False
	return clave_a == clave_b


def _facturas_socio_periodo(socio_name: str, periodo: str, *, solo_impagas: bool) -> list[str]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	filters: dict[str, Any] = {campo_socio: socio_name, "docstatus": 1}
	if solo_impagas:
		filters["outstanding_amount"] = [">", 0]
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo
	return frappe.get_all(SALES_INVOICE_DOCTYPE, filters=filters, pluck="name", order_by="name asc")


def linea_cuota_complementaria_en_periodo(
	socio_name: str,
	periodo: str,
	concepto: str | None,
	*,
	solo_impagas: bool = True,
	reservadas: set[str] | None = None,
) -> tuple[str, str, float] | None:
	"""Encuentra línea CTO COMP; `solo_impagas=False` incluye SI saldadas (clasificación)."""
	if not es_cuota_complementaria(concepto):
		return None
	reservadas = reservadas or set()
	for invoice_name in _facturas_socio_periodo(socio_name, periodo, solo_impagas=solo_impagas):
		if invoice_name in reservadas:
			continue
		for line in _lineas_factura(invoice_name):
			if cuotas_complementarias_equivalentes(concepto, line.get("description")):
				code = (line.get("item_code") or ITEM_CUOTA_COMPLEMENTARIA).strip()
				return invoice_name, code, flt(line.get("amount"))
	return None


def normalizar_concepto_informe(raw: str | None) -> str:
	"""MAYÚSCULAS ASCII, espacios colapsados, º→ N."""
	text = (raw or "").strip()
	if not text:
		return ""
	decomposed = unicodedata.normalize("NFKD", text)
	ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
	ascii_only = ascii_only.replace("º", " ").replace("°", " ")
	ascii_only = re.sub(r"\s+", " ", ascii_only).strip().upper()
	return ascii_only


def _item_codes_cuota_por_categoria(categoria: str) -> tuple[str, ...]:
	settings = get_club_settings()
	for row in settings.cuotas_categoria or []:
		if (row.categoria or "").strip() == categoria:
			code = (row.item or settings.item_cuota_social or "").strip()
			if code:
				return (code,)
	base = (settings.item_cuota_social or "").strip()
	return (base,) if base else ()


def _item_codes_cuota_desde_informe(concepto_norm: str) -> tuple[str, ...]:
	if "CUOTA SOCIAL" not in concepto_norm and "CARNET" not in concepto_norm:
		return ()
	for keyword, categoria in _CUOTA_CATEGORIA_KEYWORDS:
		if keyword in concepto_norm:
			return _item_codes_cuota_por_categoria(categoria)
	return _item_codes_cuota_por_categoria("Activo")


def _item_codes_federativa(concepto_norm: str) -> tuple[str, ...]:
	if "VOLEY" in concepto_norm or "VOLLEY" in concepto_norm:
		if "FED" in concepto_norm or "FEDER" in concepto_norm:
			return ("ICDPE-CUOTA-FEDERATIVA-voley",)
	if _FED_BASQUET_FEM_RE.search(concepto_norm):
		return ("ICDPE-CUOTA-FEDERATIVA-basquet-femenino",)
	if _FED_BASQUET_MASC_RE.search(concepto_norm) or concepto_norm.startswith("C FED") or concepto_norm.startswith("C.FED"):
		return ("ICDPE-CUOTA-FEDERATIVA-basquet-masculino",)
	return ()


def _item_codes_inscripcion_socio(socio_name: str) -> tuple[str, ...]:
	codes: list[str] = []
	for ins in frappe.get_all(
		"Inscripcion Actividad",
		filters={"socio": socio_name, "estado": "Activa"},
		pluck="name",
	):
		item = resolve_item_arancel_inscripcion(ins)
		if item and item not in codes:
			codes.append(item)
	return tuple(codes)


def _item_codes_funcional_gap(socio_name: str, *, monto_hint: float = 0) -> tuple[str, ...]:
	"""Arancel Funcional GAP (grupo Prof. Noelia) según inscripción activa."""
	codes: list[str] = []
	for ins in frappe.get_all(
		"Inscripcion Actividad",
		filters={"socio": socio_name, "estado": "Activa"},
		fields=["name", "grupo_actividad"],
	):
		grupo = (ins.get("grupo_actividad") or "").upper()
		if "FUNCIONAL" not in grupo or "GAP" not in grupo:
			continue
		item = resolve_item_arancel_inscripcion(ins["name"])
		if item and item not in codes:
			codes.append(item)
	if not codes:
		return _INFORME_ITEM_EXACTO["FUNCIONAL GAP"]
	if len(codes) == 1:
		return (codes[0],)
	if monto_hint > 0:
		codes.sort(
			key=lambda code: abs(
				flt(frappe.db.get_value("Item", code, "standard_rate") or 0) - flt(monto_hint)
			)
		)
	return tuple(codes)


def resolver_item_codes_concepto(
	concepto: str | None,
	*,
	socio_name: str | None = None,
	monto_abonado: float = 0,
) -> tuple[str, ...]:
	"""Devuelve item_code candidatos para un renglón del informe."""
	norm = normalizar_concepto_informe(concepto)
	if not norm:
		return ()

	if es_cuota_complementaria(norm):
		# Se resuelve por descripción/título (ICDPE-CARGO-VARIOS), no por arancel.
		return ()

	if norm in _INFORME_ITEM_EXACTO:
		if norm == "FUNCIONAL GAP" and socio_name:
			return _item_codes_funcional_gap(socio_name, monto_hint=monto_abonado)
		return _INFORME_ITEM_EXACTO[norm]

	if "FUNCIONAL" in norm and "GAP" in norm:
		if socio_name:
			return _item_codes_funcional_gap(socio_name, monto_hint=monto_abonado)
		return _INFORME_ITEM_EXACTO["FUNCIONAL GAP"]

	cuota = _item_codes_cuota_desde_informe(norm)
	if cuota:
		return cuota

	fed = _item_codes_federativa(norm)
	if fed:
		return fed

	if norm in _ARANCEL_EQUIPO_ALIAS:
		return _ARANCEL_EQUIPO_ALIAS[norm]

	if norm.startswith("EXPEDIENTE FEBAMBA") or norm == "FEBAMBA":
		return _INFORME_ITEM_EXACTO["EXPEDIENTE FEBAMBA"]

	if socio_name:
		por_inscripcion = _item_codes_inscripcion_socio(socio_name)
		if len(por_inscripcion) == 1:
			return por_inscripcion

	return ()


def _lineas_factura(invoice_name: str) -> list[dict[str, Any]]:
	return frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		fields=["item_code", "description", "amount", "rate", "qty"],
		order_by="idx asc",
	)


def _linea_coincide_item(line: dict[str, Any], item_codes: tuple[str, ...]) -> bool:
	code = (line.get("item_code") or "").strip()
	if code and code in item_codes:
		return True
	desc = normalizar_concepto_informe(line.get("description"))
	for candidate in item_codes:
		if candidate in (line.get("item_code") or ""):
			return True
		name = frappe.db.get_value("Item", candidate, "item_name") if frappe.db.exists("Item", candidate) else None
		if name and normalizar_concepto_informe(name) in desc:
			return True
	return False


def _linea_coincide_febamba(line: dict[str, Any], monto: float, invoice_name: str | None = None) -> bool:
	text = normalizar_concepto_informe(
		f"{line.get('description') or ''} {line.get('item_code') or ''}"
	)
	if "FEBAMBA" in text or "EXPEDIENTE" in text:
		return True
	if invoice_name:
		remarks = frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "remarks") or ""
		if "FEBAMBA" in normalizar_concepto_informe(remarks):
			return True
	amt = flt(line.get("amount"))
	if abs(amt - FEBAMBA_MONTO_CUOTA) <= 1.0 or abs(amt - FEBAMBA_MONTO_TOTAL) <= 1.0:
		return True
	return abs(monto - amt) <= 1.0 and amt > 0


def buscar_linea_factura_concepto(
	socio_name: str,
	periodo: str,
	concepto: str | None,
	*,
	monto_abonado: float = 0.0,
	reservadas: set[str] | None = None,
) -> tuple[str, str, float] | None:
	"""Encuentra `(invoice_name, item_code, monto_linea)` impaga para el concepto."""
	reservadas = reservadas or set()
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return None

	norm = normalizar_concepto_informe(concepto)
	item_codes = resolver_item_codes_concepto(concepto, socio_name=socio_name, monto_abonado=monto_abonado)
	es_febamba = "FEBAMBA" in norm or "EXPEDIENTE FEBAMBA" in norm
	es_cto_comp = es_cuota_complementaria(concepto)

	if es_cto_comp:
		match = linea_cuota_complementaria_en_periodo(
			socio_name,
			periodo,
			concepto,
			solo_impagas=True,
			reservadas=reservadas,
		)
		if match:
			return match

	invoices = _facturas_socio_periodo(socio_name, periodo, solo_impagas=True)

	for invoice_name in invoices:
		if invoice_name in reservadas:
			continue
		for line in _lineas_factura(invoice_name):
			if es_febamba and _linea_coincide_febamba(line, monto_abonado, invoice_name):
				code = (line.get("item_code") or "").strip()
				return invoice_name, code, flt(line.get("amount"))
			if item_codes and _linea_coincide_item(line, item_codes):
				code = (line.get("item_code") or "").strip()
				return invoice_name, code, flt(line.get("amount"))

	# Fallback: descripción de línea contiene texto del concepto
	if norm:
		for invoice_name in invoices:
			if invoice_name in reservadas:
				continue
			for line in _lineas_factura(invoice_name):
				desc = normalizar_concepto_informe(line.get("description"))
				if norm in desc or desc in norm:
					code = (line.get("item_code") or "").strip()
					return invoice_name, code, flt(line.get("amount"))

	return None


def buscar_cargo_pendiente_cuota_complementaria(
	socio_name: str,
	concepto_informe: str | None,
) -> dict[str, Any] | None:
	"""Primer `Cargo Socio` pendiente recurrente cuyo título equivale al concepto CTO COMP."""
	if not es_cuota_complementaria(concepto_informe):
		return None
	if not frappe.db.exists("DocType", "Cargo Socio"):
		return None
	for row in frappe.get_all(
		"Cargo Socio",
		filters={
			"socio": socio_name,
			"estado": "Pendiente",
			"modo_cobro": "Recurrente",
		},
		fields=["name", "titulo", "monto", "fecha_desde", "fecha_hasta", "item"],
		order_by="name asc",
	):
		titulo = row.get("titulo") or ""
		if "CTO COMP" not in titulo.upper():
			continue
		if cuotas_complementarias_equivalentes(concepto_informe, titulo):
			return row
	return None


def necesita_facturacion_cto_comp(
	socio_name: str,
	periodo: str,
	concepto: str | None,
) -> bool:
	"""True si hay cargo pendiente y aún no hay SI equivalente en el período."""
	if not es_cuota_complementaria(concepto):
		return False
	if linea_cuota_complementaria_en_periodo(
		socio_name, periodo, concepto, solo_impagas=False
	):
		return False
	return buscar_cargo_pendiente_cuota_complementaria(socio_name, concepto) is not None


def buscar_cargo_socio_cuota_complementaria(
	socio_name: str,
	concepto_informe: str | None,
	*,
	estados: tuple[str, ...] | None = ("Pendiente", "Facturado"),
) -> dict[str, Any] | None:
	"""Cargo recurrente CTO COMP del socio (cualquier estado no cancelado)."""
	if not es_cuota_complementaria(concepto_informe):
		return None
	if not frappe.db.exists("DocType", "Cargo Socio"):
		return None
	filters: dict[str, Any] = {
		"socio": socio_name,
		"modo_cobro": "Recurrente",
		"estado": ["!=", "Cancelado"],
	}
	if estados:
		filters["estado"] = ["in", list(estados)]
	for row in frappe.get_all(
		"Cargo Socio",
		filters=filters,
		fields=["name", "titulo", "monto", "fecha_desde", "fecha_hasta", "item", "estado"],
		order_by="name asc",
	):
		titulo = row.get("titulo") or ""
		if "CTO COMP" not in titulo.upper():
			continue
		if cuotas_complementarias_equivalentes(concepto_informe, titulo):
			return row
	return None


def necesita_alta_cargo_cto_comp(
	socio_name: str,
	periodo: str,
	concepto: str | None,
) -> bool:
	"""True si no hay SI ni cargo equivalente y el informe exige cobrar ese concepto."""
	if not es_cuota_complementaria(concepto):
		return False
	if linea_cuota_complementaria_en_periodo(
		socio_name, periodo, concepto, solo_impagas=False
	):
		return False
	return buscar_cargo_socio_cuota_complementaria(socio_name, concepto) is None

"""Cruce concepto del informe Excel ↔ ítem / línea en Sales Invoice.

Spec: `club_management/specs/informe_concepto_cobranza.md`
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from datetime import date

import frappe
from frappe.utils import flt, getdate

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

# Tarifas patín vigentes en agosto 2026 (septiembre subió ~$5.500; no usar Item Price actual).
TARIFAS_PATIN_AGOSTO_2026: dict[str, float] = {
	"ICDPE-PATIN-MINI": 20500.0,
	"ICDPE-PATIN-TEENS": 20500.0,
	"ICDPE-PATIN-INTERMEDIO": 36000.0,
	"ICDPE-PATIN-AVANZADO": 42000.0,
	"ICDPE-PATIN-DANZA": 29500.0,
	"ICDPE-PATIN-ADULTO": 26500.0,
}

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
	"BOXEO 1 VEZ": ("ICDPE-BOXEO-1-CLASE",),
	"BASQ SUP FEM": ("ICDPE-BASQUET-FEMENINO-SUP",),
	"PATIN INTERMEDIO": ("ICDPE-PATIN-INTERMEDIO",),
	"PATIN ADULTO": ("ICDPE-PATIN-ADULTO",),
	"FUNCIONAL FACU": ("ICDPE-FUNCIONAL-1-CLASE", "ICDPE-FUNCIONAL-2-CLASES"),
	"FUNCIONAL GYM 1 CLASE": ("ICDPE-FUNCIONAL-1-CLASE",),
	"FUNCIONAL CROSFFIT": ("ICDPE-FUNCIONAL-1-CLASE", "ICDPE-FUNCIONAL-2-CLASES"),
	"FUNCIONAL CROSSFIT": ("ICDPE-FUNCIONAL-1-CLASE", "ICDPE-FUNCIONAL-2-CLASES"),
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
	"JUVENILES A U17": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
	"JUVENILES B U17": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",),
	"CADETES A U15": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
	"CADETES B U15": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",),
	"INFANTILES B U13": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"INFA A U13": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"MINI A U11": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"MINI B U11": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"PRE-MINI A U9": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"PRE-MINI B U9": ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
	"LIGA APROX A U21": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
	"LIGA APROX B U21": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",),
	"U13 FLEX": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",),
	"U21 FLEX": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",),
	"BASQUET U19 FLEX": ("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX",),
	# Básquet femenino formativas: los equipos U9–U17 facturan ICDPE-BASQUET-ESCUELITA.
	"PRE MINI U9 FEM": ("ICDPE-BASQUET-ESCUELITA",),
	"MINI U11 FEM": ("ICDPE-BASQUET-ESCUELITA",),
	"INFA U13 FEM": ("ICDPE-BASQUET-ESCUELITA",),
	"CADETE U15 FEM": ("ICDPE-BASQUET-ESCUELITA",),
	"JUVENILES U17 FEM": ("ICDPE-BASQUET-ESCUELITA",),
	"U21 FEM": ("ICDPE-BASQUET-ESCUELITA",),
	# Vóley federado (equipo Superior B en padrón).
	"SUPERIOR B": ("ICDPE-VOLEY-FEDERADO",),
}

_CUOTA_CATEGORIA_KEYWORDS: tuple[tuple[str, str], ...] = (
	("HIJO 3", "3° Hermano"),
	("HIJO 2", "2° Hermano"),
	("3 HERMANO", "3° Hermano"),
	("2 HERMANO", "2° Hermano"),
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


def es_concepto_carnet(concepto: str | None) -> bool:
	"""True si el renglón del informe es CARNET (no se imputa en carga masiva)."""
	norm = normalizar_concepto_informe(concepto)
	return norm == "CARNET" or norm.startswith("CARNET ")


_PERIODO_ORDEN_RE = re.compile(r"^(\d{2})/(\d{4})")


def orden_periodo(periodo: str | None) -> tuple[int, int] | None:
	"""(año, mes) para comparar períodos; ignora sufijo `-MORA`."""
	text = (periodo or "").strip()
	match = _PERIODO_ORDEN_RE.match(text)
	if not match:
		return None
	return int(match.group(2)), int(match.group(1))


def periodo_es_adelantado(periodo: str | None, periodo_cierre: str) -> bool:
	"""True si el período de la fila/SI es posterior al mes de cierre de la corrida."""
	actual = orden_periodo(periodo)
	cierre = orden_periodo(periodo_cierre)
	if not actual or not cierre:
		return False
	return actual > cierre


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
	# º/° se quitan ANTES de NFKD: la descomposición convierte º en «o»
	# y rompía claves como «ADICIONAL PATIN 1º NIVEL».
	text = text.replace("º", " ").replace("°", " ")
	decomposed = unicodedata.normalize("NFKD", text)
	ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
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
	# «JUBILADO CENTRO» = cuota social de jubilado (sin la palabra «cuota» en el informe).
	if concepto_norm.startswith("JUBILADO"):
		return _item_codes_cuota_por_categoria("Jubilado")
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
		# Tira A = Azul / Minibasquet; no mezclar Escuelita (otro equipo).
		return _ARANCEL_EQUIPO_ALIAS[norm]

	if norm.startswith("EXPEDIENTE FEBAMBA") or norm == "FEBAMBA":
		return _INFORME_ITEM_EXACTO["EXPEDIENTE FEBAMBA"]

	if socio_name:
		por_inscripcion = _item_codes_inscripcion_socio(socio_name)
		if len(por_inscripcion) == 1:
			return por_inscripcion

	return ()


_REF_INF_CONCEPTO_RE = re.compile(
	r"INF-\d+-[^-]+-\d{2}/\d{4}-[\d.]+-(.+)$",
	re.I,
)

_REF_INF_FULL_RE = re.compile(
	r"INF-(\d+)-([^-]+)-(\d{2}/\d{4})-([\d.]+)-(.+)$",
	re.I,
)


def parse_referencia_informe(reference_no: str | None) -> dict[str, str | float] | None:
	"""Descompone `INF-fila-socio-MM/YYYY-monto-concepto`."""
	ref = (reference_no or "").strip()
	match = _REF_INF_FULL_RE.search(ref.replace("\n", " "))
	if not match:
		return None
	return {
		"fila": match.group(1),
		"socio_ref": match.group(2),
		"periodo": match.group(3),
		"monto": flt(match.group(4), 2),
		"concepto": (match.group(5) or "").strip(),
	}


def referencia_informe(
	*,
	fila: int | str,
	numero_socio: str,
	periodo: str,
	monto: float,
	concepto: str,
) -> str:
	"""Genera `reference_no` estándar (máx. 140 chars, concepto completo)."""
	concepto_trim = (concepto or "").strip()
	return f"INF-{fila}-{numero_socio}-{periodo}-{flt(monto, 2)}-{concepto_trim}"[:140]


def monto_imputado_concepto_informe_en_rango(
	socio_name: str,
	concepto: str,
	periodo: str,
	*,
	fecha_desde: str,
	fecha_hasta: str,
) -> float:
	"""Suma cobrado en PE (fecha de cobro) con concepto y período del informe."""
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return 0.0
	norm_concepto = normalizar_concepto_informe(concepto)
	periodo_key = (periodo or "").strip()
	item_codes = resolver_item_codes_concepto(concepto)
	rows = frappe.db.sql(
		f"""
		SELECT pe.name, pe.reference_no, pe.paid_amount, per.allocated_amount
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
		INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name
		WHERE pe.docstatus = 1
		  AND pe.posting_date BETWEEN %s AND %s
		  AND si.`{campo_socio}` = %s
		""",
		(getdate(fecha_desde), getdate(fecha_hasta), socio_name),
		as_dict=True,
	)
	total = 0.0
	seen_pe: set[str] = set()
	for row in rows:
		pe_name = row.name
		if pe_name in seen_pe:
			continue
		parsed = parse_referencia_informe(row.reference_no)
		if parsed:
			if parsed["periodo"] != periodo_key:
				continue
			if normalizar_concepto_informe(str(parsed["concepto"])) != norm_concepto:
				continue
			seen_pe.add(pe_name)
			total += flt(row.paid_amount, 2)
			continue
		ref_concepto = concepto_desde_comprobante(row.reference_no)
		if ref_concepto and normalizar_concepto_informe(ref_concepto) == norm_concepto:
			if periodo_key in (row.reference_no or ""):
				seen_pe.add(pe_name)
				total += flt(row.paid_amount, 2)
	if item_codes and total <= 0.005:
		for inv in _facturas_socio_periodo(socio_name, periodo_key, solo_impagas=False):
			total += monto_cobrado_de_items_en_rango(
				inv,
				list(item_codes),
				fecha_desde=fecha_desde,
				fecha_hasta=fecha_hasta,
			)
	return flt(total, 2)


def concepto_desde_comprobante(reference_no: str | None, remarks: str | None = None) -> str:
	"""Extrae el concepto del informe desde `reference_no` INF-… (no remarks de ERPNext)."""
	ref = (reference_no or "").strip()
	if not ref.upper().startswith("INF-"):
		return ""
	match = _REF_INF_CONCEPTO_RE.search(ref.replace("\n", " "))
	if match:
		return (match.group(1) or "").strip()
	return ""


def concepto_informe_desde_pe(reference_no: str | None, remarks: str | None = None) -> str:
	"""Concepto del informe asociado al PE (vacío si no es cobro masivo INF-…)."""
	return concepto_desde_comprobante(reference_no, remarks)


def _pe_en_rango(posting_date: Any, *, pe_desde: date | None, pe_hasta: date | None) -> bool:
	if not pe_desde and not pe_hasta:
		return True
	fecha = getdate(posting_date)
	if pe_desde and fecha < pe_desde:
		return False
	if pe_hasta and fecha > pe_hasta:
		return False
	return True


def _mora_si_vinculadas(invoice_name: str) -> list[str]:
	pattern = f"%Mora al cobro {invoice_name}%"
	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"docstatus": 1, "remarks": ["like", pattern]},
		pluck="name",
	)


def _pe_allocado_en_rango(
	invoice_name: str,
	*,
	pe_desde: date | None,
	pe_hasta: date | None,
) -> float:
	total = 0.0
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": invoice_name,
			"parenttype": "Payment Entry",
		},
		fields=["parent", "allocated_amount"],
	)
	if not refs:
		return 0.0
	pe_names = list({row.parent for row in refs})
	for pe in frappe.get_all(
		"Payment Entry",
		filters={"name": ["in", pe_names], "docstatus": 1},
		fields=["name", "posting_date"],
	):
		if not _pe_en_rango(pe.posting_date, pe_desde=pe_desde, pe_hasta=pe_hasta):
			continue
		for ref in refs:
			if ref.parent == pe.name:
				total += flt(ref.allocated_amount, 2)
	return flt(total, 2)


def _mora_cobrada_en_rango(
	invoice_name: str,
	item_codes: set[str],
	*,
	pe_desde: date | None,
	pe_hasta: date | None,
) -> float:
	"""Parte proporcional del cobro a SI de mora vinculada (sin duplicar mora ya en el PE de arancel)."""
	if not item_codes:
		return 0.0
	lines = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		fields=["item_code", "amount"],
	)
	arancel_base = 0.0
	total_base = 0.0
	for row in lines:
		amt = flt(row.amount, 2)
		if amt <= 0:
			continue
		total_base += amt
		if (row.item_code or "").strip() in item_codes:
			arancel_base += amt
	if arancel_base <= 0 or total_base <= 0:
		return 0.0

	imputado_arancel = 0.0
	for row in _cobros_imputados_por_linea(invoice_name, pe_desde=pe_desde, pe_hasta=pe_hasta):
		if (row.get("item_code") or "").strip() in item_codes:
			imputado_arancel += flt(row.get("imputado"), 2)
	if imputado_arancel > arancel_base + 0.005:
		return 0.0

	share = arancel_base / total_base
	total = 0.0
	for mora_inv in _mora_si_vinculadas(invoice_name):
		total += _pe_allocado_en_rango(mora_inv, pe_desde=pe_desde, pe_hasta=pe_hasta) * share
	return flt(total, 2)


def _cobros_imputados_por_linea(
	invoice_name: str,
	*,
	pe_desde: date | None = None,
	pe_hasta: date | None = None,
) -> list[dict[str, Any]]:
	"""Asigna cada PE a la línea del concepto (cuota ≠ arancel); no prorratea."""
	lines = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		fields=["name", "idx", "item_code", "description", "amount"],
		order_by="idx asc",
	)
	restante = [flt(row.amount, 2) for row in lines]
	imputado_concepto = [0.0] * len(lines)
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": invoice_name,
			"parenttype": "Payment Entry",
		},
		fields=["parent", "allocated_amount"],
	)
	if not refs:
		return [
			{
				"item_code": row.item_code,
				"description": row.description,
				"amount": flt(row.amount, 2),
				"imputado": 0.0,
				"restante": flt(row.amount, 2),
			}
			for row in lines
		]

	pe_names = list({row.parent for row in refs})
	pe_meta = {
		pe.name: pe
		for pe in frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", pe_names], "docstatus": 1},
			fields=["name", "reference_no", "remarks", "posting_date"],
		)
	}
	for ref in refs:
		pe = pe_meta.get(ref.parent)
		if not pe:
			continue
		if not _pe_en_rango(pe.posting_date, pe_desde=pe_desde, pe_hasta=pe_hasta):
			continue
		take = flt(ref.allocated_amount, 2)
		if take <= 0.005:
			continue
		concepto = concepto_desde_comprobante(pe.reference_no, pe.remarks)
		if es_cuota_complementaria(concepto):
			for idx, row in enumerate(lines):
				if take <= 0.005:
					break
				if not cuotas_complementarias_equivalentes(concepto, row.get("description")):
					continue
				use = min(restante[idx], take)
				if use <= 0.005:
					continue
				restante[idx] = flt(restante[idx] - use, 2)
				imputado_concepto[idx] = flt(imputado_concepto[idx] + use, 2)
				take = flt(take - use, 2)
			for idx, _row in enumerate(lines):
				if take <= 0.005:
					break
				use = min(restante[idx], take)
				if use <= 0.005:
					continue
				restante[idx] = flt(restante[idx] - use, 2)
				take = flt(take - use, 2)
			continue
		codes = resolver_item_codes_concepto(concepto) if concepto else ()
		if codes:
			matched: list[int] = []
			for idx, row in enumerate(lines):
				if take <= 0.005:
					break
				if (row.item_code or "").strip() not in codes:
					continue
				matched.append(idx)
				use = min(restante[idx], take)
				if use <= 0.005:
					continue
				restante[idx] = flt(restante[idx] - use, 2)
				imputado_concepto[idx] = flt(imputado_concepto[idx] + use, 2)
				take = flt(take - use, 2)
			# Mora / excedente del cobro imputado al mismo concepto (liquidación entrenadores).
			if take > 0.005 and matched:
				target = matched[-1]
				imputado_concepto[target] = flt(imputado_concepto[target] + take, 2)
				take = 0.0
			continue
		for idx, _row in enumerate(lines):
			if take <= 0.005:
				break
			use = min(restante[idx], take)
			if use <= 0.005:
				continue
			restante[idx] = flt(restante[idx] - use, 2)
			imputado_concepto[idx] = flt(imputado_concepto[idx] + use, 2)
			take = flt(take - use, 2)

	out: list[dict[str, Any]] = []
	for idx, (row, rest) in enumerate(zip(lines, restante, strict=True)):
		monto = flt(row.amount, 2)
		out.append(
			{
				"item_code": row.item_code,
				"description": row.description,
				"amount": monto,
				"imputado": flt(imputado_concepto[idx], 2),
				"restante": rest,
			}
		)
	return out


def monto_cobrado_de_items(invoice_name: str, item_codes: list[str] | tuple[str, ...]) -> float:
	"""Suma imputada a esos ítems según concepto del PE (0 si el cobro fue cuota)."""
	return monto_cobrado_de_items_en_rango(invoice_name, item_codes)


def monto_cobrado_de_items_en_rango(
	invoice_name: str,
	item_codes: list[str] | tuple[str, ...],
	*,
	fecha_desde: str | date | None = None,
	fecha_hasta: str | date | None = None,
) -> float:
	"""Imputación a ítems en rango de fechas de PE (+ mora vinculada)."""
	wanted = {str(code).strip() for code in (item_codes or []) if str(code).strip()}
	if not wanted:
		return 0.0
	pe_desde = getdate(fecha_desde) if fecha_desde else None
	pe_hasta = getdate(fecha_hasta) if fecha_hasta else None
	total = 0.0
	for row in _cobros_imputados_por_linea(invoice_name, pe_desde=pe_desde, pe_hasta=pe_hasta):
		if (row.get("item_code") or "").strip() in wanted:
			total += flt(row.get("imputado"), 2)
	total += _mora_cobrada_en_rango(invoice_name, wanted, pe_desde=pe_desde, pe_hasta=pe_hasta)
	return flt(total, 2)


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


def _es_concepto_arancel_equipo(concepto: str | None) -> bool:
	norm = normalizar_concepto_informe(concepto)
	if not norm or es_cuota_complementaria(norm):
		return False
	if "FED" in norm or "FEDER" in norm:
		return False
	if "CUOTA SOCIAL" in norm:
		return False
	if norm in _ARANCEL_EQUIPO_ALIAS:
		return True
	return bool(
		re.search(
			r"(PRE-?MINI|MINI [AB]|INFANTIL|INFA |CADETE|JUVENIL|LIGA APROX)",
			norm,
			re.I,
		)
	)


def buscar_linea_factura_concepto(
	socio_name: str,
	periodo: str,
	concepto: str | None,
	*,
	monto_abonado: float = 0.0,
	reservadas: set[str] | None = None,
	solo_impagas: bool = True,
) -> tuple[str, str, float] | None:
	"""Encuentra `(invoice_name, item_code, monto_linea)` para el concepto."""
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
			solo_impagas=solo_impagas,
			reservadas=reservadas,
		)
		if match:
			return match

	invoices = _facturas_socio_periodo(socio_name, periodo, solo_impagas=solo_impagas)

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

	if norm:
		concept_es_fed = bool(re.search(r"\b(C\.?\s*FED|FEDERATIV)", norm))
		for invoice_name in invoices:
			if invoice_name in reservadas:
				continue
			for line in _lineas_factura(invoice_name):
				desc = normalizar_concepto_informe(line.get("description"))
				if not desc:
					continue
				# Evitar que «FUTBOL FAFI» matchee «CTO COMP FUTBOL FAFI/TABI».
				line_es_cto = "CTO COMP" in desc or (line.get("item_code") or "").strip() == ITEM_CUOTA_COMPLEMENTARIA
				if line_es_cto and not es_cto_comp:
					continue
				if es_cto_comp and not line_es_cto:
					continue
				# Evitar que «U13 FLEX» matchee «C FED U13 FLEX».
				line_es_fed = bool(re.search(r"\b(C\.?\s*FED|FEDERATIV)", desc)) or (
					"FEDERATIVA" in ((line.get("item_code") or "").upper())
				)
				if line_es_fed != concept_es_fed:
					continue
				if norm in desc or desc in norm:
					code = (line.get("item_code") or "").strip()
					return invoice_name, code, flt(line.get("amount"))

	if _es_concepto_arancel_equipo(concepto):
		candidatas: list[tuple[str, dict[str, Any]]] = []
		for invoice_name in invoices:
			if invoice_name in reservadas:
				continue
			for line in _lineas_factura(invoice_name):
				desc = normalizar_concepto_informe(line.get("description"))
				code = (line.get("item_code") or "").strip()
				if desc == "ARANCEL ACTIVIDAD" or code.startswith("ICDPE-BASQUET"):
					candidatas.append((invoice_name, line))
		if candidatas:
			if monto_abonado:
				candidatas.sort(key=lambda row: abs(flt(row[1].get("amount")) - flt(monto_abonado)))
			inv, line = candidatas[0]
			amt = flt(line.get("amount"))
			if not monto_abonado or abs(amt - flt(monto_abonado)) <= 501.0:
				code = (line.get("item_code") or "").strip()
				return inv, code, amt

	return None


def concepto_linea_saldada_en_periodo(
	socio_name: str,
	periodo: str,
	concepto: str | None,
	*,
	monto_abonado: float = 0.0,
) -> bool:
	"""True si el concepto ya está en una SI del período con outstanding 0."""
	match = buscar_linea_factura_concepto(
		socio_name,
		periodo,
		concepto,
		monto_abonado=monto_abonado,
		reservadas=set(),
		solo_impagas=False,
	)
	if not match:
		return False
	outstanding = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, match[0], "outstanding_amount"))
	return outstanding <= 0.005


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

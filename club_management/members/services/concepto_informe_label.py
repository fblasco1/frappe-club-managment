"""Etiqueta de concepto del informe de cobranza desde una línea de Sales Invoice.

Mapeo inverso de `informe_concepto_cobranza.py` para reportes Desk (rendición).

Spec: `club_management/specs/informe_rendicion_cobranza_secretaria.md`
"""

from __future__ import annotations

import re
from typing import Any

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.scripts.informe_concepto_cobranza import (
	_INFORME_ITEM_EXACTO,
	_PERIODO_EN_TEXTO_RE,
	es_cuota_complementaria,
	normalizar_clave_cuota_complementaria,
	normalizar_concepto_informe,
)

_FEDERATIVA_ITEM_LABELS: dict[str, str] = {
	"ICDPE-CUOTA-FEDERATIVA-voley": "CUOTA FEDER VOLEY",
	"ICDPE-CUOTA-FEDERATIVA-basquet-masculino": "C FED BASQUET MASC",
	"ICDPE-CUOTA-FEDERATIVA-basquet-femenino": "C FED BASQUET FEM",
}

_CATEGORIA_CUOTA_INFORME: dict[str, str] = {
	"Activo": "Activo",
	"Menor": "Menor",
	"2° Hermano": "Menor",
	"3° Hermano": "Menor",
	"Menor Hijo 2": "Menor",
	"Adherente": "Adherente",
	"Jubilado": "Jubilado",
	"Vitalicio": "Vitalicio",
}

_CUOTA_DESCRIPCION_RE = re.compile(
	r"cuota\s+social\s+(activo|menor|adherente|jubilado|vitalicio)",
	re.I,
)


def _display_label_from_map_key(key: str) -> str:
	upper = key.upper()
	if upper.startswith(("CUOTA FED", "C FED", "CTO COMP", "EXPEDIENTE")):
		return upper
	if key == upper:
		return key
	return key.title()


def _item_code_to_informe_label() -> dict[str, str]:
	out: dict[str, str] = dict(_FEDERATIVA_ITEM_LABELS)
	for raw_label, codes in _INFORME_ITEM_EXACTO.items():
		display = _display_label_from_map_key(raw_label)
		for code in codes:
			out.setdefault(code, display)
	return out


_ITEM_INFORME_LABEL = _item_code_to_informe_label()


def _etiqueta_cuota_social(
	item_code: str | None,
	description: str | None,
	*,
	categoria_socio: str | None,
) -> str | None:
	text = (description or "").strip()
	match = _CUOTA_DESCRIPCION_RE.search(text)
	if match:
		cat = match.group(1).title()
		if cat.lower() == "menor":
			return "Cuota Social Menor"
		return f"Cuota Social {cat}"

	if categoria_socio:
		cat = _CATEGORIA_CUOTA_INFORME.get(categoria_socio.strip(), categoria_socio.strip())
		return f"Cuota Social {cat}"

	code = (item_code or "").strip()
	if code and code == CUOTA_SOCIAL_ITEM_CODE:
		return "Cuota Social"

	norm = normalizar_concepto_informe(text)
	if "CUOTA SOCIAL" in norm or norm.startswith("CARNET"):
		for keyword, categoria in (
			("JUBILADO", "Jubilado"),
			("ADHERENTE", "Adherente"),
			("MENOR", "Menor"),
			("ACTIVO", "Activo"),
			("VITALICIO", "Vitalicio"),
		):
			if keyword in norm:
				return f"Cuota Social {categoria}"
	return None


def _etiqueta_cto_comp(description: str | None) -> str | None:
	text = (description or "").strip()
	if not text:
		return None
	if not es_cuota_complementaria(text):
		return None
	clave = normalizar_clave_cuota_complementaria(text)
	return clave or None


def _etiqueta_federativa_desde_descripcion(description: str | None) -> str | None:
	text = (description or "").strip()
	if not text:
		return None
	norm = normalizar_concepto_informe(text)
	if not (norm.startswith("C FED") or norm.startswith("C.FED") or "CUOTA FEDER" in norm):
		return None
	clean = _PERIODO_EN_TEXTO_RE.sub("", text).strip()
	return clean.upper() if clean else None


def _fallback_descripcion(description: str | None, *, max_len: int = 140) -> str | None:
	text = re.sub(r"\s+", " ", (description or "").strip())
	if not text:
		return None
	text = _PERIODO_EN_TEXTO_RE.sub("", text).strip()
	if not text:
		return None
	return text[:max_len]


def etiqueta_concepto_informe_desde_linea_si(
	item_code: str | None,
	description: str | None,
	*,
	categoria_socio: str | None = None,
) -> str:
	"""Devuelve la etiqueta del informe manual para una línea de factura."""
	code = (item_code or "").strip()

	cto = _etiqueta_cto_comp(description)
	if cto:
		return cto

	cuota = _etiqueta_cuota_social(code, description, categoria_socio=categoria_socio)
	if cuota:
		return cuota

	fed_desc = _etiqueta_federativa_desde_descripcion(description)
	if fed_desc:
		return fed_desc

	if code in _ITEM_INFORME_LABEL:
		return _ITEM_INFORME_LABEL[code]

	fallback = _fallback_descripcion(description)
	if fallback:
		return fallback

	if code:
		return _ITEM_INFORME_LABEL.get(code, code)

	return "Concepto"


def agrupacion_tipo_concepto(etiqueta: str | None) -> str:
	"""Agrupa la etiqueta informe para filtros del reporte de rendición."""
	text = normalizar_concepto_informe(etiqueta)
	if not text:
		return "Otro"
	if text.startswith("CTO COMP"):
		return "CTO COMP"
	if "CUOTA SOCIAL" in text or text.startswith("CARNET"):
		return "Cuota"
	if text.startswith("CUOTA FED") or text.startswith("C FED") or "FEDER" in text:
		return "Federativa"
	if text.startswith("EXPEDIENTE") or "FEBAMBA" in text:
		return "Otro"
	if text.startswith("ADICIONAL") or text.startswith("ARANCEL") or "BOXEO" in text:
		return "Arancel"
	return "Otro"


def etiquetas_desde_lineas_factura(
	lineas: list[dict[str, Any]],
	*,
	categoria_socio: str | None = None,
) -> list[str]:
	"""Conveniencia para mapear varias líneas SI."""
	return [
		etiqueta_concepto_informe_desde_linea_si(
			row.get("item_code"),
			row.get("description"),
			categoria_socio=categoria_socio,
		)
		for row in lineas
	]

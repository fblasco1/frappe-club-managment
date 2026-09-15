"""Parseo del informe de cobranzas ICDPE (Excel agrupado por concepto)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from frappe.utils import flt

from club_management.scripts.bulk_io import parse_fecha

_MESES: dict[str, int] = {
	"ENERO": 1,
	"FEBRERO": 2,
	"MARZO": 3,
	"ABRIL": 4,
	"MAYO": 5,
	"JUNIO": 6,
	"JULIO": 7,
	"AGOSTO": 8,
	"SEPTIEMBRE": 9,
	"SEPTIEMRBE": 9,
	"OCTUBRE": 10,
	"NOVIEMBRE": 11,
	"DICIEMBRE": 12,
}


def parse_periodo_informe(raw: str | None, *, fecha: date | None = None) -> str | None:
	"""Convierte `JULIO 2026` / `AGOSTO 26` / `AGOSTO` a `MM/YYYY`."""
	text = re.sub(r"\s+", " ", (raw or "").strip().upper())
	if not text:
		return None
	year: int | None = None
	month: int | None = None
	m_year = re.search(r"(20\d{2})\b", text)
	if m_year:
		year = int(m_year.group(1))
	else:
		m_yy = re.search(r"\b(\d{2})\b", text)
		if m_yy:
			year = 2000 + int(m_yy.group(1))
	for name, num in _MESES.items():
		if name in text:
			month = num
			break
	if month is None:
		return None
	if year is None:
		year = fecha.year if fecha else date.today().year
	return f"{month:02d}/{year}"


def map_medio_nota(nota: str | None) -> str:
	text = (nota or "").strip().lower()
	if re.search(r"tra", text):
		return "Transferencia"
	return "Efectivo"


def is_informe_cobranzas_header(first_cell: Any) -> bool:
	return "INFORME DE COBRANZAS" in str(first_cell or "").upper()


def pagos_from_informe_rows(rows: list[tuple[Any, ...]]) -> list[dict[str, str]]:
	"""Filas de pago normalizadas para `bulk_payments.run`."""
	concepto = ""
	out: list[dict[str, str]] = []
	for idx, raw in enumerate(rows, start=1):
		vals = list(raw) + [None] * 9
		a = vals[0]
		if isinstance(a, str) and a.upper().startswith("CONCEPTO:"):
			concepto = a.split(":", 1)[1].strip()
			continue
		if a == "Fecha" or isinstance(a, str) and a.startswith("Subtotales"):
			continue
		if isinstance(a, str) and a.startswith("Totales"):
			continue
		fecha_val = a
		if not isinstance(fecha_val, (datetime, date)):
			# fila sin fecha (a veces el nro de socio está en col 1)
			if vals[1] is not None and vals[4] is not None and not isinstance(a, str):
				fecha_val = None
			else:
				continue
		fecha = None
		if isinstance(fecha_val, datetime):
			fecha = fecha_val.date()
		elif isinstance(fecha_val, date):
			fecha = fecha_val
		nro = vals[1]
		if nro is None:
			continue
		periodo_raw = vals[3]
		importe = vals[4]
		nota = vals[8]
		fecha_dt = fecha
		periodo = parse_periodo_informe(str(periodo_raw) if periodo_raw is not None else "", fecha=fecha_dt)
		ref = f"INF-{idx}-{nro}-{periodo or 'NA'}-{flt(importe)}-{concepto[:24]}"
		out.append(
			{
				"nro_socio": str(int(nro)) if isinstance(nro, (int, float)) else str(nro).strip(),
				"monto_abonado": str(importe or ""),
				"fecha_pago": fecha.isoformat() if fecha else "",
				"medio_pago": map_medio_nota(str(nota) if nota is not None else ""),
				"referencia_comprobante": ref[:140],
				"periodo": periodo or "",
				"concepto": concepto,
			}
		)
	return out

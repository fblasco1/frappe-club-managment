"""Alinea pe_monto_distinto: INF (base) + PE mora del mismo cobro = CSV.

Spec: `club_management/specs/conciliacion_migracion_agosto.md`

- Cuota/arancel: si PE mora cubre el gap → bucket `ok` (alineado).
- C FED / CTO COMP: no aplican mora; se consolidan si hubo split erróneo.
- Outliers manuales: BOXEO 12275, PATIN 8770, CTO COMP VOLEY 12235.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
)
from club_management.members.services.mora_al_cobro import periodo_es_ajuste_mora
from club_management.scripts.bulk_io import CONFIRM_LOCAL, is_production_site
from club_management.scripts.informe_concepto_cobranza import (
	es_cuota_complementaria,
	normalizar_concepto_informe,
)
from club_management.scripts.purge_historical_data_pre_september import CONFIRM_PURGE_PROD

OUTLIERS_MANUAL: frozenset[tuple[str, str, str]] = frozenset(
	{
		("12275", "08/2026", "BOXEO"),
		("8770", "08/2026", "PATIN INTERMEDIO"),
		("12235", "08/2026", "CTO COMP VOLEY ESC"),
	}
)

# Cierre de outliers (04/09/2026): ya no son pendientes de Desk.
RESOLUCION_OUTLIER: dict[tuple[str, str, str], str] = {
	("12275", "08/2026", "BOXEO"): "resuelto_manual",
	("8770", "08/2026", "PATIN INTERMEDIO"): "ignorado_error_cobrador",
	("12235", "08/2026", "CTO COMP VOLEY ESC"): "liquidado_a_4000",
}

TOL = 1.0


def concepto_exento_mora(concepto: str) -> bool:
	"""Federativas y CTO COMP no aplican mora."""
	if es_cuota_complementaria(concepto):
		return True
	n = normalizar_concepto_informe(concepto)
	return (
		n.startswith("C FED")
		or n.startswith("CUOTA FEDER")
		or "FEDERATIVA" in n
	)


def _clave_outlier(nro: str, periodo: str, concepto: str) -> tuple[str, str, str] | None:
	clave = ((nro or "").strip(), (periodo or "").strip(), (concepto or "").strip())
	if clave in OUTLIERS_MANUAL:
		return clave
	nro_s = (nro or "").strip()
	per = (periodo or "").strip()
	c = (concepto or "").upper()
	if nro_s == "12275" and per == "08/2026" and "BOXEO" in c:
		return ("12275", "08/2026", "BOXEO")
	if nro_s == "8770" and per == "08/2026" and "PATIN INTERMEDIO" in c:
		return ("8770", "08/2026", "PATIN INTERMEDIO")
	if nro_s == "12235" and per == "08/2026" and "CTO COMP" in c:
		return ("12235", "08/2026", "CTO COMP VOLEY ESC")
	return None


def es_outlier_manual(nro: str, periodo: str, concepto: str) -> bool:
	"""True si la fila fue outlier histórico (aunque ya esté resuelto)."""
	return _clave_outlier(nro, periodo, concepto) is not None


def resolucion_outlier(nro: str, periodo: str, concepto: str) -> str | None:
	"""Código de cierre del outlier, o None si no aplica / sigue pendiente."""
	clave = _clave_outlier(nro, periodo, concepto)
	if not clave:
		return None
	return RESOLUCION_OUTLIER.get(clave)


def outlier_pendiente(nro: str, periodo: str, concepto: str) -> bool:
	"""True solo si aún requiere acción de Desk."""
	return es_outlier_manual(nro, periodo, concepto) and not resolucion_outlier(
		nro, periodo, concepto
	)


def _si_es_mora(invoice_name: str) -> bool:
	si = frappe.db.get_value(
		SALES_INVOICE_DOCTYPE,
		invoice_name,
		["periodo_cobro", "remarks"],
		as_dict=True,
	)
	if not si:
		return False
	return periodo_es_ajuste_mora(si.periodo_cobro) or (si.remarks or "").startswith(
		"Mora al cobro"
	)


def _origen_mora(invoice_name: str) -> str:
	remarks = frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "remarks") or ""
	if not remarks.startswith("Mora al cobro"):
		return ""
	return remarks.replace("Mora al cobro", "", 1).strip()


def base_invoices_de_pe(pe_name: str) -> list[str]:
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={"parent": pe_name, "reference_doctype": SALES_INVOICE_DOCTYPE},
		pluck="reference_name",
	)
	return [r for r in refs if r and not _si_es_mora(r)]


def pes_mora_contra_origenes(origenes: list[str]) -> list[dict[str, Any]]:
	"""PE submitted que pagan SI mora cuyo origen está en `origenes`."""
	if not origenes:
		return []
	out: list[dict[str, Any]] = []
	seen: set[str] = set()
	for origen in origenes:
		mora_sis = frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={"docstatus": 1, "remarks": ["like", f"%Mora al cobro {origen}%"]},
			pluck="name",
		)
		# también periodo *-MORA vinculadas por remarks exacto
		for mora in mora_sis:
			links = frappe.get_all(
				"Payment Entry Reference",
				filters={
					"reference_doctype": SALES_INVOICE_DOCTYPE,
					"reference_name": mora,
					"parenttype": "Payment Entry",
				},
				fields=["parent", "allocated_amount"],
			)
			for link in links:
				pe = link.parent
				if pe in seen:
					continue
				if frappe.db.get_value("Payment Entry", pe, "docstatus") != 1:
					continue
				seen.add(pe)
				paid = flt(frappe.db.get_value("Payment Entry", pe, "paid_amount"))
				out.append(
					{
						"pe": pe,
						"paid_amount": paid,
						"allocated": flt(link.allocated_amount),
						"mora_si": mora,
						"origen": origen,
					}
				)
	return out


def cobertura_mora_de_pe_inf(pe_inf: str, gap: float) -> dict[str, Any]:
	"""Suma PE mora ligados al origen del INF; indica si cubren el gap."""
	bases = base_invoices_de_pe(pe_inf)
	moras = pes_mora_contra_origenes(bases)
	suma = flt(sum(flt(m["paid_amount"]) for m in moras), 2)
	# Preferir match exacto de un PE ≈ gap
	match_gap = [m for m in moras if abs(flt(m["paid_amount"]) - gap) <= TOL]
	if match_gap:
		suma_match = flt(sum(flt(m["paid_amount"]) for m in match_gap), 2)
		return {
			"bases": bases,
			"mora_pes": match_gap,
			"suma_mora": suma_match,
			"cubre": abs(suma_match - gap) <= TOL,
		}
	if abs(suma - gap) <= TOL:
		return {
			"bases": bases,
			"mora_pes": moras,
			"suma_mora": suma,
			"cubre": True,
		}

	# Fallback: PE del mismo día/cliente con monto ≈ gap (split indebido C FED / CTO, etc.)
	pe_meta = frappe.db.get_value(
		"Payment Entry", pe_inf, ["party", "posting_date"], as_dict=True
	)
	extra: list[dict[str, Any]] = []
	if pe_meta and pe_meta.party and abs(gap) > TOL:
		candidatos = frappe.get_all(
			"Payment Entry",
			filters={
				"party": pe_meta.party,
				"posting_date": pe_meta.posting_date,
				"docstatus": 1,
			},
			fields=["name", "paid_amount", "reference_no"],
		)
		for p in candidatos:
			if p.name == pe_inf:
				continue
			if abs(flt(p.paid_amount) - gap) <= TOL:
				extra.append(
					{
						"pe": p.name,
						"paid_amount": flt(p.paid_amount),
						"allocated": flt(p.paid_amount),
						"mora_si": "",
						"origen": "",
					}
				)
		if extra:
			suma_extra = flt(sum(flt(m["paid_amount"]) for m in extra), 2)
			return {
				"bases": bases,
				"mora_pes": extra,
				"suma_mora": suma_extra,
				"cubre": abs(suma_extra - gap) <= TOL,
			}

	return {
		"bases": bases,
		"mora_pes": moras,
		"suma_mora": suma,
		"cubre": False,
	}


def clasificar_gap_fila(
	*,
	nro_socio: str,
	periodo: str,
	concepto: str,
	monto_csv: float,
	paid_inf: float,
	gap: float,
	pe_inf: str,
) -> dict[str, Any]:
	row: dict[str, Any] = {
		"nro_socio": nro_socio,
		"periodo": periodo,
		"concepto": concepto,
		"monto_csv": monto_csv,
		"paid_inf": paid_inf,
		"gap": gap,
		"pe_inf": pe_inf,
		"exento_mora": concepto_exento_mora(concepto),
		"estado": "",
		"suma_mora": 0.0,
		"pe_mora": "",
		"paid_alineado": paid_inf,
	}
	if es_outlier_manual(nro_socio, periodo, concepto):
		row["estado"] = "outlier_manual"
		return row

	cov = cobertura_mora_de_pe_inf(pe_inf, gap)
	row["suma_mora"] = cov["suma_mora"]
	row["pe_mora"] = ";".join(m["pe"] for m in cov["mora_pes"])
	row["paid_alineado"] = flt(paid_inf + cov["suma_mora"], 2)

	if abs(flt(row["paid_alineado"]) - monto_csv) <= TOL or cov["cubre"]:
		if row["exento_mora"]:
			row["estado"] = "alineado_exento_con_split_indebido"
		else:
			row["estado"] = "alineado_con_pe_mora"
		return row

	row["estado"] = "sin_cobertura"
	return row


def alinear_filas_diferencias(
	csv_path: str,
	*,
	out_dir: str = "/tmp/alineacion_pe_monto_distinto",
) -> dict[str, Any]:
	"""Clasifica las 414 diferencias; escribe outliers + alineadas."""
	path = Path(csv_path)
	rows_in = list(csv.DictReader(path.open(encoding="utf-8")))
	clasificadas: list[dict[str, Any]] = []
	for r in rows_in:
		clasificadas.append(
			clasificar_gap_fila(
				nro_socio=r["nro_socio"],
				periodo=r["periodo"],
				concepto=r["concepto"],
				monto_csv=flt(r["monto_csv"]),
				paid_inf=flt(r["paid_amount"]),
				gap=flt(r["gap"]),
				pe_inf=r["pe"],
			)
			| {
				"socio": r.get("socio") or "",
				"fecha_pago": r.get("fecha_pago") or "",
				"clase": r.get("clase") or "",
			}
		)

	from collections import Counter

	conteo = Counter(c["estado"] for c in clasificadas)
	outliers = [c for c in clasificadas if c["estado"] == "outlier_manual"]
	alineadas = [c for c in clasificadas if c["estado"].startswith("alineado")]
	resto = [c for c in clasificadas if c["estado"] == "sin_cobertura"]

	destino = Path(out_dir)
	destino.mkdir(parents=True, exist_ok=True)

	def _write(name: str, data: list[dict[str, Any]]) -> str:
		fp = destino / name
		if not data:
			fp.write_text("", encoding="utf-8")
			return str(fp)
		fields = list(data[0].keys())
		with fp.open("w", encoding="utf-8", newline="") as handle:
			w = csv.DictWriter(handle, fieldnames=fields)
			w.writeheader()
			w.writerows(data)
		return str(fp)

	paths = {
		"outliers": _write("outliers_manual.csv", outliers),
		"alineadas": _write("alineadas_con_pe_mora.csv", alineadas),
		"sin_cobertura": _write("sin_cobertura.csv", resto),
	}
	resumen = {
		"filas": len(clasificadas),
		"conteo": dict(conteo),
		"outliers_count": len(outliers),
		"alineadas_count": len(alineadas),
		"sin_cobertura_count": len(resto),
		"paths": paths,
		"regla": "C FED y CTO COMP no aplican mora; cuota/arancel alinean con PE mora del origen",
		"outliers_definidos": [list(x) for x in sorted(OUTLIERS_MANUAL)],
	}
	(destino / "resumen.json").write_text(
		json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
	)
	print(json.dumps(resumen, indent=2, ensure_ascii=False))
	return resumen


def run_prod_clasificar() -> dict[str, Any]:
	return alinear_filas_diferencias(
		"/tmp/diferencias_monto_csv_vs_pe.csv",
		out_dir="/tmp/alineacion_pe_monto_distinto",
	)

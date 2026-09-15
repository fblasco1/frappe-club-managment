from __future__ import annotations
import frappe
from frappe.utils import flt

def run():
	from club_management.members.services.liquidacion_equipo import get_pagos_por_equipo_data
	from club_management.activities.data.basquet_aranceles_icdpe import (
		expand_arancel_item_codes_for_pagos,
		ITEM_MASCULINO_SUPERIOR_AMARILLO,
	)
	from club_management.scripts.informe_concepto_cobranza import resolver_item_codes_concepto

	equipo = "Basquet / Masculino / Amarillo / SUPERIOR"
	item_eq = frappe.db.get_value("Equipo Actividad", equipo, "item")
	expanded = sorted(expand_arancel_item_codes_for_pagos(item_eq))
	mapping = resolver_item_codes_concepto("SUPERIOR B")
	socios = frappe.get_all(
		"Inscripcion Actividad",
		filters={"equipo_actividad": equipo, "estado": "Activa"},
		pluck="socio",
	)
	nombres = {
		s: frappe.db.get_value("Socio", s, ["nombre", "apellido"], as_dict=True) for s in socios
	}
	lines = []
	pe = []
	if socios:
		lines = frappe.db.sql(
			"""
			SELECT si.socio, si.name, si.periodo_cobro, sii.item_code, sii.amount
			FROM `tabSales Invoice Item` sii
			INNER JOIN `tabSales Invoice` si ON si.name=sii.parent AND si.docstatus=1
			WHERE si.socio IN %s
			  AND sii.item_code IN %s
			ORDER BY si.socio, si.periodo_cobro
			""",
			(
				tuple(socios),
				tuple(sorted(set(expanded + ["ICDPE-VOLEY-FEDERADO", ITEM_MASCULINO_SUPERIOR_AMARILLO]))),
			),
			as_dict=True,
		)
		pe = frappe.db.sql(
			"""
			SELECT pe.name, pe.posting_date, pe.reference_no, pe.paid_amount, si.socio, sii.item_code
			FROM `tabPayment Entry` pe
			INNER JOIN `tabPayment Entry Reference` per ON per.parent=pe.name
			INNER JOIN `tabSales Invoice` si ON si.name=per.reference_name
			INNER JOIN `tabSales Invoice Item` sii ON sii.parent=si.name
			WHERE pe.docstatus=1 AND pe.posting_date BETWEEN '2026-08-01' AND '2026-08-31'
			  AND si.socio IN %s
			  AND (sii.item_code=%s OR sii.item_code=%s OR pe.reference_no ILIKE %s)
			ORDER BY si.socio, pe.posting_date
			""",
			(tuple(socios), ITEM_MASCULINO_SUPERIOR_AMARILLO, "ICDPE-VOLEY-FEDERADO", "%SUPERIOR B%"),
			as_dict=True,
		)

	def pack(data):
		return [
			{
				"socio": r["socio"],
				"nombre": r["nombre_apellido"],
				"pagos": r["pagos_en_rango"],
				"cant": r["cantidad_pagos"],
				"periodos": r.get("periodos_cobrados"),
			}
			for r in data
		]

	data = get_pagos_por_equipo_data(
		{"equipo_actividad": equipo, "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-31"}
	)
	data_sept = get_pagos_por_equipo_data(
		{"equipo_actividad": equipo, "fecha_desde": "2026-09-01", "fecha_hasta": "2026-09-30"}
	)
	return {
		"item_eq": item_eq,
		"expanded": expanded,
		"mapping_superior_b": mapping,
		"socios_activos": socios,
		"nombres": nombres,
		"si_lines": lines,
		"pe_aug": pe,
		"pagos_ago": pack(data),
		"pagos_sept": pack(data_sept),
		"totals": {
			"ago": flt(sum(flt(r["pagos_en_rango"]) for r in data), 2),
			"sept": flt(sum(flt(r["pagos_en_rango"]) for r in data_sept), 2),
		},
	}

"""Simula query_report Desk + permisos."""
from __future__ import annotations
import frappe
from frappe.utils import flt

def run():
	from club_management.members.services.liquidacion_equipo import get_pagos_por_equipo_data

	equipo = "Basquet / Masculino / Amarillo / SUPERIOR"
	filters_ago = {
		"actividad": "Basquet",
		"grupo_actividad": "Basquet / Masculino / Amarillo",
		"equipo_actividad": equipo,
		"fecha_desde": "2026-08-01",
		"fecha_hasta": "2026-08-31",
	}
	filters_default = {
		"equipo_actividad": equipo,
		"fecha_desde": "2026-09-01",
		"fecha_hasta": "2026-09-04",
	}
	# as Administrator
	admin = get_pagos_por_equipo_data(filters_ago)
	# Desk path
	desk = frappe.desk.query_report.run(
		"Pagos por equipo",
		filters=filters_ago,
		user=frappe.session.user,
	)
	# User Permission on Socio?
	up = frappe.get_all(
		"User Permission",
		filters={"allow": "Socio"},
		fields=["user", "for_value", "apply_to_all_doctypes"],
		limit=20,
	)
	# Secretaria users
	secs = frappe.db.sql(
		"""
		SELECT DISTINCT parent FROM `tabHas Role`
		WHERE role='Secretaria' AND parenttype='User'
		LIMIT 10
		""",
		pluck=True,
	)
	as_sec = {}
	for u in secs[:3]:
		frappe.set_user(u)
		try:
			rows = get_pagos_por_equipo_data(filters_ago)
			as_sec[u] = {
				"filas": len(rows),
				"total": flt(sum(flt(r["pagos_en_rango"]) for r in rows), 2),
				"socios": [r["socio"] for r in rows],
			}
		except Exception as e:
			as_sec[u] = {"error": f"{type(e).__name__}: {e}"}
		finally:
			frappe.set_user("Administrator")

	return {
		"admin_ago_filas": len(admin),
		"admin_ago_total": flt(sum(flt(r["pagos_en_rango"]) for r in admin), 2),
		"admin_ago_socios": [(r["socio"], r["nombre_apellido"], r["pagos_en_rango"]) for r in admin],
		"desk_result_keys": list(desk.keys()) if isinstance(desk, dict) else type(desk).__name__,
		"desk_result_len": len(desk.get("result") or []) if isinstance(desk, dict) else None,
		"desk_prepared": desk.get("prepared_report") if isinstance(desk, dict) else None,
		"desk_sample": (desk.get("result") or [])[:8] if isinstance(desk, dict) else None,
		"default_sept_filas": len(get_pagos_por_equipo_data(filters_default)),
		"user_permissions_socio_sample": up,
		"as_secretaria": as_sec,
	}

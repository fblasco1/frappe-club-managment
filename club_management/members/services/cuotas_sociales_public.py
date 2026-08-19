"""Valores de cuota social para la web pública (sin datos internos)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import getdate

from club_management.members.services.secretaria_workspace_panel import CUOTAS_CATEGORIAS

CONDICIONES_PUBLICAS: dict[str, str] = {
	"Activo": "Mayores de 18 años",
	"Menor": "Hasta 17 años inclusive",
	"2° Hermano": "Descuento 2.º integrante del grupo familiar",
	"3° Hermano": "Descuento 3.er integrante del grupo familiar",
	"Adherente": "Categoría adherente (disciplinas habilitadas)",
	"Jubilado": "Con comprobante de haberes",
}


def get_valores_cuota_publica_payload() -> dict[str, Any]:
	"""Montos vigentes para `/socios/cuota`. Sin ítems ERPNext ni PII."""
	rows = frappe.get_all(
		"Cuota Categoria Club",
		filters={"parenttype": "Club Settings", "parent": "Club Settings"},
		fields=["categoria", "monto"],
		ignore_permissions=True,
	)
	by_categoria = {row["categoria"]: float(row["monto"] or 0) for row in rows}

	categorias: list[dict[str, Any]] = []
	for categoria in CUOTAS_CATEGORIAS:
		valor = by_categoria.get(categoria, 0.0)
		if valor <= 0:
			continue
		categorias.append(
			{
				"categoria": categoria,
				"valor": valor,
				"condicion": CONDICIONES_PUBLICAS.get(categoria, ""),
			}
		)

	raw = frappe.db.get_single_value("Club Settings", "cuotas_vigente_desde")
	vigente = None
	if raw:
		parsed = getdate(raw)
		if parsed and parsed.year >= 1900:
			vigente = str(parsed)

	return {"vigente_desde": vigente, "categorias": categorias}

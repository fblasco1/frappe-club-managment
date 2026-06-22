"""Resolución de la Company ICDPE (tolerante a acentos en el nombre)."""

from __future__ import annotations

import frappe
from frappe import _

COMPANY_ABBR = "ICDPE"
COMPANY_CANONICAL = "Institución Cultural y Deportiva Pedro Echagüe"
COMPANY_ALIASES: tuple[str, ...] = (
	COMPANY_CANONICAL,
	"Institucion Cultural y Deportiva Pedro Echagüe",
)


def resolve_icdpe_company() -> str:
	"""Devuelve el `name` de la Company ICDPE en el sitio."""
	for name in COMPANY_ALIASES:
		if frappe.db.exists("Company", name):
			return name

	by_abbr = frappe.get_all("Company", filters={"abbr": COMPANY_ABBR}, pluck="name", limit=1)
	if by_abbr:
		return by_abbr[0]

	frappe.throw(
		_("No se encontró la Company ICDPE (abbr {0}).").format(COMPANY_ABBR),
		title=_("Company ICDPE"),
	)

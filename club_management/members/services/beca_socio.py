"""Aplicación de becas en facturación mensual (spec beca_socio.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import frappe
from frappe.utils import flt, getdate, today

BECA_DOCTYPE = "Beca Socio"


@dataclass(frozen=True)
class BecaVigente:
	tipo_beca: str
	pct_cuota_social: float
	pct_arancel: float

	@property
	def exime_cuota(self) -> bool:
		return self.tipo_beca == "Total" or flt(self.pct_cuota_social) >= 100

	@property
	def exime_arancel(self) -> bool:
		return self.tipo_beca == "Total" or flt(self.pct_arancel) >= 100

	def rate_cuota(self, rate: float) -> float:
		if self.exime_cuota:
			return 0.0
		pct = flt(self.pct_cuota_social)
		return flt(rate) * max(0.0, 1.0 - pct / 100.0)

	def rate_arancel(self, rate: float) -> float:
		if self.exime_arancel:
			return 0.0
		pct = flt(self.pct_arancel)
		return flt(rate) * max(0.0, 1.0 - pct / 100.0)


def beca_vigente_socio(
	socio_name: str,
	*,
	reference_date: str | date | None = None,
) -> BecaVigente | None:
	"""Beca activa del socio en la fecha de referencia, si existe."""
	if not frappe.db.exists("DocType", BECA_DOCTYPE):
		return None
	ref = getdate(reference_date or today())
	row = frappe.db.get_value(
		BECA_DOCTYPE,
		{
			"socio": socio_name,
			"estado": "Activa",
			"fecha_desde": ["<=", ref],
			"fecha_hasta": [">=", ref],
		},
		["tipo_beca", "pct_cuota_social", "pct_arancel"],
		as_dict=True,
		order_by="modified desc",
	)
	if not row:
		return None
	return BecaVigente(
		tipo_beca=row.tipo_beca,
		pct_cuota_social=flt(row.pct_cuota_social),
		pct_arancel=flt(row.pct_arancel),
	)


def vigencia_label_beca(
	*,
	estado: str,
	fecha_desde: str | date,
	fecha_hasta: str | date,
	reference_date: str | date | None = None,
) -> str:
	"""Etiqueta de vigencia para Desk (Vigente / Pendiente / Vencida / Cancelada)."""
	if estado == "Cancelada":
		return "Cancelada"
	if estado == "Vencida":
		return "Vencida"
	ref = getdate(reference_date or today())
	desde = getdate(fecha_desde)
	hasta = getdate(fecha_hasta)
	if ref < desde:
		return "Pendiente"
	if ref > hasta:
		return "Vencida"
	if estado == "Activa":
		return "Vigente"
	return estado or ""


def list_becas_socio(
	socio_name: str,
	*,
	reference_date: str | date | None = None,
) -> list[dict[str, object]]:
	"""Todas las becas del socio, más recientes primero."""
	if not frappe.db.exists("DocType", BECA_DOCTYPE):
		return []
	if not frappe.db.exists("Socio", socio_name):
		frappe.throw(frappe._("Socio no encontrado"), frappe.DoesNotExistError)

	rows = frappe.get_all(
		BECA_DOCTYPE,
		filters={"socio": socio_name},
		fields=[
			"name",
			"tipo_beca",
			"pct_cuota_social",
			"pct_arancel",
			"fecha_desde",
			"fecha_hasta",
			"estado",
			"observaciones",
		],
		order_by="fecha_desde desc, modified desc",
	)
	result: list[dict[str, object]] = []
	for row in rows:
		result.append(
			{
				"name": row.name,
				"tipo_beca": row.tipo_beca,
				"pct_cuota_social": flt(row.pct_cuota_social),
				"pct_arancel": flt(row.pct_arancel),
				"fecha_desde": str(row.fecha_desde) if row.fecha_desde else "",
				"fecha_hasta": str(row.fecha_hasta) if row.fecha_hasta else "",
				"estado": row.estado,
				"observaciones": row.observaciones or "",
				"vigencia_label": vigencia_label_beca(
					estado=row.estado or "",
					fecha_desde=row.fecha_desde,
					fecha_hasta=row.fecha_hasta,
					reference_date=reference_date,
				),
			}
		)
	return result


def list_becas_socio_desk(
	socio_name: str,
	*,
	reference_date: str | date | None = None,
) -> list[dict[str, object]]:
	from club_management.members.services.socio_operaciones_secretaria import (
		ensure_secretaria_operacion_access,
	)

	ensure_secretaria_operacion_access()
	return list_becas_socio(socio_name, reference_date=reference_date)

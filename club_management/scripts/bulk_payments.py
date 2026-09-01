"""Carga masiva de cobranzas del mes (Payment Entry → Sales Invoice).

Spec: `club_management/specs/carga_masiva_cobranzas.md`

    bench --site dev.localhost execute club_management.scripts.bulk_payments.run \\
        --kwargs '{"csv_path": "/ruta/cobranzas.csv", "dry_run": true}'
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	format_periodo_cobro,
	registrar_cobro_compuesto,
)
from club_management.members.services.modos_pago_desk import DESK_MODOS_PAGO_COBRANZA
from club_management.members.services.mora_al_cobro import (
	calcular_exigido_linea_factura,
	previsualizar_cobro_con_mora,
)
from club_management.scripts.bulk_io import (
	cell,
	ensure_not_production,
	find_socio,
	parse_fecha,
	parse_monto,
	read_bulk_rows,
)
from club_management.scripts.informe_concepto_cobranza import (
	buscar_linea_factura_concepto,
	es_cuota_complementaria,
	linea_cuota_complementaria_en_periodo,
)

_MEDIO_ALIASES: dict[str, str] = {
	"efectivo": "Cash",
	"cash": "Cash",
	"transferencia": "Wire Transfer",
	"wire transfer": "Wire Transfer",
	"tarjeta credito": "Credit Card",
	"tarjeta crédito": "Credit Card",
	"tarjeta (crédito)": "Credit Card",
	"credit card": "Credit Card",
	"tarjeta debito": "Bank Draft",
	"tarjeta débito": "Bank Draft",
	"tarjeta (débito)": "Bank Draft",
	"bank draft": "Bank Draft",
	"cheque": "Cheque",
}
for _row in DESK_MODOS_PAGO_COBRANZA:
	_MEDIO_ALIASES[_row["value"].lower()] = _row["value"]
	_MEDIO_ALIASES[_row["label"].lower()] = _row["value"]

# Cuota social: tarifas vigentes y mora 10 % / 15 %.
TARIFA_CUOTA_ACTIVO = 31000.0
MONTO_CUOTA_ACTIVO_MORA_15 = 35650.0
SALDO_FAVOR_ACTIVO_MORA_15 = 4650.0
TARIFA_CUOTA_MENOR = 28500.0
MONTO_CUOTA_MENOR_MORA_15 = 32775.0
TARIFA_CUOTA_ADHERENTE = 19500.0
MONTO_CUOTA_ADHERENTE_MORA_10 = 21450.0
MONTO_CUOTA_ADHERENTE_MORA_15 = 22425.0
TARIFA_CUOTA_JUBILADO = 5500.0
_CONCEPTO_CUOTA_SOCIAL = re.compile(r"cuota\s+social", re.I)
_CONCEPTO_CUOTA_ACTIVO = re.compile(r"cuota\s+social\s+activo", re.I)


def _es_cuota_social(concepto: str | None) -> bool:
	return bool(_CONCEPTO_CUOTA_SOCIAL.search((concepto or "").strip()))


def _montos_cuota_con_mora(tarifa: float) -> tuple[float, float, float]:
	base = flt(tarifa, 2)
	return base, flt(base * 1.10, 2), flt(base * 1.15, 2)


def _tarifas_cuota_social_catalogo() -> list[float]:
	from club_management.members.data.cuotas_sociales_vigentes import CUOTAS_SOCIALES_VIGENTES

	return [flt(monto, 2) for _categoria, monto in CUOTAS_SOCIALES_VIGENTES]


def _tarifa_por_monto_cuota_informe(monto: float, *, tolerance: float = 0.01) -> float | None:
	"""Resuelve tarifa base si el monto informe coincide con base o mora 10/15 %."""
	m = flt(monto, 2)
	for tarifa in _tarifas_cuota_social_catalogo():
		if any(abs(m - x) <= tolerance for x in _montos_cuota_con_mora(tarifa)):
			return tarifa
	return None


def clasificar_cobro_cuota_informe(
	concepto: str | None,
	monto: float,
	periodo: str | None,
	fecha: Any,
	socio_name: str,
	*,
	tolerance: float = 0.01,
) -> tuple[str, float, float] | None:
	"""Clasifica cobro de cuota social según tarifa del socio e informe.

	Devuelve (modo, monto_cuota, saldo_favor):
	- cobrar: imputar monto informe con mora normal
	- agosto_pre20_saldo_favor: imputar solo base; resto saldo a favor
	"""
	if not _es_cuota_social(concepto):
		return None
	m = flt(monto, 2)
	tarifa = _tarifa_por_monto_cuota_informe(m, tolerance=tolerance)
	if not tarifa:
		return None
	base, mora10, mora15 = _montos_cuota_con_mora(tarifa)

	mes_anio = _periodo_mes_anio(periodo)
	dia = getdate(fecha).day if fecha else 1
	# Agosto, pago antes del día 20, informe trae mora 15 % → saldo a favor del excedente.
	if (
		mes_anio
		and mes_anio == (2026, 8)
		and dia < 20
		and abs(m - mora15) <= tolerance
	):
		return ("agosto_pre20_saldo_favor", base, flt(m - base, 2))
	# Período anterior a agosto con mora 15 % en informe: correcto.
	if mes_anio and (mes_anio[0], mes_anio[1]) < (2026, 8) and abs(m - mora15) <= tolerance:
		return ("cobrar", m, 0.0)
	return ("cobrar", m, 0.0)


def _es_cuota_social_menor(concepto: str | None) -> bool:
	return bool(re.search(r"cuota\s+social\s+menor", (concepto or "").strip(), re.I))


def _tolerancia_menor_error_cobranza_500(
	concepto: str | None,
	monto: float,
	exigido: float,
	periodo: str | None,
	*,
	tolerance: float = 0.01,
) -> bool:
	"""Período anterior a agosto: informe cobró $500 menos (error de cobranza)."""
	if not _es_cuota_social_menor(concepto):
		return False
	mes_anio = _periodo_mes_anio(periodo)
	if not mes_anio or mes_anio >= (2026, 8):
		return False
	return abs(flt(exigido) - flt(monto) - 500.0) <= max(tolerance, 1.0)


def _tolerar_cobrador_mora10_en_lugar_15(
	monto: float,
	exigido: float,
	line_base: float,
	*,
	tolerance: float = 0.01,
) -> bool:
	"""Cobrador aplicó mora 10 % pero el sistema exige 15 % (fallo tolerado)."""
	base = flt(line_base, 2)
	if base <= 0:
		return False
	mora10 = flt(base * 1.10, 2)
	mora15 = flt(base * 1.15, 2)
	return (
		abs(flt(monto) - mora10) <= tolerance
		and abs(flt(exigido) - mora15) <= tolerance
	)


def _excedente_saldo_favor_informe(
	monto: float,
	exigido: float,
	*,
	tolerance: float = 0.01,
	max_excedente: float = 500.0,
) -> float | None:
	diff = flt(flt(monto) - flt(exigido), 2)
	if diff > tolerance and diff <= max_excedente + tolerance:
		return diff
	return None


def _es_cuota_social_activo(concepto: str | None) -> bool:
	return bool(_CONCEPTO_CUOTA_ACTIVO.search((concepto or "").strip()))


def _periodo_mes_anio(periodo: str | None) -> tuple[int, int] | None:
	from club_management.members.services.mora_al_cobro import parse_periodo_cobro

	inicio = parse_periodo_cobro(periodo)
	if not inicio:
		return None
	return inicio.year, inicio.month


def clasificar_cobro_activo_35650(
	concepto: str | None,
	monto: float,
	periodo: str | None,
	fecha: Any,
	*,
	tolerance: float = 0.01,
) -> str | None:
	"""Regla informe Activo @ $35.650 según período y fecha de pago."""
	if not _es_cuota_social_activo(concepto):
		return None
	if abs(flt(monto) - MONTO_CUOTA_ACTIVO_MORA_15) > tolerance:
		return None
	mes_anio = _periodo_mes_anio(periodo)
	if not mes_anio:
		return None
	anio, mes = mes_anio
	dia = getdate(fecha).day
	if anio == 2026 and mes == 8:
		if dia < 20:
			return "agosto_pre20_saldo_favor"
		return "mora_15"
	if (anio, mes) < (2026, 8):
		return "mora_15"
	return None


def _registrar_saldo_favor_cliente(
	socio_name: str,
	monto: float,
	*,
	mode_of_payment: str,
	posting_date: Any,
	reference_no: str | None,
	nota: str,
) -> str:
	from club_management.integrations.payment_ledger_postgres import apply_patch
	from club_management.members.services.cobranza_manual import (
		ensure_customer_for_socio,
	)
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	apply_patch()
	ensure_customer_for_socio(socio_name, skip_permission_check=True)
	inv = frappe.db.get_value(
		SALES_INVOICE_DOCTYPE,
		{"socio": socio_name, "docstatus": 1},
		"name",
		order_by="creation desc",
	)
	if not inv:
		frappe.throw(_("Sin facturas para saldo a favor de {0}").format(socio_name))

	pe = get_payment_entry(SALES_INVOICE_DOCTYPE, inv, party_amount=flt(monto, 2))
	pe.set("references", [])
	pe.mode_of_payment = mode_of_payment
	pe.paid_amount = flt(monto, 2)
	pe.received_amount = flt(monto, 2)
	pe.posting_date = getdate(posting_date)
	pe.reference_date = getdate(posting_date)
	pe.reference_no = (reference_no or f"SALDO-FAVOR-{socio_name}")[:140]
	pe.remarks = nota
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


@dataclass
class BulkPaymentsStats:
	total_filas: int = 0
	procesadas: int = 0
	simuladas: int = 0
	ya_procesado: int = 0
	monto_total: float = 0.0
	facturas_saldadas: list[str] = field(default_factory=list)
	payment_entries: list[str] = field(default_factory=list)
	inconsistencias: list[dict[str, Any]] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"procesadas": self.procesadas,
			"simuladas": self.simuladas,
			"ya_procesado": self.ya_procesado,
			"monto_total": flt(self.monto_total, 2),
			"facturas_saldadas": self.facturas_saldadas,
			"payment_entries": self.payment_entries,
			"inconsistencias": self.inconsistencias,
		}


def map_medio_pago(raw: str) -> str | None:
	key = re.sub(r"\s+", " ", (raw or "").strip().lower())
	if not key:
		return None
	return _MEDIO_ALIASES.get(key)


def facturas_impagas_periodo(socio_name: str, periodo: str) -> list[str]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	filters: dict[str, Any] = {
		campo_socio: socio_name,
		"docstatus": 1,
		"outstanding_amount": [">", 0],
	}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo
	return frappe.get_all(SALES_INVOICE_DOCTYPE, filters=filters, pluck="name", order_by="name asc")


def facturas_periodo(socio_name: str, periodo: str) -> list[str]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	filters: dict[str, Any] = {campo_socio: socio_name, "docstatus": 1}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo
	return frappe.get_all(SALES_INVOICE_DOCTYPE, filters=filters, pluck="name")


def _pe_existente(socio_name: str, referencia: str) -> str | None:
	ref = (referencia or "").strip()
	if not ref:
		return None
	campo = _campo_socio_en("Customer")
	customer = frappe.db.get_value("Customer", {campo: socio_name}, "name") if campo else None
	filters: dict[str, Any] = {"reference_no": ref, "docstatus": ["!=", 2]}
	if customer:
		filters["party"] = customer
	return frappe.db.get_value("Payment Entry", filters, "name")


def _elegir_facturas(
	preview: dict[str, Any],
	monto: float,
	invoices: list[str],
	tolerance: float,
) -> tuple[list[str] | None, float, str | None]:
	total = flt(preview.get("total_exigido"), 2)
	if abs(total - monto) <= tolerance:
		return invoices, total, None
	matches: list[str] = []
	matched_amount = 0.0
	for det in preview.get("detalle") or []:
		exigido = flt(det.get("monto_exigido"), 2)
		if abs(exigido - monto) <= tolerance:
			inv = det.get("invoice")
			if inv:
				matches.append(inv)
				matched_amount = exigido
	if len(matches) == 1:
		return matches, matched_amount, None
	return None, total, "monto_discordante"


def _intentar_cobro_por_concepto(
	socio_name: str,
	periodo_fila: str,
	concepto: str,
	monto: float,
	fecha: Any,
	reservadas: set[str],
	tolerance: float,
) -> tuple[list[str] | None, float, str | None, str | None]:
	"""Match por línea de concepto. Devuelve (facturas, exigido, err, item_code)."""
	if not (concepto or "").strip():
		return None, 0.0, None, None

	match = buscar_linea_factura_concepto(
		socio_name,
		periodo_fila,
		concepto,
		monto_abonado=monto,
		reservadas=reservadas,
	)
	if not match:
		return None, 0.0, "concepto_sin_factura", None

	invoice_name, item_code, line_base = match
	line_base = flt(line_base, 2)
	regla_cuota = clasificar_cobro_cuota_informe(
		concepto, monto, periodo_fila, fecha, socio_name, tolerance=tolerance
	)
	if regla_cuota:
		return [invoice_name], flt(monto, 2), None, item_code

	regla_activo = clasificar_cobro_activo_35650(
		concepto, monto, periodo_fila, fecha, tolerance=tolerance
	)
	if regla_activo:
		return [invoice_name], flt(monto, 2), None, item_code

	info = calcular_exigido_linea_factura(
		invoice_name,
		item_code,
		socio_name,
		posting_date=fecha,
	)
	exigido = flt(info.get("monto_exigido"), 2)
	if exigido <= 0 and line_base <= 0:
		return None, 0.0, "concepto_sin_factura", item_code
	if abs(line_base - monto) <= tolerance:
		return [invoice_name], line_base, None, item_code
	if abs(exigido - monto) <= tolerance:
		return [invoice_name], exigido, None, item_code
	preview = previsualizar_cobro_con_mora(socio_name, [invoice_name], posting_date=fecha)
	total_mora = flt(preview.get("total_exigido"), 2)
	if total_mora > 0 and abs(total_mora - monto) <= tolerance:
		return [invoice_name], total_mora, None, item_code
	# Saldo pendiente / pago parcial (p. ej. resto de cuota del mes anterior).
	outstanding = flt(
		frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"),
		2,
	)
	if 0 < monto <= outstanding + tolerance:
		return [invoice_name], monto, None, item_code
	if _tolerancia_menor_error_cobranza_500(
		concepto, monto, exigido, periodo_fila, tolerance=tolerance
	):
		return [invoice_name], monto, None, item_code
	if _tolerar_cobrador_mora10_en_lugar_15(
		monto, exigido, line_base, tolerance=tolerance
	):
		return [invoice_name], monto, None, item_code
	if _excedente_saldo_favor_informe(monto, exigido, tolerance=tolerance):
		return [invoice_name], monto, None, item_code
	return None, exigido or line_base, "monto_discordante", item_code


def _registrar_cobro_concepto_informe(
	socio_name: str,
	invoice_name: str,
	monto: float,
	*,
	mode_of_payment: str,
	posting_date: Any,
	reference_no: str | None,
	auto_submit: bool,
	concepto: str | None = None,
	periodo_fila: str | None = None,
) -> dict[str, Any]:
	"""Cobra el monto del informe contra la SI (y ajuste de mora si aplica), sin exigir el total multi-línea."""
	from club_management.integrations.payment_ledger_postgres import apply_patch
	from club_management.members.services.cobranza_manual import (
		registrar_cobro_parcial_factura,
		sync_saldo_deuda_socio,
	)
	from club_management.members.services.mora_al_cobro import preparar_facturas_cobro_con_mora

	apply_patch()
	regla_cuota = clasificar_cobro_cuota_informe(
		concepto, monto, periodo_fila, posting_date, socio_name
	)
	regla_activo = clasificar_cobro_activo_35650(concepto, monto, periodo_fila, posting_date)
	payment_entries: list[str] = []

	agosto_sf = (
		regla_cuota and regla_cuota[0] == "agosto_pre20_saldo_favor"
	) or regla_activo == "agosto_pre20_saldo_favor"

	if agosto_sf:
		if regla_cuota and regla_cuota[0] == "agosto_pre20_saldo_favor":
			monto_cuota, saldo_favor = regla_cuota[1], regla_cuota[2]
		else:
			monto_cuota = flt(TARIFA_CUOTA_ACTIVO, 2)
			saldo_favor = flt(SALDO_FAVOR_ACTIVO_MORA_15, 2)
		result = registrar_cobro_parcial_factura(
			socio_name,
			invoice_name,
			monto_cuota,
			mode_of_payment=mode_of_payment,
			posting_date=posting_date,
			reference_no=reference_no,
			auto_submit=auto_submit,
		)
		payment_entries.extend(result.get("payment_entries") or [])
		if saldo_favor > 0.005:
			pe_adv = _registrar_saldo_favor_cliente(
				socio_name,
				saldo_favor,
				mode_of_payment=mode_of_payment,
				posting_date=posting_date,
				reference_no=f"{(reference_no or 'INF')[:100]}-SF"[:140],
				nota=_(
					"Saldo a favor: cuota agosto pagada antes del día 20 con mora 15 % del informe; "
					"exigible sin mora."
				),
			)
			payment_entries.append(pe_adv)
		saldo = sync_saldo_deuda_socio(socio_name)
		return {
			"status": "ok",
			"payment_entries": payment_entries,
			"saldo_deuda": saldo,
			"saldo_favor": saldo_favor,
		}

	prep = preparar_facturas_cobro_con_mora(socio_name, [invoice_name], posting_date=posting_date)
	remaining = flt(monto, 2)
	for inv_name in prep.get("sales_invoices") or []:
		if remaining <= 0.005:
			break
		outstanding = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, inv_name, "outstanding_amount"))
		if outstanding <= 0:
			continue
		take = min(remaining, outstanding)
		result = registrar_cobro_parcial_factura(
			socio_name,
			inv_name,
			take,
			mode_of_payment=mode_of_payment,
			posting_date=posting_date,
			reference_no=reference_no if not payment_entries else None,
			auto_submit=auto_submit,
		)
		payment_entries.extend(result.get("payment_entries") or [])
		remaining = flt(remaining - take, 2)

	saldo_favor = 0.0
	if remaining > 0.005:
		saldo_favor = remaining
		pe_adv = _registrar_saldo_favor_cliente(
			socio_name,
			saldo_favor,
			mode_of_payment=mode_of_payment,
			posting_date=posting_date,
			reference_no=f"{(reference_no or 'INF')[:100]}-SF"[:140],
			nota=_("Saldo a favor: excedente del informe no imputable a la factura."),
		)
		payment_entries.append(pe_adv)

	saldo = sync_saldo_deuda_socio(socio_name)
	return {
		"status": "ok",
		"payment_entries": payment_entries,
		"saldo_deuda": saldo,
		"saldo_favor": saldo_favor,
	}


def _add_error(stats: BulkPaymentsStats, fila: int, codigo: str, **extra: Any) -> None:
	row = {"fila": fila, "codigo": codigo, **extra}
	stats.inconsistencias.append(row)


def _write_log(stats: BulkPaymentsStats, log_path: str | None) -> str | None:
	if not log_path:
		return None
	path = Path(log_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
	csv_path = path.with_suffix(".inconsistencias.csv")
	_write_inconsistencias_csv(stats, csv_path)
	return str(path)


def _write_inconsistencias_csv(stats: BulkPaymentsStats, csv_path: Path) -> None:
	import csv as csv_mod

	fields = [
		"fila",
		"codigo",
		"nro_socio",
		"socio",
		"fecha_pago",
		"periodo",
		"concepto",
		"medio_pago",
		"monto_abonado",
		"monto_exigido",
		"diferencia",
		"facturas",
		"item_code",
		"dni",
	]
	with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
		writer = csv_mod.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
		writer.writeheader()
		for row in stats.inconsistencias:
			writer.writerow({k: row.get(k, "") for k in fields})


def _print_resumen(stats: BulkPaymentsStats, *, dry_run: bool, csv_path: str) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "COBRANZAS EJECUTADAS"
	print("\n" + "=" * 72)
	print(f" CARGA MASIVA COBRANZAS — {mode}")
	print("=" * 72)
	print(f" CSV                             : {csv_path}")
	data = stats.to_dict()
	for key, value in data.items():
		if key in {"inconsistencias", "facturas_saldadas", "payment_entries"}:
			continue
		print(f" {key:30s}: {value}")
	print(f" {'facturas_saldadas':30s}: {len(stats.facturas_saldadas)}")
	if stats.inconsistencias:
		print("-" * 72)
		print(" Inconsistencias (primeras 25):")
		for err in stats.inconsistencias[:25]:
			print(f"   - {err}")
		remaining = len(stats.inconsistencias) - 25
		if remaining > 0:
			print(f"   ... y {remaining} más")
	print("=" * 72 + "\n")


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	auto_submit: bool = True,
	periodo: str | None = None,
	tolerance: float = 0.5,
	limit: int | None = None,
	log_path: str | None = None,
	commit_every: int = 25,
	confirm: str = "",
) -> dict[str, Any]:
	"""Procesa el CSV/Excel de cobranzas. Default: dry-run."""
	ensure_not_production(dry_run=dry_run, confirm=confirm)
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	rows = read_bulk_rows(csv_path)
	periodo_corrida = (periodo or "").strip() or format_periodo_cobro(today())
	stats = BulkPaymentsStats(total_filas=len(rows))
	applied = 0
	reservadas: set[str] = set()

	for idx, raw in enumerate(rows, start=2):
		if limit is not None and (stats.procesadas + stats.simuladas + stats.ya_procesado) >= limit:
			break
		nro = cell(raw, "nro_socio", "numero_socio", "nro")
		dni = cell(raw, "dni")
		monto = parse_monto(cell(raw, "monto_abonado", "monto"))
		fecha_raw = cell(raw, "fecha_pago", "fecha")
		medio_raw = cell(raw, "medio_pago", "medio")
		referencia = cell(raw, "referencia_comprobante", "referencia", "comprobante")
		periodo_fila = cell(raw, "periodo", "periodo_cobro") or periodo_corrida

		base = {
			"nro_socio": nro,
			"dni": dni,
			"fecha_pago": fecha_raw,
			"periodo": periodo_fila,
			"concepto": cell(raw, "concepto"),
			"medio_pago": medio_raw,
			"monto_abonado": monto,
		}

		socio_name = find_socio(nro_socio=nro, dni=dni)
		if not socio_name:
			_add_error(stats, idx, "socio_no_encontrado", **base)
			continue

		fecha = parse_fecha(fecha_raw)
		if not fecha:
			_add_error(stats, idx, "fecha_invalida", socio=nro, **base)
			continue
		if fecha > getdate(today()):
			_add_error(stats, idx, "fecha_invalida", socio=socio_name, **{**base, "fecha_pago": str(fecha)})
			continue

		medio = map_medio_pago(medio_raw)
		if not medio:
			_add_error(stats, idx, "medio_pago_invalido", socio=socio_name, **base)
			continue

		if monto <= 0:
			_add_error(stats, idx, "monto_invalido", socio=socio_name, **base)
			continue

		if referencia and _pe_existente(socio_name, referencia):
			stats.ya_procesado += 1
			continue

		concepto_fila = cell(raw, "concepto")
		elegidas: list[str] | None = None
		exigido = 0.0
		err: str | None = None
		item_code_match: str | None = None

		if (concepto_fila or "").strip():
			elegidas, exigido, err, item_code_match = _intentar_cobro_por_concepto(
				socio_name,
				periodo_fila,
				concepto_fila,
				monto,
				fecha,
				reservadas,
				tolerance,
			)
			if err == "concepto_sin_factura":
				if es_cuota_complementaria(concepto_fila):
					if linea_cuota_complementaria_en_periodo(
						socio_name,
						periodo_fila,
						concepto_fila,
						solo_impagas=False,
						reservadas=reservadas,
					):
						_add_error(stats, idx, "ya_saldada", socio=socio_name, **base)
					else:
						_add_error(stats, idx, "sin_factura_impaga", socio=socio_name, **base)
				else:
					todas = facturas_periodo(socio_name, periodo_fila)
					codigo = "ya_saldada" if todas else "sin_factura_impaga"
					_add_error(stats, idx, codigo, socio=socio_name, **base)
				continue
		else:
			invoices = [n for n in facturas_impagas_periodo(socio_name, periodo_fila) if n not in reservadas]
			if not invoices:
				todas = facturas_periodo(socio_name, periodo_fila)
				codigo = "ya_saldada" if todas else "sin_factura_impaga"
				_add_error(stats, idx, codigo, socio=socio_name, **base)
				continue

			preview = previsualizar_cobro_con_mora(socio_name, invoices, posting_date=fecha)
			detalle = [d for d in (preview.get("detalle") or []) if d.get("invoice") not in reservadas]
			preview = {
				**preview,
				"detalle": detalle,
				"total_exigido": flt(sum(flt(d.get("monto_exigido")) for d in detalle), 2),
			}
			elegidas, exigido, err = _elegir_facturas(preview, monto, invoices, tolerance)

		if err or not elegidas:
			_add_error(
				stats,
				idx,
				err or "monto_discordante",
				socio=socio_name,
				monto_exigido=exigido,
				diferencia=flt(monto - exigido, 2),
				facturas=";".join(elegidas or []),
				item_code=item_code_match or "",
				**base,
			)
			continue

		if dry_run:
			stats.simuladas += 1
			stats.monto_total += exigido
			stats.facturas_saldadas.extend(elegidas)
			reservadas.update(elegidas)
			continue

		if len(elegidas) == 1 and item_code_match:
			try:
				result = _registrar_cobro_concepto_informe(
					socio_name,
					elegidas[0],
					monto,
					mode_of_payment=medio,
					posting_date=fecha,
					reference_no=referencia or None,
					auto_submit=auto_submit,
					concepto=concepto_fila,
					periodo_fila=periodo_fila,
				)
			except frappe.ValidationError as exc:
				_add_error(
					stats,
					idx,
					"error_cobro",
					socio=socio_name,
					monto_exigido=exigido,
					error=str(exc),
					facturas=elegidas[0],
					item_code=item_code_match or "",
					**base,
				)
				continue
		else:
			try:
				result = registrar_cobro_compuesto(
					socio_name,
					elegidas,
					[{"mode_of_payment": medio, "amount": exigido}],
					posting_date=fecha,
					reference_no=referencia or None,
					auto_submit=auto_submit,
				)
			except frappe.ValidationError as exc:
				_add_error(
					stats,
					idx,
					"error_cobro",
					socio=socio_name,
					monto_exigido=exigido,
					error=str(exc),
					facturas=";".join(elegidas),
					item_code=item_code_match or "",
					**base,
				)
				continue
		stats.procesadas += 1
		stats.monto_total += exigido
		stats.facturas_saldadas.extend(elegidas)
		stats.payment_entries.extend(result.get("payment_entries") or [])
		reservadas.update(elegidas)
		applied += 1
		if commit_every and applied % commit_every == 0 and not getattr(frappe.flags, "in_test", False):
			frappe.db.commit()

	if not dry_run and applied and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	log = _write_log(stats, log_path)
	payload = stats.to_dict()
	payload["dry_run"] = dry_run
	payload["periodo"] = periodo_corrida
	payload["log_path"] = log
	_print_resumen(stats, dry_run=dry_run, csv_path=csv_path)
	return payload

"""Factura en lote cargos «CTO COMP» (Cuota Complementaria) pendientes.

Spec: `club_management/specs/informe_concepto_cobranza.md`

    bench --site dev.localhost execute club_management.scripts.bulk_facturar_cuota_complementaria.run \\
        --kwargs '{"periodos": ["08/2026", "07/2026"], "dry_run": false}'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import getdate

from club_management.members.services.cargo_extra_prepago import prepagar_cargo_socio
from club_management.members.services.cobranza_manual import reference_date_desde_periodo
from club_management.scripts.bulk_io import ensure_not_production

CARGO_DOCTYPE = "Cargo Socio"


def _pending_cargos(*, titulo_like: str = "CTO COMP") -> list[dict[str, Any]]:
	return frappe.get_all(
		CARGO_DOCTYPE,
		filters={
			"estado": "Pendiente",
			"titulo": ["like", f"%{titulo_like}%"],
			"modo_cobro": "Recurrente",
		},
		fields=["name", "socio", "titulo", "monto", "fecha_desde", "fecha_hasta"],
		order_by="name asc",
	)


def run(
	*,
	periodos: list[str] | None = None,
	dry_run: bool = True,
	titulo_like: str = "CTO COMP",
	log_path: str | None = None,
	commit_every: int = 25,
	confirm: str = "",
) -> dict[str, Any]:
	ensure_not_production(dry_run=dry_run, confirm=confirm)
	periodos_corrida = periodos or ["08/2026"]
	cargos = _pending_cargos(titulo_like=titulo_like)

	facturados: list[dict[str, Any]] = []
	omitidos: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []

	for idx, row in enumerate(cargos, start=1):
		cargo_name = row["name"]
		entry_base = {
			"cargo": cargo_name,
			"socio": row.get("socio"),
			"titulo": row.get("titulo"),
			"monto": row.get("monto"),
		}
		if dry_run:
			omitidos.append({**entry_base, "motivo": "dry_run"})
			continue
		try:
			created: list[str] = []
			skipped: list[str] = []
			for periodo in periodos_corrida:
				try:
					result = prepagar_cargo_socio(
						cargo_name,
						periodos=[periodo],
						reference_date=reference_date_desde_periodo(periodo),
					)
				except frappe.ValidationError as exc:
					msg = str(exc)
					if "fuera de la vigencia" in msg:
						continue
					raise
				created.extend(result.get("sales_invoices") or [])
				skipped.extend(result.get("omitidos") or [])
			if created:
				facturados.append({**entry_base, "sales_invoices": created, "omitidos_periodo": skipped})
			elif skipped:
				omitidos.append({**entry_base, "motivo": "ya_facturado_periodo", "periodos": skipped})
			else:
				omitidos.append({**entry_base, "motivo": "sin_periodos_elegibles"})
		except Exception as exc:
			errores.append({**entry_base, "error": str(exc)})

		if not dry_run and commit_every and idx % commit_every == 0 and not getattr(frappe.flags, "in_test", False):
			frappe.db.commit()

	if not dry_run and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	payload = {
		"periodos": periodos_corrida,
		"dry_run": dry_run,
		"cargos_pendientes": len(cargos),
		"facturados": len(facturados),
		"omitidos": len(omitidos),
		"errores": len(errores),
		"detalle_facturados": facturados,
		"detalle_omitidos": omitidos[:100],
		"detalle_errores": errores,
	}
	if log_path:
		path = Path(log_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
		payload["log_path"] = str(path)

	print("\n" + "=" * 72)
	print(f" FACTURACIÓN LOTE CUOTA COMPLEMENTARIA — {'SIMULACIÓN' if dry_run else 'EJECUTADO'}")
	print("=" * 72)
	for k in ("cargos_pendientes", "facturados", "omitidos", "errores", "periodos"):
		print(f" {k:30s}: {payload.get(k)}")
	if errores:
		print(" Errores (primeros 10):")
		for err in errores[:10]:
			print(f"   - {err}")
	print("=" * 72 + "\n")
	return payload

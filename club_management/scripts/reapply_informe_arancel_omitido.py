"""Reimputa renglones de arancel del informe que quedaron como `ya_saldada`.

Tras el bug de reserva de SI multi-línea, la cuota se cobró y el arancel
(PRE-MINI, tiras, etc.) se omitió aunque la factura seguía impaga.

Idempotente: las filas ya cobradas (`referencia_comprobante`) se saltan.

    bench --site dev.localhost execute \\
        club_management.scripts.reapply_informe_arancel_omitido.run \\
        --kwargs '{"csv_path": "/ruta/Cobranza 01 a 28-08.xlsx", "dry_run": true}'
"""

from __future__ import annotations

from typing import Any

from club_management.scripts.bulk_payments import run as run_bulk_payments


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	confirm: str = "",
	log_path: str | None = None,
	tolerance: float = 1.0,
) -> dict[str, Any]:
	"""Re-ejecuta la carga masiva (idempotente) para imputar aranceles omitidos."""
	return run_bulk_payments(
		csv_path=csv_path,
		dry_run=dry_run,
		confirm=confirm,
		log_path=log_path,
		tolerance=tolerance,
	)

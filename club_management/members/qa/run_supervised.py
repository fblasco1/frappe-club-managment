"""Ejecución supervisada del flujo Solicitud de Asociación.

Uso:
  bench --site dev.localhost execute club_management.members.qa.run_supervised.run
  bench --site dev.localhost execute club_management.members.qa.run_supervised.run \\
    --kwargs '{"auto": true, "dni": "80999111", "email": "qa@example.com"}'
"""

from __future__ import annotations

import json
from typing import Any

import frappe

from club_management.members.qa.flujo_solicitud import FlujoSolicitudRunner

_STEP_LABELS = {
	"alta_publica": "Alta pública (submit_solicitud)",
	"consultar": "Consulta de estado por token",
	"validar": "Validación Secretaría (User + Socio + Grupo)",
	"pago_stub": "Pago stub → Socio Activo",
	"correccion": "Corrección pública y reenvío a Pendiente",
	"fin": "Flujo con corrección finalizado",
}


def _supervised_pause(step_id: str, evidence: dict[str, Any]) -> None:
	label = _STEP_LABELS.get(step_id, step_id)
	print("\n" + "=" * 60)
	print(f"Paso: {label}")
	print(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))
	print("=" * 60)
	try:
		resp = input("¿Continuar? [Enter = sí, n = abortar]: ").strip().lower()
	except EOFError:
		return
	if resp == "n":
		frappe.throw(f"Flujo abortado por el operador en paso «{step_id}»")


def run(
	auto: bool = False,
	dni: str = "80999001",
	email: str = "flujo.qa@example.com",
	con_correccion: bool = False,
) -> dict[str, Any]:
	"""Entry point para `bench execute`."""
	frappe.only_for("System Manager")

	runner = FlujoSolicitudRunner(
		dni=dni,
		email=email,
		on_step=None if auto else _supervised_pause,
		patch_validacion_email=True,
	)

	if con_correccion:
		result = runner.run_path_con_correccion()
	else:
		result = runner.run_happy_path_adulto()

	summary = {
		"status": "ok",
		"token_seguimiento": result.token_seguimiento,
		"solicitud": result.solicitud_name,
		"socio": result.socio_name,
		"user": result.user_name,
		"grupo": result.grupo_name,
		"pago_token": result.pago_token,
		"steps": len(result.steps),
	}
	print("\n✓ Flujo completado:")
	print(json.dumps(summary, indent=2, ensure_ascii=False))
	return summary

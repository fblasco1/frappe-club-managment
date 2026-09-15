"""Scheduler: moroso automático post segundo vencimiento."""

from __future__ import annotations

from club_management.members.services.cobranza_periodica import es_dia_segundo_vencimiento
from club_management.members.services.moroso_automatico import evaluar_morosos_automatico


def run_evaluar_morosos_si_corresponde() -> None:
	"""Job diario: evalúa morosos el día del 2.º vencimiento (después del recargo)."""
	if not es_dia_segundo_vencimiento():
		return
	evaluar_morosos_automatico()

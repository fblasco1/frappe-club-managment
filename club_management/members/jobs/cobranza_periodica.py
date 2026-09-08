"""Scheduler: deuda mensual de socios."""

from __future__ import annotations

from club_management.members.services.cobranza_periodica import (
	es_dia_generacion_deuda,
	es_dia_segundo_vencimiento,
	generar_deuda_mensual_socios,
)
from club_management.members.services.cobranza_recargo import aplicar_recargos_segundo_vencimiento


def run_generar_deuda_si_corresponde() -> None:
	"""Job diario: genera deuda si hoy coincide con `dia_generacion_deuda`."""
	if not es_dia_generacion_deuda():
		return
	generar_deuda_mensual_socios()


def run_recargos_si_corresponde() -> None:
	"""Job diario: aplica recargos si hoy es el 2.º vencimiento del mes."""
	if not es_dia_segundo_vencimiento():
		return
	aplicar_recargos_segundo_vencimiento()

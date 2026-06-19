"""Retira aranceles Mayo 2026 y alinea cuotas sociales al ítem de suscripción."""

from __future__ import annotations

from club_management.activities.services.retire_aranceles_mayo_2026 import retire_aranceles_mayo_2026
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club


def execute() -> None:
	retire_aranceles_mayo_2026()
	sync_cuotas_sociales_club(update_montos_from_vigentes=True)

"""Patch GF-7: re-sincroniza workspace Tesorería con etiquetas en español.

Reutiliza el sync idempotente de `sync_tesoreria_workspace` para reimportar
el JSON (ahora con labels en español). Necesario porque los patches solo
corren una vez y el workspace ya existía con las etiquetas en inglés.
"""

from __future__ import annotations

from club_management.patches.v1_0.sync_tesoreria_workspace import execute as sync_workspace


def execute() -> None:
	sync_workspace()

"""Patch GF-6: re-sincroniza el workspace Tesorería con contenido y Card Breaks.

El workspace tenía `content` vacío y links sin `Card Break`, por lo que el área
central no renderizaba los accesos. Este patch reimporta el JSON (ahora con
content + tarjetas Análisis/Operaciones). Necesario en sitios ya migrados,
donde `sync_tesoreria_workspace` ya corrió una vez.
"""

from __future__ import annotations

from club_management.patches.v1_0.sync_tesoreria_workspace import execute as sync_workspace


def execute() -> None:
	sync_workspace()

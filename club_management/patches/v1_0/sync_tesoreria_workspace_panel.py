"""Patch GF-6: re-sincroniza Tesorería como workspace vacío (panel custom).

El workspace pasa a renderizarse con un panel JS custom; el `content` nativo
queda vacío. Reimporta el JSON en sitios ya migrados.
"""

from __future__ import annotations

from club_management.patches.v1_0.sync_tesoreria_workspace import execute as sync_workspace


def execute() -> None:
	sync_workspace()

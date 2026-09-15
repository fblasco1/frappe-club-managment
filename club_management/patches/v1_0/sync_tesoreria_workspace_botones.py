"""Patch GF-6: re-sincroniza Tesorería con botones navegadores + quick lists.

Reimporta el JSON (ahora sin título/header, con shortcuts como botones arriba y
quick lists con la info debajo). Necesario en sitios ya migrados donde
`sync_tesoreria_workspace` ya corrió una vez.
"""

from __future__ import annotations

from club_management.patches.v1_0.sync_tesoreria_workspace import execute as sync_workspace


def execute() -> None:
	sync_workspace()

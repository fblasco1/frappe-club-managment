"""Especificación de ítem ERPNext para aranceles mensuales deportivos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArancelItemSpec:
	item_code: str
	item_name: str
	rate: float
	cost_center: str

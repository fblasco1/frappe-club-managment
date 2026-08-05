"""Especificación de ítem ERPNext para aranceles mensuales deportivos."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ArancelItemSpec:
	item_code: str
	item_name: str
	rate: float
	cost_center: str


def _normalize_arancel_segment(segment: str) -> str:
	"""MAYÚSCULAS ASCII sin tildes; colapsa espacios internos."""
	decomposed = unicodedata.normalize("NFKD", segment.strip())
	ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
	return " ".join(ascii_only.upper().split())


def format_arancel_mensual_item_name(*segments: str | None) -> str:
	"""Arma ``ARANCEL MENSUAL - A/R/T/G/E`` omitiendo segmentos vacíos.

	Spec: ``arancel_item_naming.md``.
	"""
	parts = [_normalize_arancel_segment(s) for s in segments if s and str(s).strip()]
	if not parts:
		raise ValueError("format_arancel_mensual_item_name requiere al menos un segmento")
	return "ARANCEL MENSUAL - " + "/".join(parts)

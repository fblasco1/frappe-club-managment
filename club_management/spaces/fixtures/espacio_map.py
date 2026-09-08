"""Resolución de Espacio para partidos importados."""

from __future__ import annotations

import re
import unicodedata

import frappe

from club_management.spaces.fixtures.contract import (
	ORIGIN_FEBAMBA_GES,
	ORIGIN_FMV_VOLEY,
	FixturePartido,
	LOCALIA_LOCAL,
)
from club_management.spaces.import_horarios import CANCHA_1, CANCHA_2, CANCHA_3, map_espacio

# Básquet (FeBAMBA GES y fixtures sin espacio explícito) → Cancha 3.
BASQUET_ESPACIO_DEFAULT = CANCHA_3
# Vóley FMV: default Cancha 2; Superior A → Cancha 1.
VOLEY_ESPACIO_DEFAULT = CANCHA_2
VOLEY_SUPERIOR_A = CANCHA_1

_SUPERIOR_A_RE = re.compile(r"^SUPERIOR\s+ECHAGUE$", re.IGNORECASE)
_SUPERIOR_B_RE = re.compile(r"^SUPERIOR\s+ECHAGUE\s+B$", re.IGNORECASE)


def fold_accents(value: str) -> str:
	"""Normaliza acentos y espacios para comparar nombres de equipo."""
	normalized = unicodedata.normalize("NFKD", value or "")
	ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
	return " ".join(ascii_only.upper().split())


def resolve_espacio_fmv(partido: FixturePartido) -> str | None:
	"""Reglas Cancha 1/2 para partidos FMV sin espacio explícito."""
	label = fold_accents(partido.equipo or partido.categoria or "")
	if _SUPERIOR_A_RE.match(label):
		target = VOLEY_SUPERIOR_A
	elif _SUPERIOR_B_RE.match(label):
		target = VOLEY_ESPACIO_DEFAULT
	else:
		target = VOLEY_ESPACIO_DEFAULT
	if frappe.db.exists("Espacio", target):
		return target
	return None


def resolve_espacio(partido: FixturePartido) -> str | None:
	"""Resuelve nombre de Espacio; None si no se puede mapear."""
	if partido.localia != LOCALIA_LOCAL:
		return None
	if partido.espacio:
		mapped = map_espacio(partido.espacio) or partido.espacio.strip()
		if frappe.db.exists("Espacio", mapped):
			return mapped
		return None
	if partido.source == ORIGIN_FMV_VOLEY:
		return resolve_espacio_fmv(partido)
	# FeBAMBA / basquet sin espacio explícito → Cancha 3.
	if partido.source == ORIGIN_FEBAMBA_GES and frappe.db.exists(
		"Espacio", BASQUET_ESPACIO_DEFAULT
	):
		return BASQUET_ESPACIO_DEFAULT
	return None

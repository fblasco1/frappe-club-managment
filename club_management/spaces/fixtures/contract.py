"""Contrato tipado para payloads de fixture / partido."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ORIGIN_FEBAMBA_GES = "febamba_ges"
ORIGIN_FMV_VOLEY = "fmv_voley"
ORIGIN_LIGA_EXCEL = "liga_excel"
ORIGIN_MANUAL = "manual"

LOCALIA_LOCAL = "local"
LOCALIA_VISITANTE = "visitante"


@dataclass
class FixturePartido:
	"""Partido normalizado listo para upsert en Reserva Espacio."""

	source: str
	external_id: str
	fecha: str  # ISO YYYY-MM-DD
	hora_desde: str  # HH:MM:SS
	hora_hasta: str  # HH:MM:SS
	categoria: str = ""
	tira: str = ""
	rival: str = ""
	localia: str = LOCALIA_LOCAL
	direccion: str = ""
	resultado: str = ""
	espacio: str | None = None
	motivo: str = ""
	equipo: str = ""

	@classmethod
	def from_mapping(cls, raw: dict[str, Any]) -> FixturePartido:
		"""Parsea dict del contrato JSON o fila CSV/Excel normalizada."""
		source = (raw.get("source") or raw.get("origen") or ORIGIN_MANUAL).strip()
		external_id = str(
			raw.get("external_id") or raw.get("id_externo") or raw.get("ID_PARTIDO") or ""
		).strip()
		espacio_raw = raw.get("espacio") if "espacio" in raw else raw.get("ESPACIO")
		return cls(
			source=source,
			external_id=external_id,
			fecha=str(raw.get("fecha") or raw.get("FECHA") or "").strip(),
			hora_desde=str(raw.get("hora_desde") or raw.get("hora") or raw.get("HORA") or "").strip(),
			hora_hasta=str(raw.get("hora_hasta") or raw.get("HORA_HASTA") or "").strip(),
			categoria=str(raw.get("categoria") or raw.get("CATEGORIA") or "").strip(),
			tira=str(raw.get("tira") or raw.get("TIRA") or "").strip(),
			rival=str(raw.get("rival") or raw.get("RIVAL") or "").strip(),
			localia=str(raw.get("localia") or raw.get("LOCALIA") or "").strip(),
			direccion=str(raw.get("direccion") or raw.get("DIRECCION") or "").strip(),
			resultado=str(raw.get("resultado") or raw.get("RESULTADO") or "").strip(),
			espacio=None if espacio_raw is None else str(espacio_raw).strip() or None,
			motivo=str(raw.get("motivo") or raw.get("MOTIVO") or "").strip(),
			equipo=str(raw.get("equipo") or raw.get("EQUIPO") or "").strip(),
		)


@dataclass
class FixtureImportReport:
	creados: int = 0
	actualizados: int = 0
	cancelados: int = 0
	omitidos: list[str] = field(default_factory=list)
	errores: list[str] = field(default_factory=list)
	superposiciones: list[str] = field(default_factory=list)

	def as_dict(self) -> dict[str, Any]:
		return {
			"creados": self.creados,
			"actualizados": self.actualizados,
			"cancelados": self.cancelados,
			"omitidos": self.omitidos,
			"errores": self.errores,
			"superposiciones": self.superposiciones,
		}

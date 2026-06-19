"""Normalización y clasificación de teléfonos (padrón legacy y formularios)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

TELEFONO_MIN_DIGITOS_VALIDO = 6
TELEFONO_UMBRAL_CELULAR = 10

TipoTelefono = Literal["Celular", "Fijo"]


@dataclass(frozen=True)
class TelefonoParseado:
	numero: str
	tipo: TipoTelefono


def parsear_telefono(numero_crudo: str | None) -> TelefonoParseado | None:
	"""Limpia y clasifica un teléfono según longitud (fijo histórico < 10 dígitos)."""
	digits = re.sub(r"\D", "", numero_crudo or "")
	if not digits:
		return None
	tipo: TipoTelefono = "Celular" if len(digits) >= TELEFONO_UMBRAL_CELULAR else "Fijo"
	return TelefonoParseado(numero=digits, tipo=tipo)


def mapear_telefonos_desde_fila(row: dict[str, str]) -> tuple[str, str, list[str]]:
	"""Mapea columnas CSV `teléfono` / `tel_movil` a fijo y móvil del DocType."""
	telefono_fijo = ""
	telefono_movil = ""
	invalidos: list[str] = []

	for col in ("teléfono", "tel_movil"):
		parsed = parsear_telefono(row.get(col))
		if parsed is None:
			continue
		if len(parsed.numero) < TELEFONO_MIN_DIGITOS_VALIDO:
			invalidos.append(parsed.numero)
			continue
		if parsed.tipo == "Celular":
			telefono_movil = parsed.numero
		else:
			telefono_fijo = parsed.numero

	return telefono_fijo, telefono_movil, invalidos

"""Validaciones compartidas del módulo `Members`.

`validate_ficha_medica` es el helper canónico de validación de la ficha médica
para `Socio` y para el Web Form de `Solicitud de Asociación`. Vive en
`members/validations.py` para que ambas rutas usen exactamente la misma
política (MIME permitidos y tamaño máximo).
"""

from __future__ import annotations

import frappe
from frappe import _

MIMES_PERMITIDOS: frozenset[str] = frozenset(
	{"application/pdf", "image/jpeg", "image/png"}
)
TAMANO_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB


def validate_ficha_medica(
	*,
	file_url: str,
	mime_type: str,
	file_size_bytes: int,
) -> None:
	"""Valida MIME y tamaño de la ficha médica antes de adjuntarla al Socio."""
	if mime_type not in MIMES_PERMITIDOS:
		frappe.throw(
			_("Ficha médica: tipo de archivo {0} no permitido. Aceptados: PDF, JPEG o PNG.").format(
				mime_type
			)
		)

	if file_size_bytes > TAMANO_MAX_BYTES:
		frappe.throw(
			_("Ficha médica: el archivo excede el tamaño máximo de {0} MB.").format(
				TAMANO_MAX_BYTES // (1024 * 1024)
			)
		)

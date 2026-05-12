"""Validaciones compartidas del módulo `Members`.

Helpers reutilizables entre DocTypes, Web Forms y servicios:

- `validate_ficha_medica`: política canónica de MIME y tamaño de la ficha
  médica. La usan `Socio` y el Web Form de `Solicitud de Asociación` para
  garantizar la misma regla en Desk y portal.
- `enforce_mandatory_depends_on`: valida server-side las expresiones
  `mandatory_depends_on` declaradas en el JSON del DocType. Frappe v15
  solo las valida en JS (Desk); este helper cubre los inserts vía Python,
  REST y Web Form.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe import _

if TYPE_CHECKING:
	from frappe.model.document import Document

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


def enforce_mandatory_depends_on(doc: "Document") -> None:
	"""Valida server-side los `mandatory_depends_on` declarados en el DocType.

	Frappe v15 sólo evalúa `mandatory_depends_on` en JS (Desk vía `save.js`
	y `layout.js`). Server-side los inserts por `frappe.get_doc(...).insert()`,
	API REST y Web Form **no** disparan `MandatoryError` para esos campos.

	Este helper recorre `doc.meta.fields`, evalúa cada expresión
	`mandatory_depends_on` con `frappe.safe_eval` pasando `doc` en el
	contexto, y dispara `frappe.MandatoryError` con la lista agregada de
	campos faltantes. Si la expresión no compila / lanza excepción, se
	considera no disparada (degradación segura: no se exige el campo).

	Se usa típicamente desde el `validate()` del controller:

	    def validate(self) -> None:
	        enforce_mandatory_depends_on(self)
	"""
	missing_labels: list[str] = []
	for df in doc.meta.fields:
		expr = (df.mandatory_depends_on or "").strip()
		if not expr:
			continue
		if expr.startswith("eval:"):
			expr = expr[len("eval:") :]
		try:
			triggered = bool(frappe.safe_eval(expr, None, {"doc": doc}))
		except Exception:
			triggered = False
		if not triggered:
			continue
		if not doc.get(df.fieldname):
			missing_labels.append(df.label or df.fieldname)

	if missing_labels:
		frappe.throw(
			_("Faltan campos obligatorios: {0}").format(", ".join(missing_labels)),
			exc=frappe.MandatoryError,
		)

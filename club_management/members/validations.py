"""Validaciones compartidas del módulo `Members`.

Helpers reutilizables entre DocTypes, Web Forms y servicios:

- `validate_ficha_medica`: política canónica de MIME y tamaño de la ficha
  médica. La usan `Socio` y el Web Form de `Solicitud de Asociación` para
  garantizar la misma regla en Desk y portal.
- `validate_ficha_medica_from_url`: variante que resuelve el `File` por
  URL, detecta el MIME real con magic numbers (anti-spoofing por
  extensión) y delega a `validate_ficha_medica`. Pensado para el endpoint
  público `submit_solicitud` que recibe URLs de archivos subidos
  previamente por Guest vía `frappe.client.upload_file`.
- `enforce_mandatory_depends_on`: valida server-side las expresiones
  `mandatory_depends_on` declaradas en el JSON del DocType. Frappe v15
  solo las valida en JS (Desk); este helper cubre los inserts vía Python,
  REST y Web Form.
"""

from __future__ import annotations

import os
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


def _detect_mime_by_magic_numbers(head: bytes) -> str:
	"""Detecta MIME por los primeros bytes del archivo (anti-spoofing).

	Sólo reconoce los formatos aceptados por la política de ficha médica
	(`MIMES_PERMITIDOS`); cualquier otro devuelve
	`application/octet-stream`, que `validate_ficha_medica` rechaza.

	No depende de `python-magic`/`libmagic`: la inspección es nativa y
	suficiente para PDF, JPEG y PNG.
	"""
	if head.startswith(b"%PDF"):
		return "application/pdf"
	if head.startswith(b"\xff\xd8\xff"):
		return "image/jpeg"
	if head.startswith(b"\x89PNG\r\n\x1a\n"):
		return "image/png"
	return "application/octet-stream"


def validate_ficha_medica_from_url(file_url: str) -> None:
	"""Valida MIME + tamaño de la ficha médica a partir de su `file_url`.

	Pensado para el endpoint público `submit_solicitud` y cualquier flujo
	que reciba el archivo ya subido vía `frappe.client.upload_file`.

	Flujo:
	1. Resuelve el `File` doc por `file_url`.
	2. Obtiene el path local con `get_full_path()`.
	3. Lee los primeros 8 bytes y detecta el MIME por magic numbers.
	4. Lee el tamaño con `os.path.getsize`.
	5. Delega a `validate_ficha_medica` (política única para Desk y portal).
	"""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_path = file_doc.get_full_path()

	with open(file_path, "rb") as f:
		head = f.read(8)
	mime_type = _detect_mime_by_magic_numbers(head)

	file_size_bytes = os.path.getsize(file_path)

	validate_ficha_medica(
		file_url=file_url,
		mime_type=mime_type,
		file_size_bytes=file_size_bytes,
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

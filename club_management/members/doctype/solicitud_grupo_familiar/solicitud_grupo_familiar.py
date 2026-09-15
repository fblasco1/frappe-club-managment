"""Controller del DocType `Solicitud Grupo Familiar`.

Agrupa las `Solicitud Asociacion` que llegaron en un mismo trámite público
(wizard multi-persona del portal). El token de seguimiento es único para todo
el trámite: el solicitante consulta el estado de la familia completa con él.

Spec: `club_management/specs/portal_alta_grupo_familiar.md`
"""

from __future__ import annotations

import uuid

from frappe.model.document import Document


class SolicitudGrupoFamiliar(Document):
	"""Trámite de alta familiar (padre de N `Solicitud Asociacion`)."""

	def before_insert(self) -> None:
		if not self.token_seguimiento:
			self.token_seguimiento = uuid.uuid4().hex

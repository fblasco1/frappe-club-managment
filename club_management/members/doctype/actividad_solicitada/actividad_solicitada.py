"""Child table `Actividad Solicitada`.

Actividades elegidas por una persona en el wizard público de alta.

Spec: `club_management/specs/portal_alta_grupo_familiar.md`
"""

from __future__ import annotations

from frappe.model.document import Document


class ActividadSolicitada(Document):
	"""Fila de actividad elegida en el alta pública."""

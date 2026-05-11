"""Controller del Child DocType `Miembro de Grupo Familiar`.

Child de Socios miembros del Grupo Familiar. Sin lógica propia en Sprint 0:
las validaciones cross-DocType viven en el controller de `Grupo Familiar`.
"""

from __future__ import annotations

from frappe.model.document import Document


class MiembrodeGrupoFamiliar(Document):
	pass

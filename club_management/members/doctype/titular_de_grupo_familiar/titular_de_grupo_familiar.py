"""Controller del Child DocType `Titular de Grupo Familiar`.

Child polimórfica de titulares del `Grupo Familiar` (puede apuntar a `Socio` o
a `Tutor No Socio` vía Dynamic Link). Sin lógica propia en Sprint 0: las
invariantes (al menos un principal activo, mayor de edad, unicidad cross-grupo)
viven en el controller de `Grupo Familiar`.
"""

from __future__ import annotations

from frappe.model.document import Document


class TitulardeGrupoFamiliar(Document):
	pass

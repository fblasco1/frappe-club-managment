"""Controller del DocType `Solicitud Asociacion` (Sprint 1 Commit 1).

Cubre la lógica mínima necesaria para pasar a verde los tests del commit 1:

- `before_insert`: autogenera `token_seguimiento` con `uuid.uuid4().hex` si
  no fue provisto explícitamente. El token sirve para que el solicitante
  consulte el estado de su solicitud (commit 2) y para autorizar el
  endpoint público de corrección (commit 5).
- `validate`: refuerza server-side los `mandatory_depends_on` declarados
  en el JSON (Frappe v15 sólo los valida en JS de Desk, ver
  `members/validations.py::enforce_mandatory_depends_on`).

El resto de la lógica (validación de transiciones del workflow, escape XSS
en `motivos_rechazo`, validación MIME de `ficha_medica`, sincronización con
`Socio`, auditoría server-side por transición, etc.) se agrega en commits
posteriores del Sprint 1.

Nota sobre el `name` técnico:
    El DocType se llama `Solicitud Asociacion` (sin tilde y sin "de") para
    mantener el slug ASCII puro y evitar problemas de encoding entre
    plataformas. El label visible en Desk se traduce a "Solicitud de
    Asociación" vía i18n en un sprint dedicado. El concepto de negocio
    sigue siendo "Solicitud de Asociación".

Spec: `club_management/specs/solicitud_asociacion_publica.md`.
"""

from __future__ import annotations

import uuid

from frappe.model.document import Document

from club_management.members.validations import enforce_mandatory_depends_on


class SolicitudAsociacion(Document):
    """DocType `Solicitud Asociacion` (Sprint 1)."""

    def before_insert(self) -> None:
        if not self.token_seguimiento:
            self.token_seguimiento = uuid.uuid4().hex

    def validate(self) -> None:
        enforce_mandatory_depends_on(self)

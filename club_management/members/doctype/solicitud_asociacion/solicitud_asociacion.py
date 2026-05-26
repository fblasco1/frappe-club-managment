"""Controller del DocType `Solicitud Asociacion` (Sprint 1).

Cubre la lógica mínima necesaria para pasar a verde los tests del commit 1:

- `before_insert`: autogenera `token_seguimiento` con `uuid.uuid4().hex` si
  no fue provisto explícitamente. El token sirve para que el solicitante
  consulte el estado de su solicitud (commit 2) y para autorizar el
  endpoint público de corrección (commit 5).
- `validate`: refuerza server-side los `mandatory_depends_on` declarados
  en el JSON (Frappe v15 sólo los valida en JS de Desk, ver
  `members/validations.py::enforce_mandatory_depends_on`).

Commit 3 añade:

- `before_save`: auditoría de transiciones (`validado_por/en`, etc.) cuando
  cambia `workflow_state`.
- `validate`: exige `motivos_rechazo` al transicionar a `Rechazada`.

El resto de la lógica (validación de transiciones del workflow, escape XSS
en `motivos_rechazo`, validación MIME de `ficha_medica`, sincronización con
`Socio`, etc.) se agrega en commits posteriores del Sprint 1.

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

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from club_management.members.validations import enforce_mandatory_depends_on
from club_management.members.workflow.solicitud_asociacion_workflow import (
    STATE_RECHAZADA,
    STATE_REQUIERE_CORRECCION,
    STATE_VALIDADA,
)


class SolicitudAsociacion(Document):
    """DocType `Solicitud Asociacion` (Sprint 1)."""

    def before_insert(self) -> None:
        if not self.token_seguimiento:
            self.token_seguimiento = uuid.uuid4().hex

    def before_save(self) -> None:
        previous = self.get_doc_before_save()
        if not previous:
            return

        prev_state = previous.get("workflow_state")
        new_state = self.workflow_state
        if prev_state == new_state:
            return

        user = frappe.session.user
        now = now_datetime()

        if new_state == STATE_VALIDADA:
            self.validado_por = user
            self.validado_en = now
        elif new_state == STATE_RECHAZADA:
            self.rechazado_por = user
            self.rechazado_en = now
        elif new_state == STATE_REQUIERE_CORRECCION:
            self.correccion_solicitada_por = user
            self.correccion_solicitada_en = now

    def validate(self) -> None:
        enforce_mandatory_depends_on(self)
        previous = self.get_doc_before_save()
        if not previous:
            return

        if (
            previous.get("workflow_state") != self.workflow_state
            and self.workflow_state == STATE_RECHAZADA
            and not (self.motivos_rechazo or "").strip()
        ):
            frappe.throw(_("motivos_rechazo es obligatorio"), frappe.ValidationError)

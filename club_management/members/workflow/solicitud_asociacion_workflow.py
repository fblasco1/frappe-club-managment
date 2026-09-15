"""Workflow Desk de `Solicitud Asociacion` (Sprint 1 Commit 3).

Instala de forma idempotente el Workflow con estados y transiciones definidos
en `specs/solicitud_asociacion_publica.md`.

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commit 3).
"""

from __future__ import annotations

import frappe
from frappe import _

WORKFLOW_NAME = "Solicitud Asociacion"
DOCUMENT_TYPE = "Solicitud Asociacion"
WORKFLOW_STATE_FIELD = "workflow_state"

STATE_PENDIENTE = "Pendiente"
STATE_REQUIERE_CORRECCION = "Requiere Corrección"
STATE_VALIDADA = "Validada"

WORKFLOW_STATES = (
	STATE_PENDIENTE,
	STATE_REQUIERE_CORRECCION,
	STATE_VALIDADA,
)

ACTION_SOLICITAR_CORRECCION = "Solicitar Corrección"
ACTION_REENVIAR = "Reenviar"
ACTION_VALIDAR = "Validar"

WORKFLOW_ACTIONS = (
	ACTION_SOLICITAR_CORRECCION,
	ACTION_REENVIAR,
	ACTION_VALIDAR,
)

ROLE_SECRETARIA = "Secretaria"

def ensure_solicitud_asociacion_workflow() -> None:
	"""Crea o reactiva el Workflow de Solicitud Asociacion."""
	_ensure_document_type_exists()
	_ensure_role_secretaria()
	_ensure_workflow_states()
	_ensure_workflow_actions()

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		workflow = frappe.get_doc("Workflow", WORKFLOW_NAME)
		changed = _sync_workflow_definition(workflow)
		if not workflow.is_active:
			workflow.is_active = 1
			changed = True
		if changed:
			workflow.save(ignore_permissions=True)
		frappe.clear_cache(doctype=DOCUMENT_TYPE)
		return

	workflow = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW_NAME,
			"document_type": DOCUMENT_TYPE,
			"workflow_state_field": WORKFLOW_STATE_FIELD,
			"is_active": 1,
			"send_email_alert": 0,
		}
	)
	for state in WORKFLOW_STATES:
		workflow.append(
			"states",
			{
				"state": state,
				"doc_status": "0",
				"allow_edit": ROLE_SECRETARIA,
			},
		)

	transitions = (
		(STATE_PENDIENTE, ACTION_SOLICITAR_CORRECCION, STATE_REQUIERE_CORRECCION),
		(STATE_REQUIERE_CORRECCION, ACTION_REENVIAR, STATE_PENDIENTE),
		(STATE_PENDIENTE, ACTION_VALIDAR, STATE_VALIDADA),
		(STATE_REQUIERE_CORRECCION, ACTION_VALIDAR, STATE_VALIDADA),
	)
	for state, action, next_state in transitions:
		workflow.append(
			"transitions",
			_workflow_transition_row(state, action, next_state),
		)

	workflow.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=DOCUMENT_TYPE)


def _sync_workflow_definition(workflow) -> bool:
	"""Mantiene estados/transiciones alineados al flujo actual.

	En Sprint 1 cierre se eliminó el estado terminal `Rechazada` y la acción
	`Rechazar`. En sitios ya migrados puede quedar en el Doc de Workflow: este
	sync lo remueve para que Desk no lo ofrezca.
	"""
	changed = False

	expected_states = set(WORKFLOW_STATES)
	expected_actions = set(WORKFLOW_ACTIONS)

	# Filtrar estados extra (p. ej. "Rechazada")
	kept_states = [row for row in workflow.states if row.state in expected_states]
	if len(kept_states) != len(workflow.states):
		workflow.set("states", kept_states)
		changed = True

	# Filtrar transiciones extra (p. ej. acción "Rechazar")
	kept_transitions = [row for row in workflow.transitions if row.action in expected_actions]
	if len(kept_transitions) != len(workflow.transitions):
		workflow.set("transitions", kept_transitions)
		changed = True

	# Asegurar que existan las transiciones esperadas (idempotente)
	existing = {(t.state, t.action, t.next_state) for t in workflow.transitions}
	expected = {
		(STATE_PENDIENTE, ACTION_SOLICITAR_CORRECCION, STATE_REQUIERE_CORRECCION),
		(STATE_REQUIERE_CORRECCION, ACTION_REENVIAR, STATE_PENDIENTE),
		(STATE_PENDIENTE, ACTION_VALIDAR, STATE_VALIDADA),
		(STATE_REQUIERE_CORRECCION, ACTION_VALIDAR, STATE_VALIDADA),
	}
	missing = expected - existing
	for state, action, next_state in sorted(missing):
		workflow.append("transitions", _workflow_transition_row(state, action, next_state))
		changed = True

	return changed


def _workflow_transition_row(state: str, action: str, next_state: str) -> dict[str, object]:
	row: dict[str, object] = {
		"state": state,
		"action": action,
		"next_state": next_state,
		"allowed": ROLE_SECRETARIA,
		"allow_self_approval": 1,
	}
	return row


def _ensure_document_type_exists() -> None:
	"""Garantiza que `Solicitud Asociacion` esté en `tabDocType` antes del Workflow."""
	if frappe.db.exists("DocType", DOCUMENT_TYPE):
		return

	installed = frappe.get_installed_apps()
	if "club_management" not in installed:
		frappe.throw(
			_(
				"La app `club_management` no está instalada en el sitio {0}. "
				"Ejecutá: bench --site {0} install-app club_management && bench migrate"
			).format(frappe.local.site),
			frappe.ValidationError,
		)

	from frappe.model.sync import sync_for

	sync_for("club_management", force=0)
	frappe.clear_cache(doctype="DocType")

	if not frappe.db.exists("DocType", DOCUMENT_TYPE):
		frappe.throw(
			_(
				"DocType `{0}` no encontrado tras sincronizar `club_management`. "
				"Ejecutá bench migrate en el sitio {1}."
			).format(DOCUMENT_TYPE, frappe.local.site),
			frappe.ValidationError,
		)


def _ensure_role_secretaria() -> None:
	if frappe.db.exists("Role", ROLE_SECRETARIA):
		return
	frappe.get_doc(
		{"doctype": "Role", "role_name": ROLE_SECRETARIA, "desk_access": 1}
	).insert(ignore_permissions=True)


def _ensure_workflow_states() -> None:
	for state in WORKFLOW_STATES:
		if frappe.db.exists("Workflow State", state):
			continue
		frappe.get_doc(
			{"doctype": "Workflow State", "workflow_state_name": state}
		).insert(ignore_permissions=True)


def _ensure_workflow_actions() -> None:
	for action in WORKFLOW_ACTIONS:
		if frappe.db.exists("Workflow Action Master", action):
			continue
		frappe.get_doc(
			{"doctype": "Workflow Action Master", "workflow_action_name": action}
		).insert(ignore_permissions=True)

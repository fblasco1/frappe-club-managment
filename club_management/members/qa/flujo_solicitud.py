"""Runner del flujo E2E Solicitud de Asociación (API, sin navegador).

Usado por `test_flujo_solicitud_completo.py` (CI) y `run_supervised.py` (Q&A).
Spec: `specs/solicitud_asociacion_publica.md` — «Flujo E2E — CI y Q&A supervisado».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import frappe
from frappe.model.workflow import apply_workflow

from club_management.activities.services.inscripcion_socio import confirmar_inscripcion_post_pago
from club_management.members.api.solicitud_publica import (
	_actualizar_solicitud_impl,
	_consultar_solicitud_impl,
	_confirmar_pago_stub_impl,
	_submit_solicitud_impl,
)
from club_management.members.services.solicitud_tokens import sign_pago_token
from club_management.members.test_helpers import (
	MINIMAL_VALID_PDF,
	make_secretaria_user,
	make_solicitud_asociacion_payload,
	make_test_file,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_SOLICITAR_CORRECCION,
	ACTION_VALIDAR,
	STATE_PENDIENTE,
	STATE_REQUIERE_CORRECCION,
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)

StepCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class FlujoSolicitudResult:
	"""Estado acumulado al finalizar el flujo."""

	token_seguimiento: str
	solicitud_name: str
	socio_name: str
	user_name: str
	grupo_name: str
	pago_token: str
	steps: list[dict[str, Any]] = field(default_factory=list)


class FlujoSolicitudRunner:
	"""Orquesta el flujo de negocio vía API (equivalente al testeo manual en Desk)."""

	def __init__(
		self,
		*,
		dni: str = "80999001",
		email: str = "flujo.qa@example.com",
		on_step: StepCallback | None = None,
		patch_validacion_email: bool = True,
	) -> None:
		self.dni = dni
		self.email = email
		self.on_step = on_step
		self.patch_validacion_email = patch_validacion_email
		ensure_solicitud_asociacion_workflow()

	def _emit(self, step_id: str, evidence: dict[str, Any]) -> None:
		if self.on_step:
			self.on_step(step_id, evidence)

	def _payload_alta_publica(self, *, dni: str, email: str) -> dict[str, Any]:
		"""Payload para `submit_solicitud` con ficha médica real en disco."""
		payload = make_solicitud_asociacion_payload(dni=dni, email=email)
		payload["ficha_medica"] = make_test_file(
			f"flujo_qa_{dni}.pdf",
			MINIMAL_VALID_PDF,
		)
		return payload

	def run_happy_path_adulto(self) -> FlujoSolicitudResult:
		"""Alta → consulta → validar → pago stub → Socio Activo."""
		steps: list[dict[str, Any]] = []

		payload = self._payload_alta_publica(dni=self.dni, email=self.email)
		alta = _submit_solicitud_impl(payload)
		steps.append({"step": "alta_publica", "result": alta})
		self._emit("alta_publica", alta)

		token = alta["token_seguimiento"]
		consulta = _consultar_solicitud_impl(token)
		if consulta["workflow_state"] != STATE_PENDIENTE:
			frappe.throw(f"Se esperaba Pendiente, obtuvo {consulta['workflow_state']}")
		steps.append({"step": "consultar", "result": consulta})
		self._emit("consultar", consulta)

		solicitud_name = frappe.db.get_value(
			"Solicitud Asociacion", {"token_seguimiento": token}, "name"
		)
		if not solicitud_name:
			frappe.throw("Solicitud no encontrada tras alta")

		secretaria = make_secretaria_user()
		frappe.set_user(secretaria)
		doc = frappe.get_doc("Solicitud Asociacion", solicitud_name)
		try:
			if self.patch_validacion_email:
				from unittest.mock import patch

				with patch(
					"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
				):
					apply_workflow(doc, ACTION_VALIDAR)
			else:
				apply_workflow(doc, ACTION_VALIDAR)
		finally:
			frappe.set_user("Administrator")

		doc.reload()
		if doc.workflow_state != STATE_VALIDADA:
			frappe.throw(f"Validar falló: estado {doc.workflow_state}")
		if not doc.socio_generado:
			frappe.throw("socio_generado vacío tras Validar")

		socio = frappe.get_doc("Socio", doc.socio_generado)
		if socio.estado != "Pendiente de Pago":
			frappe.throw(f"Socio debería estar Pendiente de Pago, está {socio.estado}")

		validar_evidence = {
			"workflow_state": doc.workflow_state,
			"socio_generado": doc.socio_generado,
			"user_generado": doc.user_generado,
			"grupo_familiar_generado": doc.grupo_familiar_generado,
			"socio_estado": socio.estado,
		}
		steps.append({"step": "validar", "result": validar_evidence})
		self._emit("validar", validar_evidence)

		pago_token = sign_pago_token(doc.name)
		pago = _confirmar_pago_stub_impl(pago_token)
		socio.reload()
		inscripcion = confirmar_inscripcion_post_pago(doc.name, [])
		socio.reload()
		if socio.estado != "Activo":
			frappe.throw(f"Socio debería estar Activo, está {socio.estado}")

		pago_evidence = {
			"pago": pago,
			"inscripcion": inscripcion,
			"socio_estado": socio.estado,
		}
		steps.append({"step": "pago_stub", "result": pago_evidence})
		self._emit("pago_stub", pago_evidence)

		return FlujoSolicitudResult(
			token_seguimiento=token,
			solicitud_name=doc.name,
			socio_name=doc.socio_generado,
			user_name=doc.user_generado or "",
			grupo_name=doc.grupo_familiar_generado or "",
			pago_token=pago_token,
			steps=steps,
		)

	def run_path_con_correccion(self) -> FlujoSolicitudResult:
		"""Alta → corrección → reenvío → validar → pago."""
		steps: list[dict[str, Any]] = []

		corr_email = f"flujo.corr.{self.dni}@example.com"
		payload = self._payload_alta_publica(dni=self.dni, email=corr_email)
		alta = _submit_solicitud_impl(payload)
		token = alta["token_seguimiento"]
		solicitud_name = frappe.db.get_value(
			"Solicitud Asociacion", {"token_seguimiento": token}, "name"
		)
		steps.append({"step": "alta_publica", "result": alta})
		self._emit("alta_publica", alta)

		secretaria = make_secretaria_user()
		frappe.set_user(secretaria)
		doc = frappe.get_doc("Solicitud Asociacion", solicitud_name)
		apply_workflow(doc, ACTION_SOLICITAR_CORRECCION)
		doc.reload()
		if doc.workflow_state != STATE_REQUIERE_CORRECCION:
			frappe.throw("Se esperaba Requiere Corrección")
		frappe.set_user("Administrator")

		correccion = _actualizar_solicitud_impl(
			token, {"telefono_movil": "+549119998877"}
		)
		doc.reload()
		if doc.workflow_state != STATE_PENDIENTE:
			frappe.throw("Tras corrección debería estar Pendiente")
		steps.append({"step": "correccion", "result": correccion})
		self._emit("correccion", correccion)

		frappe.set_user(secretaria)
		doc = frappe.get_doc("Solicitud Asociacion", solicitud_name)
		try:
			if self.patch_validacion_email:
				from unittest.mock import patch

				with patch(
					"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
				):
					apply_workflow(doc, ACTION_VALIDAR)
			else:
				apply_workflow(doc, ACTION_VALIDAR)
		finally:
			frappe.set_user("Administrator")

		doc.reload()
		pago_token = sign_pago_token(doc.name)
		_confirmar_pago_stub_impl(pago_token)
		confirmar_inscripcion_post_pago(doc.name, [])
		socio = frappe.get_doc("Socio", doc.socio_generado)
		if socio.estado != "Activo":
			frappe.throw("Socio no quedó Activo")

		self._emit(
			"fin",
			{"socio_estado": socio.estado, "telefono_movil": doc.telefono_movil},
		)

		return FlujoSolicitudResult(
			token_seguimiento=token,
			solicitud_name=doc.name,
			socio_name=doc.socio_generado,
			user_name=doc.user_generado or "",
			grupo_name=doc.grupo_familiar_generado or "",
			pago_token=pago_token,
			steps=steps,
		)

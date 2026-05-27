"""Endpoints públicos del flujo `Solicitud Asociacion` (Sprint 1).

Expone el endpoint custom `submit_solicitud` whitelisted con
`allow_guest=True` que reemplaza al built-in `frappe.www.web_form.accept`
para tener control total sobre rate-limit, persistencia server-side de
`enviado_desde_ip`, validación de adjuntos por magic numbers y filtrado
de campos del sistema.

Ver `specs/solicitud_asociacion_publica.md`, sección
"Decisión sobre el endpoint público del Web Form".
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from club_management.members.services.actividades_portal import list_actividades_asociacion
from club_management.members.services.google_places import get_places_config_for_portal
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.services.solicitud_tokens import (
    get_solicitud_by_seguimiento_token,
    verify_pago_token,
)
from club_management.members.validations import validate_ficha_medica_from_url
from club_management.members.workflow.solicitud_asociacion_workflow import (
    STATE_PENDIENTE,
    STATE_REQUIERE_CORRECCION,
    STATE_VALIDADA,
)

# Campos que el cliente Guest NO puede setear desde el payload del Web Form.
# El servidor los gestiona internamente (workflow, token, IP, auditoría,
# referencias generadas al validar la solicitud). Cualquier intento de
# override desde el payload se filtra silenciosamente antes del insert.
_CAMPOS_BLOQUEADOS_DESDE_PAYLOAD: frozenset[str] = frozenset(
    {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
        "workflow_state",
        "token_seguimiento",
        "enviado_desde_ip",
        "socio_generado",
        "user_generado",
        "grupo_familiar_generado",
        "validado_por",
        "validado_en",
        "rechazado_por",
        "rechazado_en",
        "correccion_solicitada_por",
        "correccion_solicitada_en",
        "motivos_rechazo",
        "motivo_rechazo",
        "motivo_correccion",
    }
)

# Campos que Guest puede actualizar vía `actualizar_solicitud` (corrección).
_CAMPOS_EDITABLES_CORRECCION: frozenset[str] = frozenset(
    {
        "nombre",
        "apellido",
        "dni",
        "nacionalidad",
        "fecha_nacimiento",
        "genero",
        "categoria_solicitada",
        "email",
        "telefono",
        "calle",
        "localidad",
        "provincia",
        "codigo_postal",
        "dni_frente",
        "dni_dorso",
        "foto_perfil",
        "ficha_medica",
        "comprobante_domicilio",
        "actividad_interes",
        "tiene_familiares_socios",
        "familiares_existentes_dnis",
        "dni_tutor",
        "nombre_tutor",
        "apellido_tutor",
        "fecha_nacimiento_tutor",
        "nacionalidad_tutor",
        "genero_tutor",
        "email_tutor",
        "telefono_tutor",
        "calle_tutor",
        "localidad_tutor",
        "provincia_tutor",
        "codigo_postal_tutor",
        "rol_tutor",
        "dni_frente_tutor",
        "dni_dorso_tutor",
        "foto_perfil_tutor",
    }
)


def _resolve_client_ip() -> str:
    """Devuelve la IP real del cliente respetando `X-Forwarded-For`.

    Cuando la app corre detrás de un proxy (nginx, traefik, CDN) el
    `request.remote_addr` apunta al proxy, no al cliente final. La IP
    real se publica en el header `X-Forwarded-For` como una lista
    `cliente, proxy1, proxy2, ...`; el primer elemento es el cliente.

    Fallback: si no hay XFF (request directo sin proxy o testing local
    con cliente Werkzeug), se usa `request.remote_addr`. Si tampoco hay
    request (CLI, scheduler, background job), devuelve `""`.
    """
    request = getattr(frappe.local, "request", None)
    if not request:
        return ""

    headers = getattr(request, "headers", None) or {}
    xff = ""
    if headers:
        try:
            xff = headers.get("X-Forwarded-For", "") or ""
        except Exception:
            xff = ""

    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first

    return getattr(request, "remote_addr", None) or ""


def _submit_solicitud_impl(data: Any) -> dict[str, Any]:
    """Implementación interna de `submit_solicitud`, sin decoradores HTTP.

    Esta función contiene la lógica de negocio completa: parseo del
    payload, filtrado de campos sistema, validación de ficha médica por
    magic numbers, resolución de IP del cliente e `insert` del
    documento. El wrapper público `submit_solicitud` agrega
    `@frappe.whitelist(allow_guest=True)` y
    `@frappe.rate_limiter.rate_limit(...)` para el ciclo HTTP, pero esos
    decoradores requieren un request real (`frappe.local.request_ip`
    seteado) y un store Redis para el contador. Los unit tests llaman
    directamente a `_submit_solicitud_impl` para validar la lógica de
    negocio sin acoplarse a esos requisitos del runtime HTTP; los
    escenarios E2E del rate-limit y de Guest+Whitelist se cubren como
    integration tests separados en un sprint posterior.

    Ver `specs/solicitud_asociacion_publica.md`, sección
    "Decisión sobre el endpoint público del Web Form".

    Comportamiento:
    - El payload se filtra contra `_CAMPOS_BLOQUEADOS_DESDE_PAYLOAD`:
      `workflow_state`, `token_seguimiento`, `enviado_desde_ip`,
      auditoría y referencias generadas no pueden venir del cliente.
    - `ficha_medica` se valida (MIME + tamaño) leyendo el archivo del
      disco con detección por magic numbers (no por extensión).
    - El documento se crea con `insert(ignore_permissions=True)` porque
      el rol Guest NO tiene DocPerm de creación sobre `Solicitud
      Asociacion`; el único camino legítimo de creación es este endpoint.
    - La respuesta NO expone el `name` del documento (anti-enumeración):
      solo `status` y `token_seguimiento`, que el solicitante usará
      para consultar el estado.

    Returns:
        `{"status": "ok", "token_seguimiento": "<hex>"}`.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            frappe.throw(_("Payload inválido (JSON malformado)."), exc=frappe.ValidationError)

    if not isinstance(data, dict):
        frappe.throw(_("Payload inválido: se esperaba un objeto."), exc=frappe.ValidationError)

    payload: dict[str, Any] = {
        k: v for k, v in data.items() if k not in _CAMPOS_BLOQUEADOS_DESDE_PAYLOAD
    }
    _normalize_legacy_address_fields(payload)
    payload["doctype"] = "Solicitud Asociacion"

    ficha_url = payload.get("ficha_medica")
    if ficha_url:
        validate_ficha_medica_from_url(ficha_url)

    payload["enviado_desde_ip"] = _resolve_client_ip()

    doc = frappe.get_doc(payload)
    doc.insert(ignore_permissions=True)

    return {
        "status": "ok",
        "token_seguimiento": doc.token_seguimiento,
    }


def _normalize_legacy_address_fields(payload: dict[str, Any]) -> None:
	"""Acepta `domicilio` / `domicilio_tutor` legacy del cliente anterior."""
	if payload.get("domicilio") and not payload.get("calle"):
		payload["calle"] = payload.pop("domicilio")
	elif "domicilio" in payload:
		payload.pop("domicilio", None)
	if payload.get("domicilio_tutor") and not payload.get("calle_tutor"):
		payload["calle_tutor"] = payload.pop("domicilio_tutor")
	elif "domicilio_tutor" in payload:
		payload.pop("domicilio_tutor", None)


@frappe.whitelist(allow_guest=True)
def get_places_config() -> dict[str, str | bool]:
	"""Devuelve si Google Places está habilitado y la API key (referrer-restricted)."""
	return get_places_config_for_portal()


@frappe.whitelist(allow_guest=True)
def get_actividades_asociacion() -> list[dict[str, str]]:
	"""Lista actividades para el desplegable del formulario público."""
	return list_actividades_asociacion()


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=600)
def submit_solicitud(data: Any) -> dict[str, Any]:
    """Endpoint público para crear una `Solicitud Asociacion`.

    Wrapper HTTP que aplica los decoradores de Frappe y delega la
    lógica a `_submit_solicitud_impl`. Recibe un payload (JSON string
    o dict) con los campos del solicitante y (cuando
    `categoria_solicitada == "Menor"`) del tutor. Los adjuntos
    (`foto_perfil`, `dni_frente`, `dni_dorso`, `ficha_medica`) deben
    haberse subido previamente con `frappe.client.upload_file`
    (`allow_guest=True`) y referenciarse como URLs `/files/...`.

    Decoradores aplicados (en orden de wrap, de adentro hacia afuera):
    - `@rate_limit(limit=5, seconds=600)`
      (`frappe.rate_limiter.rate_limit`): 5 requests cada 600 segundos
      por IP. `ip_based=True` (default) identifica al cliente por
      `frappe.local.request_ip` (la IP que Frappe deriva del request).
      Nuestro `_resolve_client_ip` aplica la lógica de
      `X-Forwarded-For` solo para persistir `enviado_desde_ip`
      server-side.
    - `@frappe.whitelist(allow_guest=True)`: expone el endpoint vía
      `/api/method/...` sin requerir autenticación. Guest NO tiene
      DocPerm sobre `Solicitud Asociacion`, así que este endpoint es
      el único camino legítimo de creación.

    Returns:
        `{"status": "ok", "token_seguimiento": "<hex>"}`.
    """
    return _submit_solicitud_impl(data)


def _consultar_solicitud_impl(token: str) -> dict[str, Any]:
	"""Consulta estado por `token_seguimiento` sin filtrar PII extra."""
	doc = get_solicitud_by_seguimiento_token(token)
	if not doc:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)

	result: dict[str, Any] = {
		"status": "ok",
		"workflow_state": doc.workflow_state,
		"creation": str(doc.creation),
	}
	if doc.workflow_state == "Rechazada" and doc.motivos_rechazo:
		result["motivos_rechazo"] = doc.motivos_rechazo
	return result


def _actualizar_solicitud_impl(token: str, data: Any) -> dict[str, Any]:
	"""Actualiza campos permitidos y reenvía a cola (`Pendiente`)."""
	doc = get_solicitud_by_seguimiento_token(token)
	if not doc or doc.workflow_state != STATE_REQUIERE_CORRECCION:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)

	if isinstance(data, str):
		try:
			data = json.loads(data)
		except json.JSONDecodeError as exc:
			frappe.throw(_("Payload inválido (JSON malformado)."), exc=frappe.ValidationError)

	if not isinstance(data, dict):
		frappe.throw(_("Payload inválido: se esperaba un objeto."), frappe.ValidationError)

	for key, value in data.items():
		if key in _CAMPOS_EDITABLES_CORRECCION:
			doc.set(key, value)

	if data.get("ficha_medica"):
		validate_ficha_medica_from_url(doc.get("ficha_medica"))

	doc.workflow_state = STATE_PENDIENTE
	doc.save(ignore_permissions=True)
	return {"status": "ok", "message": _("Solicitud actualizada y reenviada.")}


def _confirmar_pago_stub_impl(pago_token: str) -> dict[str, str]:
	"""Stub Sprint 1: marca el socio como `Activo` tras pago simulado."""
	solicitud_name = verify_pago_token(pago_token)
	if not solicitud_name:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)

	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if solicitud.workflow_state != STATE_VALIDADA or not solicitud.socio_generado:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)

	cambiar_estado(
		solicitud.socio_generado,
		"Activo",
		motivo="Pago stub Sprint 1",
	)
	return {"status": "ok"}


@frappe.whitelist(allow_guest=True)
def consultar_solicitud(token: str) -> dict[str, Any]:
	"""Endpoint público de consulta de estado por token."""
	return _consultar_solicitud_impl(token)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=600)
def actualizar_solicitud(token: str, data: Any) -> dict[str, Any]:
	"""Endpoint público de corrección/reenvío por token."""
	return _actualizar_solicitud_impl(token, data)


@frappe.whitelist(allow_guest=True)
def confirmar_pago_stub(token: str) -> dict[str, str]:
	"""Confirma pago simulado desde la página `/pago-stub`."""
	return _confirmar_pago_stub_impl(token)

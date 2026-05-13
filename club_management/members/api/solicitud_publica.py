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

from club_management.members.validations import validate_ficha_medica_from_url

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
        "motivo_rechazo",
        "motivo_correccion",
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

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe

from club_management.integrations.supervielle_api import SupervielleIntegrationError, _iter_json_values


class SupervielleWebhookAuthError(SupervielleIntegrationError):
    """El webhook no pudo autenticar el mensaje del banco."""


def validate_webhook_hash(payload: dict[str, Any], *, secret_key: str) -> None:
    received = (payload.get("hash") or "").strip()
    if not received:
        raise SupervielleWebhookAuthError("Falta hash en el webhook.")

    computed = hashlib.sha256(("".join(_iter_json_values(payload)) + secret_key).encode("utf-8")).hexdigest()
    if computed != received:
        raise SupervielleWebhookAuthError("Hash inválido en webhook.")


def _get_payload_from_request() -> dict[str, Any]:
    if hasattr(frappe, "request") and frappe.request:
        try:
            data = frappe.request.get_json(silent=True)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # fallback: query/form dict
    try:
        return dict(frappe.local.form_dict or {})
    except Exception:
        return {}


def _ack_ok(message: str = "OK") -> dict[str, Any]:
    frappe.local.response["http_status_code"] = 200
    return {"status": "ok", "message": message}


def _ack_forbidden(message: str) -> dict[str, Any]:
    frappe.local.response["http_status_code"] = 403
    return {"status": "forbidden", "message": message}


def _find_sales_invoice(reference: str) -> str | None:
    # Estrategia base: asumimos que `reference` es el `name` de Sales Invoice.
    # En una iteración siguiente se puede mapear `cod_trx` -> Sales Invoice vía un DocType de log.
    if frappe.db.exists("Sales Invoice", reference):
        return reference
    return None


def _payment_entry_already_exists(invoice_name: str) -> bool:
    # Idempotencia: si existe un Payment Entry submitted que referencia la invoice, no duplicar.
    refs = frappe.get_all(
        "Payment Entry Reference",
        filters={"reference_doctype": "Sales Invoice", "reference_name": invoice_name, "docstatus": 1},
        pluck="parent",
        limit=1,
    )
    return bool(refs)


def _submit_payment_for_invoice(invoice_name: str) -> None:
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    if getattr(invoice, "status", None) == "Paid" or getattr(invoice, "outstanding_amount", 0) == 0:
        return

    if _payment_entry_already_exists(invoice_name):
        return

    try:
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    except Exception as exc:
        raise SupervielleIntegrationError("ERPNext no disponible para crear Payment Entry.") from exc

    pe = get_payment_entry("Sales Invoice", invoice_name)
    pe.insert(ignore_permissions=True)
    pe.submit()


def _activate_socio_from_invoice(invoice_name: str) -> None:
    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    socio_name = (
        invoice.get("socio")
        or invoice.get("custom_socio")
        or invoice.get("member")
        or invoice.get("custom_member")
    )
    if not socio_name:
        return

    if not frappe.db.exists("Socio", socio_name):
        return

    socio = frappe.get_doc("Socio", socio_name)
    estado = (socio.get("estado") or "").strip()
    if estado in {"Moroso", "Pendiente"}:
        socio.set("estado", "Activo")
        socio.save(ignore_permissions=True)

    # Hook blando: si el DocType Socio expone un método para carné/QR, lo invocamos.
    for meth in ("habilitar_carne_digital_qr", "generar_carne_digital_qr", "generar_qr", "habilitar_qr"):
        fn = getattr(socio, meth, None)
        if callable(fn):
            fn()
            break


@frappe.whitelist(allow_guest=True)
def recibir_notificacion_pago() -> dict[str, Any]:
    """Webhook público Cobros Plus.

    Ruta esperada:
    `/api/method/club_management.integrations.supervielle_webhook.recibir_notificacion_pago`

    Nota: para mantener compatibilidad con la ruta pedida por negocio
    `/api/method/club_management.supervielle_api.recibir_notificacion_pago`,
    se expone un thin-wrapper en `club_management/supervielle_api.py`.
    """

    payload = _get_payload_from_request()

    try:
        settings = frappe.get_single("Cobros Plus Settings")
        secret_key = settings.get_password("secret_key")
    except Exception as exc:
        frappe.log_error(title="Supervielle Webhook Error", message=repr(exc))
        # Fail-closed: sin secret_key no se procesa nada.
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": "Configuración incompleta."}

    try:
        validate_webhook_hash(payload, secret_key=secret_key)
    except SupervielleWebhookAuthError as exc:
        frappe.log_error(
            title="Supervielle Webhook Fraud",
            message=json.dumps({"payload": payload, "error": str(exc)}, ensure_ascii=False),
        )
        return _ack_forbidden("Hash inválido.")

    # Lógica de conciliación: referencia de deuda
    reference = (payload.get("cod_trx") or payload.get("reference") or payload.get("sales_invoice") or "").strip()
    if not reference:
        # Si falta el identificador, no podemos conciliar; pero respondemos 200 para evitar tormenta de reintentos
        frappe.log_error(
            title="Supervielle Webhook Error",
            message=json.dumps({"payload": payload, "error": "Missing reference"}, ensure_ascii=False),
        )
        return _ack_ok("Referencia ausente; notificación aceptada.")

    invoice_name = _find_sales_invoice(reference)
    if not invoice_name:
        frappe.log_error(
            title="Supervielle Webhook Error",
            message=json.dumps({"payload": payload, "error": "Sales Invoice not found"}, ensure_ascii=False),
        )
        return _ack_ok("Factura no encontrada; notificación aceptada.")

    # Idempotencia + conciliación
    try:
        _submit_payment_for_invoice(invoice_name)
    except Exception as exc:
        # Si ya estaba pagada u otro medio lo impactó, no queremos reintentos.
        frappe.log_error(
            title="Supervielle Webhook Error",
            message=json.dumps({"invoice": invoice_name, "payload": payload, "exception": repr(exc)}, ensure_ascii=False),
        )
        return _ack_ok("Pago ya procesado o no aplicable.")

    # Activación socio + QR (best-effort; no bloquea el ack)
    try:
        _activate_socio_from_invoice(invoice_name)
    except Exception as exc:
        frappe.log_error(
            title="Supervielle Webhook Error",
            message=json.dumps({"invoice": invoice_name, "payload": payload, "exception": repr(exc)}, ensure_ascii=False),
        )

    return _ack_ok("Pago conciliado.")


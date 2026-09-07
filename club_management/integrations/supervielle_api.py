from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

import frappe

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore[assignment]


class SupervielleIntegrationError(RuntimeError):
    """Error tipado para que controladores Frappe manejen fallos de integración."""


@dataclass(frozen=True)
class SupervielleCredentials:
    cuit: str
    id_clave: str
    secret_key: str
    base_url_api: str


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _iter_json_values(obj: Any) -> Iterable[str]:
    """Itera valores JSON en orden, recursivo, sin claves ni separadores."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() == "hash":
                continue
            yield from _iter_json_values(v)
        return

    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_json_values(item)
        return

    yield _stringify_value(obj)


class SupervielleAPI:
    DEFAULT_TIMEOUT_SECONDS = 10

    # TODO: confirmar paths exactos según documentación del banco.
    ENDPOINT_PUBLICAR_DEUDA = "/publicar_deuda"
    ENDPOINT_GENERAR_BOTON_PAGO = "/generar_boton_pago"
    ENDPOINT_CONSULTAR_ESTADO = "/consultar_estado"

    def __init__(
        self,
        *,
        cuit: str | None = None,
        id_clave: str | None = None,
        secret_key: str | None = None,
        base_url_api: str | None = None,
        timeout_seconds: int | float | None = None,
        session: Any | None = None,
    ) -> None:
        self._cuit = cuit
        self._id_clave = id_clave
        self._secret_key = secret_key
        self._base_url_api = base_url_api
        self._timeout_seconds = float(timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS)
        self._session = session

    @classmethod
    def from_settings(cls) -> "SupervielleAPI":
        settings = frappe.get_single("Cobros Plus Settings")
        return cls(
            cuit=settings.cuit,
            id_clave=settings.id_clave,
            secret_key=settings.get_password("secret_key"),
            base_url_api=settings.base_url_api,
        )

    def _generate_hash(self, payload_dict: dict[str, Any]) -> str:
        if not self._secret_key:
            raise SupervielleIntegrationError("Falta secret_key para generar hash.")

        concatenated = "".join(_iter_json_values(payload_dict)) + self._secret_key
        return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

    def _prepare_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        final_payload = dict(payload)
        final_payload["hash"] = self._generate_hash(final_payload)
        return final_payload

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        if requests is None:
            raise SupervielleIntegrationError(
                "Dependencia 'requests' no disponible para integrar con Supervielle."
            )
        return requests.Session()

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._base_url_api:
            raise SupervielleIntegrationError("Falta base_url_api en Cobros Plus Settings.")

        url = self._base_url_api.rstrip("/") + "/" + endpoint.lstrip("/")
        body = self._prepare_payload(payload)

        sess = self._get_session()
        try:
            resp = sess.post(url, json=body, timeout=self._timeout_seconds)
        except Exception as exc:
            frappe.log_error(
                title="Supervielle API Error",
                message=json.dumps(
                    {"url": url, "payload": body, "exception": repr(exc)}, ensure_ascii=False
                ),
            )
            raise SupervielleIntegrationError("Error de red al llamar a Supervielle.") from exc

        if getattr(resp, "status_code", None) != 200:
            frappe.log_error(
                title="Supervielle API Error",
                message=json.dumps(
                    {
                        "url": url,
                        "status_code": getattr(resp, "status_code", None),
                        "response_text": getattr(resp, "text", None),
                    },
                    ensure_ascii=False,
                ),
            )
            raise SupervielleIntegrationError(
                f"Supervielle respondió HTTP {getattr(resp, 'status_code', 'desconocido')}."
            )

        try:
            data = resp.json()
        except Exception as exc:
            frappe.log_error(
                title="Supervielle API Error",
                message=json.dumps(
                    {"url": url, "status_code": resp.status_code, "response_text": resp.text},
                    ensure_ascii=False,
                ),
            )
            raise SupervielleIntegrationError("Respuesta no-JSON desde Supervielle.") from exc

        # Heurística conservadora de error interno; se ajusta con el doc real.
        internal_error = (
            data.get("error")
            or data.get("errors")
            or data.get("error_code")
            or data.get("codigo_error")
            or data.get("cod_error")
        )
        if internal_error:
            frappe.log_error(title="Supervielle API Error", message=json.dumps(data, ensure_ascii=False))
            raise SupervielleIntegrationError("Supervielle devolvió error de negocio.")

        return data

    def publicar_deuda(self, debt_data: dict[str, Any]) -> dict[str, Any]:
        payload = {"cuit": self._cuit, "id_clave": self._id_clave, **debt_data}
        return self._post_json(self.ENDPOINT_PUBLICAR_DEUDA, payload)

    def generar_boton_pago(self, trx_data: dict[str, Any]) -> dict[str, Any]:
        payload = {"cuit": self._cuit, "id_clave": self._id_clave, **trx_data}
        return self._post_json(self.ENDPOINT_GENERAR_BOTON_PAGO, payload)

    def consultar_estado(self, cod_trx: str) -> dict[str, Any]:
        payload = {"cuit": self._cuit, "id_clave": self._id_clave, "cod_trx": cod_trx}
        return self._post_json(self.ENDPOINT_CONSULTAR_ESTADO, payload)


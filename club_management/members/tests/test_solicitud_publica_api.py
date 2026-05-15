"""Tests del endpoint público de alta de `Solicitud Asociacion` (Sprint 1 Commit 2).

Cubre el endpoint custom whitelisted `submit_solicitud` y su helper de
resolución de IP detrás de proxy, según las decisiones registradas en
`specs/solicitud_asociacion_publica.md`:

- `_resolve_client_ip()`: primer valor de `X-Forwarded-For`, fallback a
  `remote_addr`.
- `submit_solicitud(data)`: crea la solicitud con `insert(ignore_permissions=True)`,
  filtra campos del sistema del payload, persiste `enviado_desde_ip`
  server-side y devuelve `{status, token_seguimiento}` sin filtrar `name`.
- `validate_ficha_medica_from_url`: valida MIME (magic numbers) + tamaño.
- Aislamiento: el rol `Guest` NO está declarado en DocPerm.

Notas sobre los archivos de tests:
- `MINIMAL_VALID_PDF` (en `test_helpers`) es un PDF estructuralmente
  válido que `pypdf` puede parsear sin error. Lo usamos cuando el File
  necesita pasar los hooks de procesamiento automático de Frappe v15.
- Los archivos creados para tests de spoofing / tamaño excesivo se
  guardan con extensión `.bin` (no `.pdf`) para **evitar** que Frappe
  ejecute pypdf sobre ellos al insertarlos: la detección por magic
  numbers que validamos NO depende de la extensión, así que el test
  conceptual sigue siendo válido y no rompemos en el hook del File doc.
- Todos los Files se crean con `is_private=1` (default de
  `make_test_file`), lo que también ayuda a saltearse el procesamiento
  agresivo que solo aplica a archivos públicos.

No incluye test funcional de las 6 requests del rate-limit (depende del
estado de Redis y queda como test de integración E2E). Sí valida que el
módulo importa el decorator correcto.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import frappe

from club_management.members.test_helpers import (
    MINIMAL_VALID_PDF,
    MembersTestCase,
    make_solicitud_asociacion_payload,
    make_solicitud_menor_payload,
    make_test_file,
)


def _mock_request(remote_addr: str = "1.2.3.4", xff: str | None = None) -> MagicMock:
    """Construye un mock de `frappe.local.request` con headers y remote_addr."""
    req = MagicMock()
    req.remote_addr = remote_addr
    req.headers = {"X-Forwarded-For": xff} if xff else {}
    return req


_PATCH_SENTINEL = object()


@contextmanager
def _patched_request(mock_request):
    """Setea `frappe.local.request` durante el bloque y lo restaura al salir.

    `frappe.local` es un `werkzeug.local.Local` cuyos atributos se setean
    dinámicamente en cada request; fuera del ciclo HTTP el atributo
    `request` puede no existir. `unittest.mock.patch.object` falla con
    `AttributeError` en ese caso a menos que se pase `create=True`. Este
    helper hace el set/restore manualmente y es robusto en ambos
    escenarios (atributo previamente seteado o no).
    """
    old = getattr(frappe.local, "request", _PATCH_SENTINEL)
    frappe.local.request = mock_request
    try:
        yield
    finally:
        if old is _PATCH_SENTINEL:
            try:
                delattr(frappe.local, "request")
            except AttributeError:
                pass
        else:
            frappe.local.request = old


# ---------------------------------------------------------------------------
# `_resolve_client_ip` — resolución de IP detrás de proxy
# ---------------------------------------------------------------------------


class TestResolveClientIP(MembersTestCase):
    """Helper interno que resuelve la IP cliente respetando X-Forwarded-For."""

    def test_xff_devuelve_primer_ip_del_header(self) -> None:
        from club_management.members.api.solicitud_publica import _resolve_client_ip

        with _patched_request(_mock_request(xff="9.9.9.9, 10.0.0.1, 172.16.0.1")):
            self.assertEqual(_resolve_client_ip(), "9.9.9.9")

    def test_xff_con_un_solo_ip_funciona(self) -> None:
        from club_management.members.api.solicitud_publica import _resolve_client_ip

        with _patched_request(_mock_request(xff="9.9.9.9")):
            self.assertEqual(_resolve_client_ip(), "9.9.9.9")

    def test_xff_trim_de_espacios(self) -> None:
        """`X-Forwarded-For: ' 9.9.9.9 , 10.0.0.1 '` -> `9.9.9.9`."""
        from club_management.members.api.solicitud_publica import _resolve_client_ip

        with _patched_request(_mock_request(xff=" 9.9.9.9 , 10.0.0.1 ")):
            self.assertEqual(_resolve_client_ip(), "9.9.9.9")

    def test_sin_xff_usa_remote_addr(self) -> None:
        from club_management.members.api.solicitud_publica import _resolve_client_ip

        with _patched_request(_mock_request(remote_addr="5.5.5.5", xff=None)):
            self.assertEqual(_resolve_client_ip(), "5.5.5.5")

    def test_xff_vacio_cae_a_remote_addr(self) -> None:
        from club_management.members.api.solicitud_publica import _resolve_client_ip

        with _patched_request(_mock_request(remote_addr="5.5.5.5", xff="")):
            self.assertEqual(_resolve_client_ip(), "5.5.5.5")

    def test_sin_request_devuelve_string_vacio(self) -> None:
        from club_management.members.api.solicitud_publica import _resolve_client_ip

        with _patched_request(None):
            self.assertEqual(_resolve_client_ip(), "")


# ---------------------------------------------------------------------------
# Mixin: clases que entran al endpoint con éxito necesitan un PDF real
# ---------------------------------------------------------------------------


class _PayloadConFichaRealMixin:
    """Provee `self.real_ficha_url` (un PDF mínimo válido) a la subclase.

    Se crea una vez por clase con `setUpClass` para evitar regenerar el
    archivo en cada test. El SAVEPOINT del `MembersTestCase` opera dentro
    del savepoint del test, así que el File creado en `setUpClass`
    sobrevive a los rollbacks de cada test.
    """

    real_ficha_url: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.real_ficha_url = make_test_file(
            "ficha_minimo_valido.pdf",
            MINIMAL_VALID_PDF,
            is_private=1,
        )

    def _adulto_payload(self, **overrides):
        overrides.setdefault("ficha_medica", self.real_ficha_url)
        return make_solicitud_asociacion_payload(**overrides)

    def _menor_payload(self, **overrides):
        overrides.setdefault("ficha_medica", self.real_ficha_url)
        return make_solicitud_menor_payload(**overrides)


# ---------------------------------------------------------------------------
# `submit_solicitud` — alta básica
# ---------------------------------------------------------------------------


class TestSubmitSolicitudPublicaAdulto(_PayloadConFichaRealMixin, MembersTestCase):
    """Alta pública de un solicitante adulto vía endpoint custom."""

    def test_submit_crea_solicitud_con_workflow_pendiente(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=self._adulto_payload())

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result.get("token_seguimiento"))

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertEqual(sol.workflow_state, "Pendiente")
        self.assertEqual(sol.dni, "30123456")

    def test_submit_devuelve_token_pero_no_expone_name(self) -> None:
        """La respuesta NO debe filtrar `name` (anti-enumeración)."""
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=self._adulto_payload())

        self.assertIn("status", result)
        self.assertIn("token_seguimiento", result)
        self.assertNotIn("name", result)

    def test_submit_persiste_enviado_desde_ip_server_side(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        with _patched_request(_mock_request(xff="9.9.9.9, 10.0.0.1")):
            result = submit_solicitud(data=self._adulto_payload())

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertEqual(sol.enviado_desde_ip, "9.9.9.9")

    def test_submit_persiste_remote_addr_si_no_hay_xff(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        with _patched_request(_mock_request(remote_addr="5.5.5.5", xff=None)):
            result = submit_solicitud(data=self._adulto_payload())

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertEqual(sol.enviado_desde_ip, "5.5.5.5")

    def test_submit_acepta_payload_como_json_string(self) -> None:
        """Frappe whitelist suele recibir el body como string JSON."""
        import json

        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload_str = json.dumps(self._adulto_payload(), default=str)

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=payload_str)

        self.assertEqual(result["status"], "ok")


# ---------------------------------------------------------------------------
# `submit_solicitud` — filtrado de campos del sistema
# ---------------------------------------------------------------------------


class TestSubmitSolicitudFiltradoDeCampos(
    _PayloadConFichaRealMixin, MembersTestCase
):
    """El cliente Guest no debe poder setear campos del sistema."""

    def test_workflow_state_del_payload_es_ignorado(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._adulto_payload()
        payload["workflow_state"] = "Validada"

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=payload)

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertEqual(sol.workflow_state, "Pendiente")

    def test_token_seguimiento_del_payload_es_ignorado(self) -> None:
        """Si el cliente manda un token, el server genera uno fresco."""
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._adulto_payload()
        payload["token_seguimiento"] = "tk-ataque-conocido"

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=payload)

        self.assertNotEqual(result["token_seguimiento"], "tk-ataque-conocido")

    def test_enviado_desde_ip_del_payload_es_ignorado(self) -> None:
        """El cliente no puede pisar la IP server-side."""
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._adulto_payload()
        payload["enviado_desde_ip"] = "9.9.9.9"

        with _patched_request(_mock_request(remote_addr="1.2.3.4")):
            result = submit_solicitud(data=payload)

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertEqual(sol.enviado_desde_ip, "1.2.3.4")

    def test_referencias_de_auditoria_del_payload_son_ignoradas(self) -> None:
        """`socio_generado`, `validado_por`, etc. no pueden venir del cliente."""
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._adulto_payload()
        payload["socio_generado"] = "SOC-FALSO"
        payload["user_generado"] = "atacante@example.com"
        payload["validado_por"] = "Administrator"
        payload["rechazado_por"] = "Administrator"

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=payload)

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertFalse(sol.socio_generado)
        self.assertFalse(sol.user_generado)
        self.assertFalse(sol.validado_por)
        self.assertFalse(sol.rechazado_por)


# ---------------------------------------------------------------------------
# `submit_solicitud` — campos obligatorios y mandatory_depends_on
# ---------------------------------------------------------------------------


class TestSubmitSolicitudCamposObligatorios(
    _PayloadConFichaRealMixin, MembersTestCase
):
    """El endpoint hereda las validaciones del DocType (`validate()`)."""

    def test_falla_si_falta_dni_del_solicitante(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._adulto_payload(dni="")

        with _patched_request(_mock_request()):
            with self.assertRaises(frappe.exceptions.MandatoryError):
                submit_solicitud(data=payload)

    def test_menor_sin_email_tutor_falla_por_mandatory_depends_on(self) -> None:
        """`enforce_mandatory_depends_on` se gatilla server-side desde el endpoint."""
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._menor_payload(email_tutor="")

        with _patched_request(_mock_request()):
            with self.assertRaises(frappe.exceptions.MandatoryError):
                submit_solicitud(data=payload)

    def test_menor_completo_pasa(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=self._menor_payload())

        self.assertEqual(result["status"], "ok")


# ---------------------------------------------------------------------------
# `validate_ficha_medica_from_url` — validación de adjuntos
# ---------------------------------------------------------------------------


class TestValidateFichaMedicaFromUrl(MembersTestCase):
    """El helper resuelve el `File` por URL, detecta MIME por magic numbers."""

    def test_pdf_valido_pasa(self) -> None:
        from club_management.members.validations import validate_ficha_medica_from_url

        url = make_test_file("ficha_ok.pdf", MINIMAL_VALID_PDF, is_private=1)
        validate_ficha_medica_from_url(url)

    def test_jpeg_valido_pasa(self) -> None:
        from club_management.members.validations import validate_ficha_medica_from_url

        # Magic numbers de JPEG (SOI + APP0). El cuerpo es arbitrario porque
        # nuestro validador solo inspecciona los primeros 8 bytes; usamos
        # `is_private=1` y filename `.bin` para evitar que Frappe procese
        # el archivo como imagen (Pillow lo rechazaría por estructura).
        url = make_test_file(
            "ficha_jpeg.bin",
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00 cuerpo arbitrario",
            is_private=1,
        )
        validate_ficha_medica_from_url(url)

    def test_png_valido_pasa(self) -> None:
        from club_management.members.validations import validate_ficha_medica_from_url

        url = make_test_file(
            "ficha_png.bin",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR cuerpo arbitrario",
            is_private=1,
        )
        validate_ficha_medica_from_url(url)

    def test_extension_pdf_pero_contenido_no_pdf_falla(self) -> None:
        """Anti-spoofing: la detección es por magic numbers, no por extensión.

        Filename `.bin` para evitar el hook de pypdf sobre el File doc;
        lo que importa es que el contenido NO empieza con `%PDF` y por
        eso `_detect_mime_by_magic_numbers` devuelve `octet-stream`,
        que `validate_ficha_medica` rechaza.
        """
        from club_management.members.validations import validate_ficha_medica_from_url

        url = make_test_file(
            "spoof_supuestamente_pdf.bin",
            b"PK\x03\x04 esto en realidad es un ZIP renombrado",
            is_private=1,
        )
        with self.assertRaises(frappe.ValidationError):
            validate_ficha_medica_from_url(url)

    def test_tamano_excesivo_falla(self) -> None:
        """Archivo >5MB rechazado. Filename `.bin` para evitar pypdf
        (el contenido tiene magic bytes `%PDF` pero no es un PDF
        estructuralmente válido)."""
        from club_management.members.validations import validate_ficha_medica_from_url

        big_pdf_like = b"%PDF-1.4\n" + (b"\x00" * (6 * 1024 * 1024))
        url = make_test_file("big_pdf_like.bin", big_pdf_like, is_private=1)
        with self.assertRaises(frappe.ValidationError):
            validate_ficha_medica_from_url(url)


# ---------------------------------------------------------------------------
# `submit_solicitud` — integración con validate_ficha_medica
# ---------------------------------------------------------------------------


class TestSubmitSolicitudFichaMedica(_PayloadConFichaRealMixin, MembersTestCase):
    """El endpoint valida la ficha médica antes de insertar la solicitud."""

    def test_submit_acepta_ficha_medica_pdf_real(self) -> None:
        """El PDF mínimo válido se acepta y la solicitud se crea."""
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        url = make_test_file(
            "ficha_real_test.pdf", MINIMAL_VALID_PDF, is_private=1
        )
        payload = self._adulto_payload(ficha_medica=url)

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=payload)

        self.assertEqual(result["status"], "ok")

    def test_submit_rechaza_ficha_medica_mime_invalido(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        url = make_test_file(
            "ficha_falsa.bin",
            b"PK\x03\x04 esto es un zip, no un pdf",
            is_private=1,
        )
        payload = self._adulto_payload(ficha_medica=url)

        with _patched_request(_mock_request()):
            with self.assertRaises(frappe.ValidationError):
                submit_solicitud(data=payload)

    def test_submit_rechaza_ficha_medica_tamano_excesivo(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        big_pdf_like = b"%PDF-1.4\n" + (b"\x00" * (6 * 1024 * 1024))
        url = make_test_file(
            "ficha_grande_pdf_like.bin", big_pdf_like, is_private=1
        )
        payload = self._adulto_payload(ficha_medica=url)

        with _patched_request(_mock_request()):
            with self.assertRaises(frappe.ValidationError):
                submit_solicitud(data=payload)


# ---------------------------------------------------------------------------
# Aislamiento: Guest NO está declarado en DocPerm
# ---------------------------------------------------------------------------


class TestGuestNoTienePermisoSobreSolicitud(
    _PayloadConFichaRealMixin, MembersTestCase
):
    """El rol `Guest` no aparece en DocPerm; el endpoint custom usa
    `ignore_permissions=True` para la inserción."""

    def test_guest_no_aparece_en_docperm(self) -> None:
        meta = frappe.get_meta("Solicitud Asociacion")
        guest_perms = [p for p in meta.permissions if p.role == "Guest"]
        self.assertEqual(
            guest_perms,
            [],
            "Rol Guest NO debe declararse en DocPerm de Solicitud Asociacion",
        )

    def test_guest_no_tiene_permiso_de_lectura(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=self._adulto_payload())

        sol_name = frappe.db.get_value(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
            "name",
        )
        self.assertFalse(
            frappe.has_permission(
                "Solicitud Asociacion", "read", doc=sol_name, user="Guest"
            )
        )

    def test_guest_no_tiene_permiso_de_creacion_directa(self) -> None:
        """Guest no puede crear via `/api/resource/Solicitud Asociacion`."""
        self.assertFalse(
            frappe.has_permission("Solicitud Asociacion", "create", user="Guest")
        )


# ---------------------------------------------------------------------------
# Rate-limit decorator está aplicado
# ---------------------------------------------------------------------------


class TestSubmitSolicitudLegacyAddressFields(
    _PayloadConFichaRealMixin, MembersTestCase
):
    """Payload legacy `domicilio` se normaliza a `calle` antes del insert."""

    def test_submit_acepta_domicilio_legacy_como_calle(self) -> None:
        from club_management.members.api.solicitud_publica import (
            _submit_solicitud_impl as submit_solicitud,
        )

        payload = self._adulto_payload()
        payload.pop("calle", None)
        payload["domicilio"] = "Av. Siempre Viva 742"

        with _patched_request(_mock_request()):
            result = submit_solicitud(data=payload)

        sol = frappe.get_doc(
            "Solicitud Asociacion",
            {"token_seguimiento": result["token_seguimiento"]},
        )
        self.assertEqual(sol.calle, "Av. Siempre Viva 742")


class TestGetPlacesConfig(MembersTestCase):
    def test_sin_clave_devuelve_disabled(self) -> None:
        from club_management.members.api.solicitud_publica import get_places_config

        old = frappe.conf.get("google_maps_api_key")
        frappe.conf.google_maps_api_key = ""
        try:
            cfg = get_places_config()
        finally:
            frappe.conf.google_maps_api_key = old
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["api_key"], "")

    def test_con_clave_devuelve_enabled(self) -> None:
        from club_management.members.api.solicitud_publica import get_places_config

        old = frappe.conf.get("google_maps_api_key")
        frappe.conf.google_maps_api_key = "test-key-123"
        try:
            cfg = get_places_config()
        finally:
            frappe.conf.google_maps_api_key = old
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["api_key"], "test-key-123")


class TestSubmitSolicitudRateLimitDecorator(MembersTestCase):
    """Verifica que `submit_solicitud` está decorado con `@frappe.rate_limit`.

    No testea funcionalmente las 6 requests (depende de Redis y es flaky en
    unit tests). El test E2E del rate-limit queda como integration test.
    """

    def test_modulo_importa_rate_limit_de_frappe(self) -> None:
        import inspect

        from club_management.members.api import solicitud_publica

        source = inspect.getsource(solicitud_publica)
        self.assertIn("rate_limit", source, "El endpoint debe usar rate_limit")
        self.assertIn("limit=5", source, "El límite debe ser 5 requests")
        self.assertIn("seconds=600", source, "La ventana debe ser 600s (10 min)")


if __name__ == "__main__":
    import unittest

    unittest.main()


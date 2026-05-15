"""Tests del DocType `Solicitud Asociacion` (Sprint 1 Commit 1).

Nota: el `name` técnico del DocType es `Solicitud Asociacion` (ASCII puro,
sin tilde y sin "de"). El label visible en UX se traducirá a "Solicitud de
Asociación" vía i18n en un sprint dedicado. El concepto de negocio sigue
siendo "Solicitud de Asociación".

Cubre lo que se puede validar sin Web Form ni Workflow ni servicios de
validación (esos entran en Commits 2-6 del Sprint 1):

- Existencia y metadata del DocType.
- Autoname `SOL-YYYY-####`.
- Defaults (`workflow_state = "Pendiente"`).
- Campos `reqd` mínimos del solicitante.
- `mandatory_depends_on` del bloque tutor cuando `categoria_solicitada = "Menor"`.
- `token_seguimiento` autogenerado en `before_insert`.
- DocPerm estático (System Manager, Secretaría, Socio).

Spec: `club_management/specs/solicitud_asociacion_publica.md`.
"""

from __future__ import annotations

import re

import frappe

from club_management.members.test_helpers import (
    MembersTestCase,
    make_solicitud_asociacion_payload,
    make_solicitud_menor_payload,
)

DOCTYPE = "Solicitud Asociacion"


class TestSolicitudAsociacionMetadata(MembersTestCase):
    """Smoke + metadata del DocType."""

    def test_campos_calle_en_meta(self) -> None:
        meta = frappe.get_meta(DOCTYPE)
        self.assertIsNotNone(meta.get_field("calle"))
        self.assertIsNotNone(meta.get_field("calle_tutor"))
        self.assertIsNone(meta.get_field("domicilio"))

    def test_campos_documentacion_tutor_en_meta(self) -> None:
        meta = frappe.get_meta(DOCTYPE)
        for fname in (
            "dni_frente_tutor",
            "dni_dorso_tutor",
            "foto_perfil_tutor",
        ):
            self.assertIsNotNone(
                meta.get_field(fname),
                f"Falta campo {fname} en Solicitud Asociacion",
            )

    def test_doctype_existe(self) -> None:
        self.assertTrue(frappe.db.exists("DocType", DOCTYPE))

    def test_modulo_es_members(self) -> None:
        meta = frappe.get_meta(DOCTYPE)
        self.assertEqual(meta.module, "Members")

    def test_autoname_es_serie_sol_yyyy(self) -> None:
        meta = frappe.get_meta(DOCTYPE)
        self.assertEqual(meta.autoname, "format:SOL-{YYYY}-{####}")

    def test_track_changes_activo(self) -> None:
        meta = frappe.get_meta(DOCTYPE)
        self.assertEqual(meta.track_changes, 1)


class TestSolicitudAsociacionAltaBasica(MembersTestCase):
    """Alta de solicitud adulta con todos los campos requeridos."""

    def test_alta_adulto_minima_es_valida(self) -> None:
        sol = frappe.get_doc(make_solicitud_asociacion_payload()).insert(
            ignore_permissions=True
        )
        self.assertTrue(sol.name.startswith("SOL-"))
        self.assertEqual(sol.workflow_state, "Pendiente")
        self.assertEqual(sol.categoria_solicitada, "Activo")

    def test_dni_obligatorio(self) -> None:
        payload = make_solicitud_asociacion_payload(dni=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_email_obligatorio(self) -> None:
        payload = make_solicitud_asociacion_payload(email=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_categoria_solicitada_obligatoria(self) -> None:
        payload = make_solicitud_asociacion_payload(categoria_solicitada=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_ficha_medica_obligatoria(self) -> None:
        payload = make_solicitud_asociacion_payload(ficha_medica=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_nacionalidad_obligatoria(self) -> None:
        payload = make_solicitud_asociacion_payload(nacionalidad="")
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_genero_obligatorio(self) -> None:
        payload = make_solicitud_asociacion_payload(genero=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)


class TestSolicitudAsociacionDniNoEsUnique(MembersTestCase):
    """`dni` NO es unique en `Solicitud`: una persona puede reintentar.

    La validación 'DNI ya como Socio' se hace al validar la solicitud, no
    al crearla. Eso permite a un solicitante rechazado reenviar la solicitud
    con su mismo DNI.
    """

    def test_dos_solicitudes_con_mismo_dni_son_validas(self) -> None:
        s1 = frappe.get_doc(make_solicitud_asociacion_payload()).insert(
            ignore_permissions=True
        )
        s2 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="otro@example.com")
        ).insert(ignore_permissions=True)
        self.assertEqual(s1.dni, s2.dni)
        self.assertNotEqual(s1.name, s2.name)


class TestSolicitudAsociacionMenor(MembersTestCase):
    """`categoria_solicitada = "Menor"` exige los campos del bloque tutor."""

    def test_menor_con_datos_tutor_completos_es_valido(self) -> None:
        sol = frappe.get_doc(make_solicitud_menor_payload()).insert(
            ignore_permissions=True
        )
        self.assertEqual(sol.categoria_solicitada, "Menor")
        self.assertEqual(sol.dni_tutor, "20111111")
        self.assertEqual(sol.email_tutor, "papa@example.com")

    def test_menor_sin_documentacion_tutor_falla(self) -> None:
        payload = make_solicitud_menor_payload(dni_frente_tutor=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_menor_sin_dni_tutor_falla(self) -> None:
        payload = make_solicitud_menor_payload(dni_tutor=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_menor_sin_email_tutor_falla(self) -> None:
        payload = make_solicitud_menor_payload(email_tutor=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_menor_sin_rol_tutor_falla(self) -> None:
        payload = make_solicitud_menor_payload(rol_tutor=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_adulto_no_exige_datos_tutor(self) -> None:
        """Sin pasar campos del tutor, una solicitud `Activo` pasa."""
        sol = frappe.get_doc(make_solicitud_asociacion_payload()).insert(
            ignore_permissions=True
        )
        self.assertEqual(sol.categoria_solicitada, "Activo")
        self.assertFalse(sol.dni_tutor)


class TestSolicitudAsociacionTokenSeguimiento(MembersTestCase):
    """`token_seguimiento` se autogenera en `before_insert`."""

    def test_token_seguimiento_se_genera_en_creacion(self) -> None:
        sol = frappe.get_doc(make_solicitud_asociacion_payload()).insert(
            ignore_permissions=True
        )
        self.assertTrue(sol.token_seguimiento)
        # UUID v4 hexadecimal o token equivalente: al menos 16 chars.
        self.assertGreaterEqual(len(sol.token_seguimiento), 16)

    def test_token_seguimiento_es_unico_entre_solicitudes(self) -> None:
        s1 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="a@example.com")
        ).insert(ignore_permissions=True)
        s2 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="b@example.com")
        ).insert(ignore_permissions=True)
        self.assertNotEqual(s1.token_seguimiento, s2.token_seguimiento)

    def test_token_seguimiento_es_read_only(self) -> None:
        meta = frappe.get_meta(DOCTYPE)
        field = next(
            (f for f in meta.fields if f.fieldname == "token_seguimiento"), None
        )
        self.assertIsNotNone(field, "Campo `token_seguimiento` no declarado")
        self.assertEqual(field.read_only, 1)

    def test_token_seguimiento_no_es_adivinable_por_enumeracion(self) -> None:
        """Sucesivos tokens no comparten prefijos largos (no son seriales)."""
        s1 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="a@example.com")
        ).insert(ignore_permissions=True)
        s2 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="b@example.com")
        ).insert(ignore_permissions=True)
        common_prefix = _common_prefix_len(s1.token_seguimiento, s2.token_seguimiento)
        self.assertLess(
            common_prefix,
            8,
            f"Tokens son demasiado similares: {s1.token_seguimiento} vs {s2.token_seguimiento}",
        )


class TestSolicitudAsociacionAutoname(MembersTestCase):
    """Autoname `SOL-YYYY-####` genera serie secuencial por año."""

    def test_autoname_formato_correcto(self) -> None:
        sol = frappe.get_doc(make_solicitud_asociacion_payload()).insert(
            ignore_permissions=True
        )
        self.assertRegex(sol.name, r"^SOL-\d{4}-\d{4,}$")

    def test_autoname_genera_serie_secuencial(self) -> None:
        s1 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="a@example.com")
        ).insert(ignore_permissions=True)
        s2 = frappe.get_doc(
            make_solicitud_asociacion_payload(email="b@example.com")
        ).insert(ignore_permissions=True)
        m1 = re.match(r"^SOL-(\d{4})-(\d+)$", s1.name)
        m2 = re.match(r"^SOL-(\d{4})-(\d+)$", s2.name)
        assert m1 is not None and m2 is not None
        self.assertEqual(m1.group(1), m2.group(1), "Año debe coincidir")
        self.assertEqual(
            int(m2.group(2)) - int(m1.group(2)),
            1,
            "Serie debe ser secuencial",
        )


class TestSolicitudAsociacionPermisos(MembersTestCase):
    """DocPerm estático declarado en `solicitud_asociacion.json`."""

    def setUp(self) -> None:
        super().setUp()
        meta = frappe.get_meta(DOCTYPE)
        self._perms_by_role = {p.role: p for p in meta.permissions}

    def test_system_manager_tiene_full_access(self) -> None:
        sm = self._perms_by_role.get("System Manager")
        self.assertIsNotNone(sm, "Rol System Manager no declarado")
        self.assertEqual(sm.create, 1)
        self.assertEqual(sm.read, 1)
        self.assertEqual(sm.write, 1)
        self.assertEqual(sm.delete, 1)

    def test_secretaria_tiene_cru_sin_delete(self) -> None:
        sec = self._perms_by_role.get("Secretaria")
        self.assertIsNotNone(sec, "Rol Secretaria no declarado")
        self.assertEqual(sec.create, 1)
        self.assertEqual(sec.read, 1)
        self.assertEqual(sec.write, 1)
        self.assertEqual(sec.delete, 0)

    def test_socio_no_tiene_read(self) -> None:
        """El rol Socio no debe ver solicitudes (es el solicitante anterior)."""
        socio = self._perms_by_role.get("Socio")
        if socio is None:
            return
        self.assertEqual(socio.read, 0)
        self.assertEqual(socio.create, 0)
        self.assertEqual(socio.write, 0)
        self.assertEqual(socio.delete, 0)


def _common_prefix_len(a: str, b: str) -> int:
    """Devuelve la longitud del prefijo común entre `a` y `b`."""
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            return n
        n += 1
    return n

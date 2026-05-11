"""Tests de aislamiento del DocType `Socio` por usuario.

Cubre los escenarios de `specs/socio_minimo.md`:

- Un `User` con rol `Socio` ve **solo** su propio `Socio`.
- `Secretaria` y `System Manager` ven todos.
- Abrir directamente un `Socio` ajeno por `name` lanza `PermissionError`.
"""

from __future__ import annotations

import contextlib

import frappe

from club_management.members.services.user_provisioning import (
    provision_user_for_socio,
)
from club_management.members.test_helpers import (
    MembersTestCase,
    ensure_role_socio_exists,
    insert_socio,
)


@contextlib.contextmanager
def as_user(user: str):
    """Context manager que cambia `frappe.session.user` y restaura al salir."""
    previous = frappe.session.user
    try:
        frappe.set_user(user)
        yield
    finally:
        frappe.set_user(previous)


class TestSocioIsolation(MembersTestCase):
    def _setup_dos_socios(self):
        ensure_role_socio_exists()

        s1 = insert_socio(dni="30100100", email="s1@example.com")
        provision_user_for_socio(s1.name)
        s1.reload()

        s2 = insert_socio(dni="30200200", email="s2@example.com")
        provision_user_for_socio(s2.name)
        s2.reload()

        return s1, s2

    def test_user_de_s1_ve_solo_s1_en_listado(self) -> None:
        s1, s2 = self._setup_dos_socios()

        with as_user(s1.user):
            names = frappe.get_list("Socio", pluck="name")

        self.assertIn(s1.name, names)
        self.assertNotIn(s2.name, names)

    def test_user_de_s1_no_puede_abrir_s2_directo(self) -> None:
        """`frappe.has_permission(throw=True)` es la API que ejerce el portal/REST.

        `frappe.get_doc(...)` desde código Python server-side **no** dispara
        el chequeo en Frappe v15+; la responsabilidad de verificar permisos
        en un get directo recae en `frappe.client.get` (REST) o en una llamada
        explícita a `frappe.has_permission` (server-side).
        """
        s1, s2 = self._setup_dos_socios()

        with as_user(s1.user):
            self.assertFalse(
                frappe.has_permission("Socio", "read", doc=s2.name, user=s1.user)
            )
            with self.assertRaises(frappe.PermissionError):
                frappe.has_permission(
                    "Socio", "read", doc=s2.name, user=s1.user, throw=True
                )

    def test_user_de_s1_puede_abrir_s1(self) -> None:
        s1, _s2 = self._setup_dos_socios()

        with as_user(s1.user):
            self.assertTrue(
                frappe.has_permission("Socio", "read", doc=s1.name, user=s1.user)
            )
            doc = frappe.get_doc("Socio", s1.name)

        self.assertEqual(doc.name, s1.name)

    def test_administrator_ve_todos(self) -> None:
        s1, s2 = self._setup_dos_socios()

        with as_user("Administrator"):
            names = frappe.get_list("Socio", pluck="name")

        self.assertIn(s1.name, names)
        self.assertIn(s2.name, names)

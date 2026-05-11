"""Tests de aislamiento del DocType `Tutor No Socio` por usuario.

Cubre los escenarios de `specs/tutor_no_socio_minimo.md`:

- Un `User` enlazado a un `Tutor No Socio` ve su propio registro.
- Un `User` enlazado a un `Socio` miembro de un grupo cuyo titular es un
  `Tutor No Socio` ve a ese tutor (y solo a ese).
- Abrir un `Tutor No Socio` ajeno por `name` lanza `PermissionError`.
"""

from __future__ import annotations

import contextlib

import frappe

from club_management.members.services.user_provisioning import (
    provision_user_for_socio,
    provision_user_for_tutor_no_socio,
)
from club_management.members.test_helpers import (
    MembersTestCase,
    add_miembro_socio,
    ensure_role_socio_exists,
    insert_grupo_familiar_solo_tutor,
    insert_socio,
    insert_tutor_no_socio,
    minor_birthdate,
)


@contextlib.contextmanager
def as_user(user: str):
    previous = frappe.session.user
    try:
        frappe.set_user(user)
        yield
    finally:
        frappe.set_user(previous)


class TestTutorNoSocioIsolationOwnUser(MembersTestCase):
    def test_tutor_ve_su_propio_registro(self) -> None:
        ensure_role_socio_exists()

        tutor = insert_tutor_no_socio(dni="20800000", email="tutor.propio@example.com")
        provision_user_for_tutor_no_socio(tutor.name)
        tutor.reload()

        otro = insert_tutor_no_socio(
            dni="20900000",
            email="tutor.otro@example.com",
        )

        with as_user(tutor.user):
            names = frappe.get_list("Tutor No Socio", pluck="name")
            self.assertIn(tutor.name, names)
            self.assertNotIn(otro.name, names)


class TestTutorNoSocioIsolationViaGrupoFamiliar(MembersTestCase):
    """Un `Socio` (User con rol Socio) ve al `Tutor No Socio` titular de su grupo."""

    def test_socio_hijo_ve_al_tutor_de_su_grupo(self) -> None:
        ensure_role_socio_exists()

        tutor = insert_tutor_no_socio(
            dni="20700000", email="papa.test@example.com"
        )
        provision_user_for_tutor_no_socio(tutor.name)
        tutor.reload()

        grupo = insert_grupo_familiar_solo_tutor(
            tutor.name,
            nombre_grupo="Familia Test",
            apellido_principal="Test",
        )

        hijo = insert_socio(
            dni="55700000",
            email="hijo.test@example.com",
            fecha_nacimiento=minor_birthdate(10),
            categoria="Menor",
            tipo_tutor="Tutor No Socio",
            tutor=tutor.name,
            grupo_familiar=grupo.name,
        )
        provision_user_for_socio(hijo.name)
        hijo.reload()
        add_miembro_socio(grupo.name, hijo.name, rol="Hijo")

        tutor_ajeno = insert_tutor_no_socio(
            dni="20600000",
            email="tutor.ajeno@example.com",
        )

        with as_user(hijo.user):
            names = frappe.get_list("Tutor No Socio", pluck="name")
            self.assertIn(tutor.name, names)
            self.assertNotIn(tutor_ajeno.name, names)

            self.assertFalse(
                frappe.has_permission(
                    "Tutor No Socio",
                    "read",
                    doc=tutor_ajeno.name,
                    user=hijo.user,
                )
            )
            with self.assertRaises(frappe.PermissionError):
                frappe.has_permission(
                    "Tutor No Socio",
                    "read",
                    doc=tutor_ajeno.name,
                    user=hijo.user,
                    throw=True,
                )

            self.assertTrue(
                frappe.has_permission(
                    "Tutor No Socio",
                    "read",
                    doc=tutor.name,
                    user=hijo.user,
                )
            )


class TestTutorNoSocioIsolationAdministrator(MembersTestCase):
    def test_administrator_ve_todos(self) -> None:
        t1 = insert_tutor_no_socio(dni="20100100", email="adm.t1@example.com")
        t2 = insert_tutor_no_socio(dni="20100200", email="adm.t2@example.com")

        names = frappe.get_list("Tutor No Socio", pluck="name")
        self.assertIn(t1.name, names)
        self.assertIn(t2.name, names)

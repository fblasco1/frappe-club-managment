"""Tests de aislamiento del DocType `Grupo Familiar` por usuario.

Cubre los escenarios de `specs/grupo_familiar_minimo.md`:

- Un `User` enlazado a un `Socio` miembro de G1 ve **solo** G1.
- Un `User` enlazado a un `Tutor No Socio` titular activo de G ve **solo** G.
- Abrir directamente un grupo ajeno por `name` lanza `PermissionError`.
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
    insert_grupo_familiar_solo_socio,
    insert_grupo_familiar_solo_tutor,
    insert_socio,
    insert_tutor_no_socio,
)


@contextlib.contextmanager
def as_user(user: str):
    previous = frappe.session.user
    try:
        frappe.set_user(user)
        yield
    finally:
        frappe.set_user(previous)


class TestGrupoFamiliarIsolationViaSocio(MembersTestCase):
    """El usuario es un Socio miembro de un grupo."""

    def _setup_dos_grupos_con_socio_en_uno(self):
        ensure_role_socio_exists()

        s_familia_a = insert_socio(dni="30111000", email="papa.a@example.com")
        provision_user_for_socio(s_familia_a.name)
        s_familia_a.reload()
        g1 = insert_grupo_familiar_solo_socio(
            s_familia_a.name,
            nombre_grupo="Familia A",
            apellido_principal="A",
        )

        s_familia_b = insert_socio(dni="30222000", email="papa.b@example.com")
        provision_user_for_socio(s_familia_b.name)
        s_familia_b.reload()
        g2 = insert_grupo_familiar_solo_socio(
            s_familia_b.name,
            nombre_grupo="Familia B",
            apellido_principal="B",
        )

        return s_familia_a, s_familia_b, g1, g2

    def test_user_de_g1_ve_solo_g1(self) -> None:
        s_a, _s_b, g1, g2 = self._setup_dos_grupos_con_socio_en_uno()

        with as_user(s_a.user):
            names = frappe.get_list("Grupo Familiar", pluck="name")

        self.assertIn(g1.name, names)
        self.assertNotIn(g2.name, names)

    def test_user_de_g1_no_puede_abrir_g2(self) -> None:
        s_a, _s_b, _g1, g2 = self._setup_dos_grupos_con_socio_en_uno()

        with as_user(s_a.user):
            self.assertFalse(
                frappe.has_permission(
                    "Grupo Familiar", "read", doc=g2.name, user=s_a.user
                )
            )
            with self.assertRaises(frappe.PermissionError):
                frappe.has_permission(
                    "Grupo Familiar", "read", doc=g2.name, user=s_a.user, throw=True
                )


class TestGrupoFamiliarIsolationViaTutorNoSocio(MembersTestCase):
    """El usuario es un Tutor No Socio titular activo de un grupo."""

    def test_user_de_tutor_ve_solo_su_grupo(self) -> None:
        ensure_role_socio_exists()

        tutor_a = insert_tutor_no_socio(dni="20111000", email="tutor.a@example.com")
        provision_user_for_tutor_no_socio(tutor_a.name)
        tutor_a.reload()
        g_a = insert_grupo_familiar_solo_tutor(
            tutor_a.name,
            nombre_grupo="Familia Tutor A",
            apellido_principal="A",
        )

        tutor_b = insert_tutor_no_socio(dni="20222000", email="tutor.b@example.com")
        provision_user_for_tutor_no_socio(tutor_b.name)
        tutor_b.reload()
        g_b = insert_grupo_familiar_solo_tutor(
            tutor_b.name,
            nombre_grupo="Familia Tutor B",
            apellido_principal="B",
        )

        with as_user(tutor_a.user):
            names = frappe.get_list("Grupo Familiar", pluck="name")
            self.assertIn(g_a.name, names)
            self.assertNotIn(g_b.name, names)

            self.assertFalse(
                frappe.has_permission(
                    "Grupo Familiar", "read", doc=g_b.name, user=tutor_a.user
                )
            )
            with self.assertRaises(frappe.PermissionError):
                frappe.has_permission(
                    "Grupo Familiar",
                    "read",
                    doc=g_b.name,
                    user=tutor_a.user,
                    throw=True,
                )


class TestGrupoFamiliarIsolationAdministrator(MembersTestCase):
    def test_administrator_ve_todos(self) -> None:
        ensure_role_socio_exists()

        s1 = insert_socio(dni="30333000", email="s.adm1@example.com")
        g1 = insert_grupo_familiar_solo_socio(s1.name, nombre_grupo="Adm A")
        s2 = insert_socio(dni="30444000", email="s.adm2@example.com")
        g2 = insert_grupo_familiar_solo_socio(s2.name, nombre_grupo="Adm B")

        names = frappe.get_list("Grupo Familiar", pluck="name")
        self.assertIn(g1.name, names)
        self.assertIn(g2.name, names)

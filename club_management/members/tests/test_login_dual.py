"""Tests del `auth_hook` `resolve_login_user`.

Cubre los 8 escenarios de `club_management/specs/login_dual.md`.

No ejercemos el `LoginManager` real ni el flujo HTTP de Frappe: la función
`resolve_login_user` recibe un objeto con atributo `user` y lo reescribe in
place, así que un fake simple alcanza. Esto desacopla los tests de internals
del framework y los hace rápidos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe

from club_management.members.auth.dual_login import resolve_login_user
from club_management.members.services.user_provisioning import (
    provision_user_for_socio,
    provision_user_for_tutor_no_socio,
)
from club_management.members.test_helpers import (
    MembersTestCase,
    insert_socio,
    insert_tutor_no_socio,
)


@dataclass
class FakeLoginManager:
    """Stand-in del `LoginManager` con sólo lo que el hook necesita."""

    user: Any = ""


def _ensure_role_socio_exists() -> None:
    if not frappe.db.exists("Role", "Socio"):
        frappe.get_doc(
            {"doctype": "Role", "role_name": "Socio", "desk_access": 0}
        ).insert(ignore_permissions=True)


class TestResolveLoginUserBasico(MembersTestCase):
    def test_input_vacio_no_modifica_nada(self) -> None:
        lm = FakeLoginManager(user="")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "")

    def test_input_none_no_modifica_nada(self) -> None:
        lm = FakeLoginManager(user=None)
        resolve_login_user(lm)
        self.assertIsNone(lm.user)

    def test_email_no_se_modifica(self) -> None:
        lm = FakeLoginManager(user="ana@example.com")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "ana@example.com")

    def test_dni_numerico_no_se_modifica(self) -> None:
        # Frappe nativo resuelve User.username = DNI cuando
        # allow_login_using_user_name = 1; el hook no debe interferir.
        lm = FakeLoginManager(user="30123456")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "30123456")


class TestResolveLoginUserSocio(MembersTestCase):
    def test_socio_number_valido_resuelve_email(self) -> None:
        _ensure_role_socio_exists()
        socio = insert_socio(
            dni="30100200",
            email="ana.login@example.com",
        )
        provision_user_for_socio(socio.name)
        socio.reload()
        self.assertEqual(socio.user, "ana.login@example.com")

        lm = FakeLoginManager(user=socio.name)
        resolve_login_user(lm)

        self.assertEqual(lm.user, "ana.login@example.com")

    def test_socio_inexistente_no_modifica_nada(self) -> None:
        usr_inexistente = "SOC-2099-9999"
        lm = FakeLoginManager(user=usr_inexistente)
        resolve_login_user(lm)
        self.assertEqual(lm.user, usr_inexistente)

    def test_socio_sin_user_no_resuelve(self) -> None:
        socio = insert_socio(
            dni="30100201",
            email="huerfano@example.com",
        )
        self.assertFalse(socio.user)

        lm = FakeLoginManager(user=socio.name)
        resolve_login_user(lm)

        self.assertEqual(lm.user, socio.name)


class TestResolveLoginUserTutorNoSocio(MembersTestCase):
    def test_tns_number_valido_resuelve_email(self) -> None:
        _ensure_role_socio_exists()
        tutor = insert_tutor_no_socio(
            dni="20100200",
            email="juan.login@example.com",
        )
        provision_user_for_tutor_no_socio(tutor.name)
        tutor.reload()
        self.assertEqual(tutor.user, "juan.login@example.com")

        lm = FakeLoginManager(user=tutor.name)
        resolve_login_user(lm)

        self.assertEqual(lm.user, "juan.login@example.com")

    def test_tns_inexistente_no_modifica_nada(self) -> None:
        usr_inexistente = "TNS-2099-9999"
        lm = FakeLoginManager(user=usr_inexistente)
        resolve_login_user(lm)
        self.assertEqual(lm.user, usr_inexistente)


class TestResolveLoginUserFormatoEstricto(MembersTestCase):
    """Inputs con formato parecido pero inválido no deben resolver."""

    def test_soc_con_anio_corto_no_resuelve(self) -> None:
        lm = FakeLoginManager(user="SOC-26-0001")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "SOC-26-0001")

    def test_soc_con_numero_corto_no_resuelve(self) -> None:
        lm = FakeLoginManager(user="SOC-2026-1")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "SOC-2026-1")

    def test_tns_con_numero_corto_no_resuelve(self) -> None:
        lm = FakeLoginManager(user="TNS-2026-1")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "TNS-2026-1")

    def test_prefijo_parecido_no_resuelve(self) -> None:
        # No reemplaza strings que casualmente empiezan con SOC- o TNS-.
        lm = FakeLoginManager(user="SOCIO-2026-0001")
        resolve_login_user(lm)
        self.assertEqual(lm.user, "SOCIO-2026-0001")

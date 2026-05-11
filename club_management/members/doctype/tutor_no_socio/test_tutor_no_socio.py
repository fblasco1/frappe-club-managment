"""Tests rojos del DocType `Tutor No Socio` (Sprint 0).

Cubre los escenarios principales de
`club_management/specs/tutor_no_socio_minimo.md`:
- Mayor de edad obligatorio.
- `dni` único.
- `email` puede repetirse con un Socio familiar.
- Naming por serie `TNS-{YYYY}-####`.
- Provisión de `User` cuando el email está libre.
- Bloqueo de creación de `User` cuando el email ya está tomado.
- Sin `User` propio también es válido.

Ejecución:

    bench --site <site> run-tests --app club_management \
        --module club_management.members.doctype.tutor_no_socio.test_tutor_no_socio
"""

from __future__ import annotations

import unittest

import frappe

from club_management.members.test_helpers import (
    MembersTestCase,
    adult_birthdate,
    insert_socio,
    insert_tutor_no_socio,
    make_tutor_no_socio_payload,
)


class TestTutorNoSocioCamposObligatorios(MembersTestCase):
    def test_alta_basica_es_valida(self) -> None:
        tutor = insert_tutor_no_socio()
        self.assertTrue(tutor.name.startswith("TNS-"))

    def test_dni_obligatorio(self) -> None:
        payload = make_tutor_no_socio_payload(dni="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_email_obligatorio(self) -> None:
        payload = make_tutor_no_socio_payload(email="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_dni_unico(self) -> None:
        insert_tutor_no_socio()
        with self.assertRaises(frappe.UniqueValidationError):
            insert_tutor_no_socio(email="otro@example.com")


class TestTutorNoSocioMayorDeEdad(MembersTestCase):
    def test_menor_de_18_falla(self) -> None:
        payload = make_tutor_no_socio_payload(
            fecha_nacimiento=adult_birthdate(17),
        )
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_exactamente_18_es_valido(self) -> None:
        tutor = insert_tutor_no_socio(fecha_nacimiento=adult_birthdate(18))
        self.assertEqual(tutor.fecha_nacimiento, adult_birthdate(18))


class TestTutorNoSocioEmailCompartido(MembersTestCase):
    def test_email_puede_coincidir_con_socio_familiar(self) -> None:
        insert_socio(dni="30123456", email="familia@example.com")
        tutor = insert_tutor_no_socio(
            dni="20111111",
            email="familia@example.com",
        )
        self.assertEqual(tutor.email, "familia@example.com")


class TestTutorNoSocioProvisionUser(MembersTestCase):
    """`Tutor No Socio.user` se provisiona con la misma política que Socio."""

    def test_provisiona_user_cuando_email_libre(self) -> None:
        from club_management.members.services.user_provisioning import (
            provision_user_for_tutor_no_socio,
        )

        tutor = insert_tutor_no_socio(
            email="papa.libre@example.com",
            dni="20999999",
        )
        provision_user_for_tutor_no_socio(tutor.name)
        tutor.reload()
        self.assertEqual(tutor.user, "papa.libre@example.com")

        user_doc = frappe.get_doc("User", "papa.libre@example.com")
        self.assertEqual(user_doc.username, "20999999")
        self.assertEqual(user_doc.user_type, "Website User")
        self.assertEqual(user_doc.enabled, 1)
        self.assertIn(
            "Socio",
            [r.role for r in user_doc.get("roles", [])],
        )

    def test_bloquea_cuando_email_ya_tiene_user(self) -> None:
        from club_management.members.services.user_provisioning import (
            provision_user_for_tutor_no_socio,
        )

        otro_socio = insert_socio(
            dni="30888888",
            email="papa@example.com",
        )
        # Provisionamos User para ese Socio primero (asumimos un helper análogo)
        from club_management.members.services.user_provisioning import (
            provision_user_for_socio,
        )

        provision_user_for_socio(otro_socio.name)

        tutor = insert_tutor_no_socio(
            dni="20111111",
            email="papa@example.com",
        )
        with self.assertRaises(frappe.ValidationError):
            provision_user_for_tutor_no_socio(tutor.name)
        tutor.reload()
        self.assertFalse(tutor.user)

    def test_sin_user_propio_es_valido(self) -> None:
        tutor = insert_tutor_no_socio()
        self.assertFalse(tutor.user)


if __name__ == "__main__":
    unittest.main()

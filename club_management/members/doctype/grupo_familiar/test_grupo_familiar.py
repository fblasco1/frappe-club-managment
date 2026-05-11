"""Tests rojos del DocType `Grupo Familiar` (Sprint 0).

Cubre los escenarios principales de
`club_management/specs/grupo_familiar_minimo.md`:
- Alta con un único titular Socio (auto-incorporación como miembro).
- Alta con un único titular Tutor No Socio (sin miembros).
- Alta con cotitulares (padre + madre).
- Exactamente un titular activo principal.
- Titular menor de edad rechazado.
- Unicidad cross-grupo de la titularidad por persona.
- `get_titular_principal()`.

Ejecución:

    bench --site <site> run-tests --app club_management \
        --module club_management.members.doctype.grupo_familiar.test_grupo_familiar
"""

from __future__ import annotations

import unittest

import frappe

from club_management.members.test_helpers import (
    MembersTestCase,
    adult_birthdate,
    insert_grupo_familiar_solo_socio,
    insert_grupo_familiar_solo_tutor,
    insert_socio,
    insert_tutor_no_socio,
)


class TestGrupoFamiliarTitularSocio(MembersTestCase):
    def test_alta_con_titular_socio_agrega_como_miembro(self) -> None:
        socio = insert_socio()
        grupo = insert_grupo_familiar_solo_socio(socio.name)
        self.assertEqual(len(grupo.titulares), 1)
        fila_titular = grupo.titulares[0]
        self.assertEqual(fila_titular.tipo_titular, "Socio")
        self.assertEqual(fila_titular.titular, socio.name)
        self.assertEqual(fila_titular.es_principal, 1)

        socios_miembros = [m.socio for m in grupo.miembros if not m.hasta]
        self.assertIn(socio.name, socios_miembros)

    def test_get_titular_principal_devuelve_socio(self) -> None:
        socio = insert_socio()
        grupo = insert_grupo_familiar_solo_socio(socio.name)
        tipo, name = grupo.get_titular_principal()
        self.assertEqual(tipo, "Socio")
        self.assertEqual(name, socio.name)


class TestGrupoFamiliarTitularTutorNoSocio(MembersTestCase):
    def test_alta_con_titular_tutor_sin_miembros(self) -> None:
        tutor = insert_tutor_no_socio()
        grupo = insert_grupo_familiar_solo_tutor(tutor.name)
        self.assertEqual(len(grupo.titulares), 1)
        self.assertEqual(grupo.titulares[0].tipo_titular, "Tutor No Socio")
        self.assertEqual(grupo.titulares[0].titular, tutor.name)
        self.assertEqual(len(grupo.miembros or []), 0)


class TestGrupoFamiliarCotitulares(MembersTestCase):
    def test_alta_con_padre_y_madre_como_cotitulares(self) -> None:
        padre = insert_tutor_no_socio(dni="20111111", email="papa@example.com")
        madre = insert_tutor_no_socio(dni="20222222", email="mama@example.com")

        grupo = frappe.get_doc(
            {
                "doctype": "Grupo Familiar",
                "nombre_grupo": "Familia Pérez",
                "apellido_principal": "Pérez",
                "titulares": [
                    {
                        "tipo_titular": "Tutor No Socio",
                        "titular": padre.name,
                        "es_principal": 1,
                        "rol": "Padre",
                    },
                    {
                        "tipo_titular": "Tutor No Socio",
                        "titular": madre.name,
                        "es_principal": 0,
                        "rol": "Madre",
                    },
                ],
            }
        )
        grupo.insert(ignore_permissions=True)
        self.assertEqual(len(grupo.titulares), 2)
        tipo, name = grupo.get_titular_principal()
        self.assertEqual((tipo, name), ("Tutor No Socio", padre.name))

    def test_dos_principales_activos_falla(self) -> None:
        padre = insert_tutor_no_socio(dni="20111111", email="papa@example.com")
        madre = insert_tutor_no_socio(dni="20222222", email="mama@example.com")

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Grupo Familiar",
                    "nombre_grupo": "Familia Pérez",
                    "apellido_principal": "Pérez",
                    "titulares": [
                        {
                            "tipo_titular": "Tutor No Socio",
                            "titular": padre.name,
                            "es_principal": 1,
                            "rol": "Padre",
                        },
                        {
                            "tipo_titular": "Tutor No Socio",
                            "titular": madre.name,
                            "es_principal": 1,
                            "rol": "Madre",
                        },
                    ],
                }
            ).insert(ignore_permissions=True)

    def test_cero_principales_activos_falla(self) -> None:
        padre = insert_tutor_no_socio(dni="20111111", email="papa@example.com")

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Grupo Familiar",
                    "nombre_grupo": "Familia Pérez",
                    "apellido_principal": "Pérez",
                    "titulares": [
                        {
                            "tipo_titular": "Tutor No Socio",
                            "titular": padre.name,
                            "es_principal": 0,
                            "rol": "Padre",
                        },
                    ],
                }
            ).insert(ignore_permissions=True)


class TestGrupoFamiliarMayorDeEdad(MembersTestCase):
    def test_titular_socio_menor_de_edad_falla(self) -> None:
        socio_joven = insert_socio(
            dni="30888888",
            email="joven@example.com",
            fecha_nacimiento=adult_birthdate(15),
        )
        with self.assertRaises(frappe.ValidationError):
            insert_grupo_familiar_solo_socio(socio_joven.name)


class TestGrupoFamiliarUnicidad(MembersTestCase):
    def test_una_persona_no_puede_encabezar_dos_grupos(self) -> None:
        tutor = insert_tutor_no_socio()
        insert_grupo_familiar_solo_tutor(tutor.name, nombre_grupo="Familia A")
        with self.assertRaises(frappe.ValidationError):
            insert_grupo_familiar_solo_tutor(tutor.name, nombre_grupo="Familia B")


if __name__ == "__main__":
    unittest.main()

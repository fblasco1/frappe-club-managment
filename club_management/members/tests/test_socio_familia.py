"""Tests E2E cross-DocType para el flujo Socio menor ↔ tutor ↔ Grupo Familiar.

Estos tests integran los tres DocTypes del Sprint 0 (`Socio`, `Tutor No Socio` y
`Grupo Familiar`) en escenarios representativos del dominio del club, alineados
con los specs:

- `club_management/specs/socio_minimo.md`
- `club_management/specs/tutor_no_socio_minimo.md`
- `club_management/specs/grupo_familiar_minimo.md`

Casos cubiertos:

1. Padre `Tutor No Socio` como titular principal con dos hijos menores en el
   mismo grupo (escenario "padre asocia a sus dos hijos").
2. Familia mixta: padre `Socio` + madre `Tutor No Socio` cotitulares, hijo
   menor puede declarar como tutor a cualquiera de los dos.
3. Un titular dado de baja (`hasta` poblado) **no** puede figurar como tutor
   activo del menor.
4. `get_titular_principal()` devuelve un `Tutor No Socio` cuando éste es el
   principal del grupo.
5. La invariante de unicidad cross-grupo se mantiene aunque el conflicto sea
   entre un `Socio` titular en un grupo y otro grupo activo con el mismo Socio.

Lo que **NO** se cubre acá (queda para Sprint 1):

- Sincronización automática de `Socio.grupo_familiar` → fila en
  `Grupo Familiar.miembros`. Por ahora `Socio._validate_menor()` valida la
  referencia, pero la administración de la fila `miembros` se hace explícita
  en el flujo de Solicitud de Asociación.
"""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import (
    MembersTestCase,
    adult_birthdate,
    insert_grupo_familiar_solo_socio,
    insert_grupo_familiar_solo_tutor,
    insert_socio,
    insert_tutor_no_socio,
    make_socio_payload,
    minor_birthdate,
)


class TestFamiliaTutorNoSocioConHijos(MembersTestCase):
    """Padre `Tutor No Socio` con dos hijos menores en el mismo grupo."""

    def _setup_familia(self):
        padre = insert_tutor_no_socio(
            dni="20111111",
            email="papa@example.com",
            fecha_nacimiento=adult_birthdate(45),
        )
        grupo = insert_grupo_familiar_solo_tutor(
            padre.name,
            nombre_grupo="Familia Pérez",
            apellido_principal="Pérez",
        )
        return padre, grupo

    def test_dos_hijos_menores_comparten_tutor_y_grupo(self) -> None:
        padre, grupo = self._setup_familia()

        hijo1 = insert_socio(
            dni="55111111",
            email="hijo1@example.com",
            fecha_nacimiento=minor_birthdate(10),
            categoria="Menor",
            tipo_tutor="Tutor No Socio",
            tutor=padre.name,
            grupo_familiar=grupo.name,
        )
        hijo2 = insert_socio(
            dni="55222222",
            email="hijo2@example.com",
            fecha_nacimiento=minor_birthdate(7),
            categoria="Menor",
            tipo_tutor="Tutor No Socio",
            tutor=padre.name,
            grupo_familiar=grupo.name,
        )

        self.assertEqual(hijo1.grupo_familiar, grupo.name)
        self.assertEqual(hijo2.grupo_familiar, grupo.name)
        self.assertEqual(hijo1.tutor, padre.name)
        self.assertEqual(hijo2.tutor, padre.name)

    def test_get_titular_principal_devuelve_tutor_no_socio(self) -> None:
        padre, grupo = self._setup_familia()

        principal = grupo.get_titular_principal()

        self.assertEqual(principal, ("Tutor No Socio", padre.name))


class TestFamiliaMixtaCotitulares(MembersTestCase):
    """Padre Socio adulto + madre Tutor No Socio como cotitulares del grupo."""

    def _setup_familia(self):
        padre_socio = insert_socio(
            dni="30111111",
            email="papa.socio@example.com",
            fecha_nacimiento=adult_birthdate(40),
        )
        madre_tutor = insert_tutor_no_socio(
            dni="20999999",
            email="mama.tutora@example.com",
            fecha_nacimiento=adult_birthdate(38),
        )
        grupo = frappe.get_doc(
            {
                "doctype": "Grupo Familiar",
                "nombre_grupo": "Familia García",
                "apellido_principal": "García",
                "titulares": [
                    {
                        "tipo_titular": "Socio",
                        "titular": padre_socio.name,
                        "es_principal": 1,
                        "rol": "Titular",
                    },
                    {
                        "tipo_titular": "Tutor No Socio",
                        "titular": madre_tutor.name,
                        "es_principal": 0,
                        "rol": "Madre",
                    },
                ],
            }
        )
        grupo.insert(ignore_permissions=True)
        return padre_socio, madre_tutor, grupo

    def test_hijo_puede_declarar_padre_socio_como_tutor(self) -> None:
        padre_socio, _madre_tutor, grupo = self._setup_familia()

        hijo = insert_socio(
            dni="55333333",
            email="hijo.mixto@example.com",
            fecha_nacimiento=minor_birthdate(11),
            categoria="Menor",
            tipo_tutor="Socio",
            tutor=padre_socio.name,
            grupo_familiar=grupo.name,
        )

        self.assertEqual(hijo.tutor, padre_socio.name)
        self.assertEqual(hijo.tipo_tutor, "Socio")

    def test_hijo_puede_declarar_madre_tutora_como_tutor(self) -> None:
        _padre_socio, madre_tutor, grupo = self._setup_familia()

        hijo = insert_socio(
            dni="55444444",
            email="hijo.mixto2@example.com",
            fecha_nacimiento=minor_birthdate(8),
            categoria="Menor",
            tipo_tutor="Tutor No Socio",
            tutor=madre_tutor.name,
            grupo_familiar=grupo.name,
        )

        self.assertEqual(hijo.tutor, madre_tutor.name)
        self.assertEqual(hijo.tipo_tutor, "Tutor No Socio")


class TestTitularDadoDeBajaNoEsTutorValido(MembersTestCase):
    """Si un titular tiene `hasta` poblado, ya no es titular activo y no puede
    figurar como tutor del menor."""

    def test_tutor_inactivo_falla(self) -> None:
        padre = insert_tutor_no_socio(
            dni="20888888",
            email="papa.inactivo@example.com",
            fecha_nacimiento=adult_birthdate(50),
        )
        grupo = insert_grupo_familiar_solo_tutor(
            padre.name,
            nombre_grupo="Familia Inactiva",
            apellido_principal="Inactivo",
        )

        grupo.titulares[0].hasta = "2020-01-01"
        try:
            grupo.append(
                "titulares",
                {
                    "tipo_titular": "Tutor No Socio",
                    "titular": insert_tutor_no_socio(
                        dni="20777777",
                        email="papa.reemplazo@example.com",
                        fecha_nacimiento=adult_birthdate(48),
                    ).name,
                    "es_principal": 1,
                    "rol": "Padre",
                },
            )
            grupo.save(ignore_permissions=True)
        except frappe.ValidationError:
            self.fail("El reemplazo del titular principal debería ser válido")

        payload = make_socio_payload(
            dni="55555555",
            email="hijo.huerfano@example.com",
            fecha_nacimiento=minor_birthdate(9),
            categoria="Menor",
            tipo_tutor="Tutor No Socio",
            tutor=padre.name,
            grupo_familiar=grupo.name,
        )
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(payload).insert(ignore_permissions=True)


class TestTitularidadUnicaCrossGrupoMixta(MembersTestCase):
    """Una persona (Socio o Tutor No Socio) no puede ser titular activo en
    dos grupos a la vez, incluso si los grupos son de distinto tipo."""

    def test_socio_titular_no_puede_repetirse_en_otro_grupo(self) -> None:
        socio = insert_socio(
            dni="30222222",
            email="socio.unico@example.com",
            fecha_nacimiento=adult_birthdate(36),
        )
        insert_grupo_familiar_solo_socio(
            socio.name,
            nombre_grupo="Familia A",
            apellido_principal="A",
        )

        payload = {
            "doctype": "Grupo Familiar",
            "nombre_grupo": "Familia B",
            "apellido_principal": "B",
            "titulares": [
                {
                    "tipo_titular": "Socio",
                    "titular": socio.name,
                    "es_principal": 1,
                    "rol": "Titular",
                }
            ],
        }
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_tutor_no_socio_no_puede_repetirse_en_otro_grupo(self) -> None:
        tutor = insert_tutor_no_socio(
            dni="20666666",
            email="tutor.unico@example.com",
            fecha_nacimiento=adult_birthdate(42),
        )
        insert_grupo_familiar_solo_tutor(
            tutor.name,
            nombre_grupo="Familia C",
            apellido_principal="C",
        )

        payload = {
            "doctype": "Grupo Familiar",
            "nombre_grupo": "Familia D",
            "apellido_principal": "D",
            "titulares": [
                {
                    "tipo_titular": "Tutor No Socio",
                    "titular": tutor.name,
                    "es_principal": 1,
                    "rol": "Padre",
                }
            ],
        }
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

"""Helpers de tests para el módulo `Members`.

Centralizan la creación de fixtures válidos (Socio adulto, Tutor No Socio,
Grupo Familiar, Solicitud de Asociación) con defaults coherentes con los specs
`socio_minimo.md`, `tutor_no_socio_minimo.md` y `grupo_familiar_minimo.md`.

También expone `MembersTestCase`, una base de tests que aísla cada método
con un SAVEPOINT y un ROLLBACK posterior; esto garantiza que tests dentro de
una misma clase no interfieran entre sí (FrappeTestCase en Frappe v16 no hace
rollback automático entre métodos para los tests de la categoría legacy).

Los helpers NO deben usarse en código de producción.
"""

from __future__ import annotations

import datetime
from typing import Any

import frappe
from frappe.tests.utils import FrappeTestCase


_SAVEPOINT_NAME = "members_test_savepoint"


class MembersTestCase(FrappeTestCase):
	"""Base de tests del módulo Members con aislamiento por SAVEPOINT.

	Cada test entra dentro de un SAVEPOINT en `setUp` y hace rollback al
	mismo SAVEPOINT en `tearDown`, garantizando que el estado de la base
	de datos vuelve a lo que había antes del test (compatible con MariaDB
	y PostgreSQL).
	"""

	def setUp(self) -> None:
		super().setUp()
		frappe.db.savepoint(_SAVEPOINT_NAME)

	def tearDown(self) -> None:
		frappe.db.rollback(save_point=_SAVEPOINT_NAME)
		super().tearDown()


# Paths simbólicos para campos Attach.
# Frappe no exige que el archivo exista físicamente para guardar el campo.
DUMMY_FOTO_PERFIL = "/files/test_foto_perfil.jpg"
DUMMY_DNI_FRENTE = "/files/test_dni_frente.jpg"
DUMMY_DNI_DORSO = "/files/test_dni_dorso.jpg"
DUMMY_FICHA_MEDICA = "/files/test_ficha_medica.pdf"


def adult_birthdate(years: int = 35) -> datetime.date:
    """Devuelve una fecha de nacimiento que deja a la persona con `years` años."""
    today = datetime.date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(month=2, day=28, year=today.year - years)


def minor_birthdate(years: int = 12) -> datetime.date:
    """Devuelve una fecha de nacimiento que deja a la persona con `years` años."""
    return adult_birthdate(years)


def make_socio_payload(**overrides: Any) -> dict[str, Any]:
    """Defaults para un `Socio` adulto válido (categoría `Activo`).

    Los tests pasan `**overrides` para mutar campos puntuales y probar
    invariantes.
    """
    payload: dict[str, Any] = {
        "doctype": "Socio",
        "nombre": "Ana",
        "apellido": "Pérez",
        "dni": "30123456",
        "nacionalidad": "Argentina",
        "fecha_nacimiento": adult_birthdate(35),
        "genero": "Femenino",
        "email": "ana@example.com",
        "telefono": "+541112345678",
        "domicilio": "Calle Falsa 123",
        "localidad": "CABA",
        "provincia": "CABA",
        "codigo_postal": "1414",
        "categoria": "Activo",
        "foto_perfil": DUMMY_FOTO_PERFIL,
        "dni_frente": DUMMY_DNI_FRENTE,
        "dni_dorso": DUMMY_DNI_DORSO,
        "ficha_medica": DUMMY_FICHA_MEDICA,
    }
    payload.update(overrides)
    return payload


def make_tutor_no_socio_payload(**overrides: Any) -> dict[str, Any]:
    """Defaults para un `Tutor No Socio` válido."""
    payload: dict[str, Any] = {
        "doctype": "Tutor No Socio",
        "nombre": "Juan",
        "apellido": "Pérez",
        "dni": "20111111",
        "nacionalidad": "Argentina",
        "fecha_nacimiento": adult_birthdate(45),
        "genero": "Masculino",
        "email": "juan@example.com",
        "telefono": "+541198765432",
        "domicilio": "Calle Falsa 123",
        "localidad": "CABA",
        "provincia": "CABA",
        "codigo_postal": "1414",
    }
    payload.update(overrides)
    return payload


def insert_socio(**overrides: Any) -> "frappe.model.document.Document":
    """Inserta un `Socio` con defaults válidos y devuelve el doc persistido."""
    doc = frappe.get_doc(make_socio_payload(**overrides))
    doc.insert(ignore_permissions=True)
    return doc


def insert_tutor_no_socio(**overrides: Any) -> "frappe.model.document.Document":
    """Inserta un `Tutor No Socio` con defaults válidos."""
    doc = frappe.get_doc(make_tutor_no_socio_payload(**overrides))
    doc.insert(ignore_permissions=True)
    return doc


def insert_grupo_familiar_solo_socio(
    socio_name: str,
    **overrides: Any,
) -> "frappe.model.document.Document":
    """Inserta un `Grupo Familiar` con un único titular `Socio` principal."""
    payload: dict[str, Any] = {
        "doctype": "Grupo Familiar",
        "nombre_grupo": overrides.pop("nombre_grupo", "Familia Test"),
        "apellido_principal": overrides.pop("apellido_principal", "Pérez"),
        "titulares": [
            {
                "tipo_titular": "Socio",
                "titular": socio_name,
                "es_principal": 1,
                "rol": "Titular",
            }
        ],
    }
    payload.update(overrides)
    doc = frappe.get_doc(payload)
    doc.insert(ignore_permissions=True)
    return doc


def insert_grupo_familiar_solo_tutor(
    tutor_no_socio_name: str,
    **overrides: Any,
) -> "frappe.model.document.Document":
    """Inserta un `Grupo Familiar` con un único titular `Tutor No Socio` principal."""
    payload: dict[str, Any] = {
        "doctype": "Grupo Familiar",
        "nombre_grupo": overrides.pop("nombre_grupo", "Familia Test"),
        "apellido_principal": overrides.pop("apellido_principal", "Pérez"),
        "titulares": [
            {
                "tipo_titular": "Tutor No Socio",
                "titular": tutor_no_socio_name,
                "es_principal": 1,
                "rol": "Padre",
            }
        ],
    }
    payload.update(overrides)
    doc = frappe.get_doc(payload)
    doc.insert(ignore_permissions=True)
    return doc


def add_miembro_socio(
    grupo_name: str,
    socio_name: str,
    rol: str = "Hijo",
) -> "frappe.model.document.Document":
    """Agrega un `Socio` como miembro del grupo (útil para tests de aislamiento)."""
    grupo = frappe.get_doc("Grupo Familiar", grupo_name)
    grupo.append(
        "miembros",
        {
            "socio": socio_name,
            "rol": rol,
            "desde": datetime.date.today(),
        },
    )
    grupo.save(ignore_permissions=True)
    return grupo


def ensure_role_socio_exists() -> None:
    """Asegura que el rol Frappe `Socio` exista para que `provision_user_*`
    pueda asignarlo y los tests de aislamiento puedan setear el `frappe.session.user`."""
    if not frappe.db.exists("Role", "Socio"):
        frappe.get_doc(
            {"doctype": "Role", "role_name": "Socio", "desk_access": 0}
        ).insert(ignore_permissions=True)

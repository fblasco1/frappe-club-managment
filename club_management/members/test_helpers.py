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
# Frappe NO exige que el archivo exista físicamente para guardar el campo en
# DocTypes propios (Socio, Tutor No Socio, Grupo Familiar, Solicitud
# Asociacion al insertarse via `insert_solicitud_asociacion`); el campo
# `Attach` solo almacena la URL como string. Estos paths son útiles para
# probar invariantes que NO atraviesan `validate_ficha_medica_from_url`
# (que SÍ lee el archivo del disco). Para tests que entran al endpoint
# público `submit_solicitud` usar `make_test_file(...)` con un PDF
# válido como `MINIMAL_VALID_PDF`.
DUMMY_FOTO_PERFIL = "/files/test_foto_perfil.jpg"
DUMMY_DNI_FRENTE = "/files/test_dni_frente.jpg"
DUMMY_DNI_DORSO = "/files/test_dni_dorso.jpg"
DUMMY_FICHA_MEDICA = "/files/test_ficha_medica.pdf"
DUMMY_DNI_FRENTE_TUTOR = "/files/test_dni_frente_tutor.jpg"
DUMMY_DNI_DORSO_TUTOR = "/files/test_dni_dorso_tutor.jpg"
DUMMY_FOTO_PERFIL_TUTOR = "/files/test_foto_perfil_tutor.jpg"


# PDF mínimo estructuralmente válido (~180 bytes). pypdf 6.x lo parsea sin
# error: tiene header, 3 objetos (catalog, pages, page), xref table,
# trailer y %%EOF. Para tests del endpoint público y de
# `validate_ficha_medica_from_url` que necesitan que Frappe acepte el
# File sin romper en el hook de procesamiento de PDFs.
MINIMAL_VALID_PDF: bytes = (
    b"%PDF-1.0\n"
    b"1 0 obj<</Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Parent 2 0 R>>endobj\n"
    b"xref\n"
    b"0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000044 00000 n \n"
    b"0000000083 00000 n \n"
    b"trailer<</Root 1 0 R/Size 4>>\n"
    b"startxref\n"
    b"112\n"
    b"%%EOF\n"
)


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


def make_solicitud_asociacion_payload(**overrides: Any) -> dict[str, Any]:
    """Defaults para una `Solicitud Asociacion` adulta válida (categoría `Activo`).

    Refleja la spec `solicitud_asociacion_publica.md` Sprint 1: campos del
    solicitante completos, sin bloque tutor (`mandatory_depends_on` no
    aplica para `Activo`).

    Nota: el `name` técnico del DocType es `Solicitud Asociacion` (ASCII
    puro, sin tilde y sin "de"). En UX el label final será "Solicitud de
    Asociación" vía traducción (i18n) en un sprint dedicado.
    """
    payload: dict[str, Any] = {
        "doctype": "Solicitud Asociacion",
        "nombre": "Ana",
        "apellido": "Pérez",
        "dni": "30123456",
        "nacionalidad": "Argentina",
        "fecha_nacimiento": adult_birthdate(35),
        "genero": "Femenino",
        "categoria_solicitada": "Activo",
        "email": "ana@example.com",
        "telefono": "+541112345678",
        "calle": "Calle Falsa 123",
        "localidad": "CABA",
        "provincia": "CABA",
        "codigo_postal": "1414",
        "dni_frente": DUMMY_DNI_FRENTE,
        "dni_dorso": DUMMY_DNI_DORSO,
        "foto_perfil": DUMMY_FOTO_PERFIL,
        "ficha_medica": DUMMY_FICHA_MEDICA,
    }
    payload.update(overrides)
    return payload


def make_solicitud_menor_payload(**overrides: Any) -> dict[str, Any]:
    """Defaults para una `Solicitud de Asociación` de un menor con bloque tutor.

    Por default usa el caso "tutor no Socio" con email distinto al del menor
    (regla 2 de la "Decisión sobre `User` para menores"). Los tests pueden
    sobreescribir `email_tutor` para forzar el caso "email compartido".
    """
    payload = make_solicitud_asociacion_payload()
    payload.update(
        {
            "categoria_solicitada": "Menor",
            "fecha_nacimiento": minor_birthdate(12),
            "email": "ana.hija@example.com",
            "dni_tutor": "20111111",
            "nombre_tutor": "Juan",
            "apellido_tutor": "Pérez",
            "fecha_nacimiento_tutor": adult_birthdate(45),
            "nacionalidad_tutor": "Argentina",
            "genero_tutor": "Masculino",
            "email_tutor": "papa@example.com",
            "telefono_tutor": "+541198765432",
            "calle_tutor": "Calle Falsa 123",
            "localidad_tutor": "CABA",
            "provincia_tutor": "CABA",
            "codigo_postal_tutor": "1414",
            "rol_tutor": "Padre",
            "dni_frente_tutor": DUMMY_DNI_FRENTE_TUTOR,
            "dni_dorso_tutor": DUMMY_DNI_DORSO_TUTOR,
            "foto_perfil_tutor": DUMMY_FOTO_PERFIL_TUTOR,
        }
    )
    payload.update(overrides)
    return payload


def insert_solicitud_asociacion(**overrides: Any) -> "frappe.model.document.Document":
    """Inserta una `Solicitud de Asociación` adulta con defaults válidos."""
    doc = frappe.get_doc(make_solicitud_asociacion_payload(**overrides))
    doc.insert(ignore_permissions=True)
    return doc


def make_test_file(filename: str, content: bytes, is_private: int = 1) -> str:
    """Crea un `File` de Frappe con contenido binario y devuelve su `file_url`.

    Útil para tests que validan `ficha_medica` por magic numbers o tamaño:
    el helper `validate_ficha_medica_from_url` necesita un archivo real en
    disco para leer los primeros bytes y `os.path.getsize`.

    Por defecto el archivo se crea como **privado** (`is_private=1`,
    almacenado en `/private/files/`). Esto evita los hooks de
    procesamiento automático que Frappe v15 ejecuta sobre archivos
    públicos (p. ej. `pypdf` para PDFs), que rompen si el contenido no
    es estructuralmente válido. Para tests que necesitan un PDF
    "real" pasar `MINIMAL_VALID_PDF` como `content`.

    No se asocia a ningún DocType padre. El SAVEPOINT del `MembersTestCase`
    hace rollback del `File` doc en tearDown, pero el archivo físico en
    `/private/files/` queda en disco; eso es inocuo para el suite.
    """
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "content": content,
            "is_private": is_private,
            "decode": False,
        }
    ).insert(ignore_permissions=True)
    return file_doc.file_url


def ensure_role_socio_exists() -> None:
    """Asegura que el rol Frappe `Socio` exista con `desk_access = 0`.

    En Frappe v15+, el `User.update_user_type` auto-promueve a `"System User"`
    cualquier `User` que tenga al menos un rol con `desk_access = 1`. Como el
    portal de socios sólo debe acceder al Website, garantizamos
    `desk_access = 0` independientemente de cómo lo haya creado Frappe al
    sincronizar los DocPerms.
    """
    if not frappe.db.exists("Role", "Socio"):
        frappe.get_doc(
            {"doctype": "Role", "role_name": "Socio", "desk_access": 0}
        ).insert(ignore_permissions=True)
        return

    if frappe.db.get_value("Role", "Socio", "desk_access"):
        frappe.db.set_value("Role", "Socio", "desk_access", 0, update_modified=False)

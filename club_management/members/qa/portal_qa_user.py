"""Crea o actualiza el socio de QA del portal local (dev.localhost).

  bench --site dev.localhost execute club_management.members.qa.portal_qa_user.ensure
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils.password import update_password

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.members.services.user_provisioning import (
	_ensure_rol_portal_sin_desk,
	provision_user_for_socio,
)
from club_management.members.test_helpers import ensure_role_socio_exists, insert_socio

QA_EMAIL = "socio.portal.qa@icdpe.test"
QA_DNI = "90909090"
QA_PASSWORD = "PortalQa123!"


def ensure() -> dict[str, Any]:
	frappe.set_user("Administrator")
	ensure_role_socio_exists()
	_ensure_rol_portal_sin_desk("Socio")

	existing = frappe.db.get_value("Socio", {"email": QA_EMAIL}, "name")
	if existing:
		socio = frappe.get_doc("Socio", existing)
	else:
		socio = insert_socio(
			nombre="Portal",
			apellido="QA",
			dni=QA_DNI,
			email=QA_EMAIL,
			telefono_movil="+541100000001",
		)

	if not socio.user:
		if frappe.db.exists("User", QA_EMAIL):
			socio.db_set("user", QA_EMAIL, commit=False)
			socio.reload()
		else:
			provision_user_for_socio(socio.name)
			socio.reload()

	user = frappe.get_doc("User", socio.user)
	user.enabled = 1
	user.user_type = "Website User"
	if "Socio" not in [r.role for r in user.roles]:
		user.append("roles", {"role": "Socio"})
	user.flags.ignore_password_policy = True
	user.save(ignore_permissions=True)
	update_password(user.name, QA_PASSWORD)
	frappe.db.set_value(
		"Socio",
		socio.name,
		"estado",
		ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
		update_modified=False,
	)
	frappe.db.commit()
	return {
		"socio": socio.name,
		"email": QA_EMAIL,
		"dni": socio.dni,
		"password": QA_PASSWORD,
		"estado": ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
		"url": "http://localhost:3000/socios/login",
	}

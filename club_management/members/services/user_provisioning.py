"""Provisión de cuentas `User` para `Socio` y `Tutor No Socio`.

Reglas (Sprint 0 — ver `socio_minimo.md` y `tutor_no_socio_minimo.md`):

- `User.name` = email real de la persona; **no** se crean emails técnicos.
- `User.username` = DNI (permite login dual junto con el `auth_hook` que
  reconoce las series `SOC-…` y `TNS-…`).
- Si el email **ya está tomado** por otro `User`, la provisión falla con
  `frappe.ValidationError` y el `<Doc>.user` queda vacío.
- Rol asignado: `Socio` (decisión Sprint 0; se puede refinar a un rol `Tutor`
  separado en sprints posteriores).
"""

from __future__ import annotations

import frappe
from frappe import _

ROL_PORTAL = "Socio"


def provision_user_for_socio(socio_name: str) -> str:
	"""Provisiona un `User` para el `Socio` indicado y lo enlaza."""
	socio = frappe.get_doc("Socio", socio_name)
	user_name = _provision_user(email=socio.email, username=socio.dni)
	socio.db_set("user", user_name, commit=False)
	return user_name


def provision_user_for_tutor_no_socio(tutor_name: str) -> str:
	"""Provisiona un `User` para el `Tutor No Socio` indicado y lo enlaza."""
	tutor = frappe.get_doc("Tutor No Socio", tutor_name)
	user_name = _provision_user(email=tutor.email, username=tutor.dni)
	tutor.db_set("user", user_name, commit=False)
	return user_name


def _provision_user(*, email: str, username: str) -> str:
	if frappe.db.exists("User", email):
		frappe.throw(
			_("El email ya tiene cuenta en el portal; usá un email distinto o coordiná con Secretaría")
		)

	_assert_rol_existe(ROL_PORTAL)

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"username": username,
			"first_name": username,
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"roles": [{"role": ROL_PORTAL}],
		}
	)
	user.insert(ignore_permissions=True)
	return user.name


def _assert_rol_existe(rol: str) -> None:
	if frappe.db.exists("Role", rol):
		return
	frappe.get_doc({"doctype": "Role", "role_name": rol, "desk_access": 0}).insert(
		ignore_permissions=True
	)

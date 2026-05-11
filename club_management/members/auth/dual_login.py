"""Login dual: traducción de SOC-/TNS- al `User` asociado.

Implementación del `auth_hook` documentado en
`club_management/specs/login_dual.md`.

La función `resolve_login_user(login_manager)` se registra en
`hooks.auth_hooks` y se invoca **antes** de que Frappe valide la contraseña.
Su única responsabilidad es reescribir `login_manager.user` cuando el usuario
tipea un número de Socio o de Tutor No Socio; en cualquier otro caso (email,
DNI numérico, string vacío, formato inválido, registro inexistente o sin
`User` asociado) **no modifica nada** y deja que Frappe resuelva por su cuenta.
"""

from __future__ import annotations

import re
from typing import Any

import frappe


_SOC_PATTERN = re.compile(r"^SOC-\d{4}-\d{4,}$")
_TNS_PATTERN = re.compile(r"^TNS-\d{4}-\d{4,}$")


def resolve_login_user(login_manager: Any) -> None:
	usr = getattr(login_manager, "user", None)
	if not usr or not isinstance(usr, str):
		return

	if _SOC_PATTERN.match(usr):
		email = frappe.db.get_value("Socio", usr, "user")
		if email:
			login_manager.user = email
		return

	if _TNS_PATTERN.match(usr):
		email = frappe.db.get_value("Tutor No Socio", usr, "user")
		if email:
			login_manager.user = email
		return

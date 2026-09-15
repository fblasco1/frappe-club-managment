"""Socio QA Activo para reservas de espacios (dev.localhost).

  bench --site dev.localhost execute \\
    club_management.members.qa.portal_reservas_qa_user.ensure
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils.password import update_password

from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.services.user_provisioning import (
	_ensure_rol_portal_sin_desk,
	provision_user_for_socio,
)
from club_management.members.test_helpers import ensure_role_socio_exists, insert_socio
from club_management.spaces.services.portal_reservas import ITEM_ALQUILER_SOCIO

QA_EMAIL = "reserva.qa@icdpe.test"
QA_DNI = "91919191"
QA_PASSWORD = "ReservaQa123!"
QA_RATE = 15000.0


def _ensure_alquiler_item() -> None:
	if frappe.db.exists("Item", ITEM_ALQUILER_SOCIO):
		frappe.db.set_value(
			"Item",
			ITEM_ALQUILER_SOCIO,
			"standard_rate",
			QA_RATE,
			update_modified=False,
		)
		return
	group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": ITEM_ALQUILER_SOCIO,
			"item_name": "Alquiler canchas / espacios (ARS) — Temporal",
			"item_group": group,
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"standard_rate": QA_RATE,
		}
	).insert(ignore_permissions=True)


def ensure() -> dict[str, Any]:
	"""Crea/actualiza socio Activo + usuario portal para probar reservas."""
	frappe.set_user("Administrator")
	ensure_role_socio_exists()
	_ensure_rol_portal_sin_desk("Socio")
	_ensure_alquiler_item()

	existing = frappe.db.get_value("Socio", {"email": QA_EMAIL}, "name")
	if existing:
		socio = frappe.get_doc("Socio", existing)
	else:
		socio = insert_socio(
			nombre="Reservas",
			apellido="QA",
			dni=QA_DNI,
			email=QA_EMAIL,
			telefono_movil="+541100000091",
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

	if socio.estado != "Activo":
		cambiar_estado(socio.name, "Activo", motivo="QA reservas portal")
		socio.reload()

	# Asegurar número de socio visible
	if not socio.numero_socio:
		frappe.db.set_value(
			"Socio",
			socio.name,
			"numero_socio",
			int(socio.dni) if str(socio.dni).isdigit() else socio.name,
			update_modified=False,
		)

	espacios = frappe.get_all(
		"Espacio",
		filters={"alquilable": 1, "habilitado": 1},
		fields=["name", "titulo"],
		limit=5,
	)
	frappe.db.commit()
	return {
		"socio": socio.name,
		"email": QA_EMAIL,
		"dni": socio.dni or QA_DNI,
		"password": QA_PASSWORD,
		"estado": socio.estado,
		"tarifa_item": ITEM_ALQUILER_SOCIO,
		"tarifa": QA_RATE,
		"espacios_alquilables": espacios,
		"url": "http://localhost:3000/socios/login",
		"reservas_url": "http://localhost:3000/socios/reservas",
	}

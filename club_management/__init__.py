__version__ = "0.0.1"


def _apply_postgres_compat_on_import() -> None:
	"""Aplica parches ERPNext+PostgreSQL al cargar la app (idempotente)."""
	try:
		import frappe

		if not getattr(frappe.local, "site", None):
			return
		if not getattr(frappe.local, "db", None):
			return
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
	except Exception:
		return


_apply_postgres_compat_on_import()

"""Finance Settings: configuración del módulo de Finanzas (Single)."""

from __future__ import annotations

from frappe.model.document import Document


class FinanceSettings(Document):
	holiday_list: str | None

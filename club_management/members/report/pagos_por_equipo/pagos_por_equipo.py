# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.services.liquidacion_equipo import (
	get_pagos_por_equipo_data,
	get_pagos_report_columns,
)


def execute(filters: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	return get_pagos_report_columns(), get_pagos_por_equipo_data(filters or {})

# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.finance.services.informes_contables import ejecutar_ganancias_y_perdidas


def execute(filters: dict[str, Any] | None = None):
	return ejecutar_ganancias_y_perdidas(filters)

# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.members.services.deuda_socios import get_deuda_socios


def execute(filters: dict[str, Any] | None = None):
	return get_deuda_socios(filters or {})

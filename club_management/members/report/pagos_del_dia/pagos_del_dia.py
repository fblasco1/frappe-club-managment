# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.members.services.informe_pagos_del_dia import (
	get_pagos_del_dia_report_columns,
	get_pagos_del_dia_report_data,
	get_pagos_del_dia_report_summary,
)


def execute(
	filters: dict[str, Any] | None = None,
) -> tuple[
	list[dict[str, Any]],
	list[dict[str, Any]],
	None,
	None,
	list[dict[str, Any]],
]:
	return (
		get_pagos_del_dia_report_columns(),
		get_pagos_del_dia_report_data(filters),
		None,
		None,
		get_pagos_del_dia_report_summary(filters),
	)

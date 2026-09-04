"""Scheduler Frappe + PostgreSQL: normaliza datetimes en Scheduled Job Type.

PostgreSQL devuelve `last_execution` con tzinfo; `croniter.get_next` y
`now_datetime()` suelen ser naive → `TypeError` en `is_event_due` y el
scheduler deja de encolar jobs desde la primera ejecución.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def naive_datetime(value: datetime | Any) -> datetime:
	"""Quita tzinfo para comparar fechas de scheduler de forma segura."""
	if not isinstance(value, datetime):
		return value
	if value.tzinfo is not None:
		return value.replace(tzinfo=None)
	return value


def _patch_scheduled_job_type_is_event_due() -> None:
	from frappe.core.doctype.scheduled_job_type.scheduled_job_type import ScheduledJobType
	from frappe.utils import now_datetime

	if getattr(ScheduledJobType, "_club_scheduler_pg_patch", False):
		return

	def _is_event_due(self, current_time=None):  # noqa: ANN001
		next_exec = naive_datetime(self.get_next_execution())
		current = naive_datetime(current_time or now_datetime())
		return next_exec <= current

	ScheduledJobType.is_event_due = _is_event_due
	ScheduledJobType._club_scheduler_pg_patch = True


def _patch_enqueue_events_wrapper() -> None:
	from frappe.utils import scheduler

	if getattr(scheduler, "_club_enqueue_wrapper", False):
		return

	_orig: Callable[[], list[str]] = scheduler.enqueue_events

	def enqueue_events() -> list[str]:
		apply_patch()
		return _orig()

	scheduler.enqueue_events = enqueue_events
	scheduler._club_enqueue_wrapper = True


def apply_patch() -> None:
	"""Idempotente; aplica en sitios PostgreSQL."""
	try:
		import frappe
	except ImportError:
		return

	if not getattr(frappe, "db", None) or frappe.db.db_type != "postgres":
		return

	_patch_scheduled_job_type_is_event_due()


def _register_enqueue_wrapper() -> None:
	"""Registra el wrapper al importar (bench schedule no pasa por before_request)."""
	try:
		_patch_enqueue_events_wrapper()
	except Exception:
		pass


_register_enqueue_wrapper()

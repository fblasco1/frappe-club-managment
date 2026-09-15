"""Instala el Workflow Desk de Solicitud Asociacion (Sprint 1 Commit 3)."""

from __future__ import annotations

from club_management.members.workflow.solicitud_asociacion_workflow import (
	ensure_solicitud_asociacion_workflow,
)


def execute() -> None:
	ensure_solicitud_asociacion_workflow()

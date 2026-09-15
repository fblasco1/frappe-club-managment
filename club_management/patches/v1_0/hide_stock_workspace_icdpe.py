"""Oculta workspace Stock (widgets rotos en PostgreSQL + fuera de alcance ICDPE)."""

from __future__ import annotations

from club_management.setup.hide_stock_workspace import hide_stock_workspaces


def execute() -> None:
	hide_stock_workspaces()

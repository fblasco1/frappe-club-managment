"""Corrige labels en `content` del workspace Secretaría (cards no renderizaban)."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "Secretaría"

CONTENT = [
	{"id": "sec_hdr", "type": "header", "data": {"text": "Panel Secretaría", "col": 12}},
	{
		"id": "nc_pend",
		"type": "number_card",
		"data": {"number_card_name": "Solicitudes pendientes de revisión", "col": 3},
	},
	{
		"id": "nc_pago",
		"type": "number_card",
		"data": {"number_card_name": "Aprobados pendientes de 1er pago", "col": 3},
	},
	{
		"id": "nc_mor",
		"type": "number_card",
		"data": {"number_card_name": "Socios morosos", "col": 3},
	},
	{
		"id": "nc_act",
		"type": "number_card",
		"data": {"number_card_name": "Socios activos", "col": 3},
	},
]


def execute() -> None:
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return
	frappe.db.set_value(
		"Workspace",
		WORKSPACE_NAME,
		"content",
		json.dumps(CONTENT, ensure_ascii=False),
		update_modified=False,
	)
	frappe.clear_cache(doctype="Workspace")

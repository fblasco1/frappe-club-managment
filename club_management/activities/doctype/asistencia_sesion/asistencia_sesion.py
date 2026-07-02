"""Registro de asistencia por sesión de actividad."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class AsistenciaSesion(Document):
	def validate(self) -> None:
		inscriptos = cint(self.inscriptos)
		presentes = cint(self.presentes)
		if inscriptos < 0 or presentes < 0:
			frappe.throw(_("Los valores de inscriptos y presentes no pueden ser negativos."))
		if presentes > inscriptos:
			frappe.throw(_("Los presentes no pueden superar a los inscriptos esperados."))

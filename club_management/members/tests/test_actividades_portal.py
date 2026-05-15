"""Tests del listado de actividades para el formulario público."""

from __future__ import annotations

import frappe

from club_management.members.services.actividades_portal import list_actividades_asociacion
from club_management.members.test_helpers import MembersTestCase


class TestActividadesPortal(MembersTestCase):
	def test_devuelve_lista_no_vacia(self) -> None:
		actividades = list_actividades_asociacion()
		self.assertGreater(len(actividades), 0)
		self.assertIn("value", actividades[0])
		self.assertIn("label", actividades[0])

	def test_endpoint_guest_whitelist(self) -> None:
		from club_management.members.api.solicitud_publica import get_actividades_asociacion

		result = get_actividades_asociacion()
		self.assertIsInstance(result, list)
		self.assertTrue(result)

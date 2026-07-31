"""Tests configuración de cobranza periódica en Club Settings.

Spec: `club_management/specs/cobranza_config_club_settings.md`
"""

from __future__ import annotations

import frappe
from frappe.exceptions import ValidationError

from club_management.members.test_helpers import MembersTestCase


class TestCobranzaConfigClubSettings(MembersTestCase):
	def _settings(self):
		return frappe.get_single("Club Settings")

	def test_defaults_tras_migrate(self) -> None:
		settings = self._settings()
		settings.dia_generacion_deuda = None
		settings.dia_primer_vencimiento = None
		settings.dia_segundo_vencimiento = ""
		settings.recargo_segundo_vencimiento_pct = None
		settings.recargo_mes_vencido_pct = None
		settings.recargo_post_vencimiento_pct = None
		settings.incluir_aranceles_en_deuda_mensual = None
		settings.incluir_cargos_extra_en_deuda_mensual = None
		settings.save()
		settings.reload()
		self.assertEqual(settings.dia_generacion_deuda, 1)
		self.assertEqual(settings.dia_primer_vencimiento, 10)
		self.assertEqual(settings.dia_segundo_vencimiento, "Ultimo dia del mes")
		self.assertEqual(settings.recargo_segundo_vencimiento_pct, 10)
		self.assertEqual(settings.recargo_mes_vencido_pct, 5)
		self.assertEqual(settings.recargo_post_vencimiento_pct, 10)
		self.assertTrue(settings.incluir_aranceles_en_deuda_mensual)
		self.assertTrue(settings.incluir_cargos_extra_en_deuda_mensual)

	def test_primer_vencimiento_posterior_a_generacion(self) -> None:
		settings = self._settings()
		settings.dia_generacion_deuda = 15
		settings.dia_primer_vencimiento = 10
		with self.assertRaises(ValidationError):
			settings.save()

	def test_dia_invalido_falla(self) -> None:
		settings = self._settings()
		settings.dia_primer_vencimiento = 31
		with self.assertRaises(ValidationError):
			settings.save()

	def test_configuracion_valida_se_guarda(self) -> None:
		settings = self._settings()
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 15
		settings.dia_segundo_vencimiento = "20"
		settings.recargo_segundo_vencimiento_pct = 12.5
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.save()

		settings.reload()
		self.assertEqual(settings.dia_primer_vencimiento, 15)
		self.assertEqual(settings.dia_segundo_vencimiento, "20")
		self.assertEqual(settings.recargo_segundo_vencimiento_pct, 12.5)
		self.assertFalse(settings.incluir_aranceles_en_deuda_mensual)

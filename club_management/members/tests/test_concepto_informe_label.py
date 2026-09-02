"""Etiquetas de concepto informe desde líneas de Sales Invoice.

Spec: `club_management/specs/informe_rendicion_cobranza_secretaria.md` (fase 1)
"""

from __future__ import annotations

from club_management.members.services.concepto_informe_label import (
	agrupacion_tipo_concepto,
	etiqueta_concepto_informe_desde_linea_si,
)
from club_management.members.test_helpers import MembersTestCase


class TestConceptoInformeLabel(MembersTestCase):
	def test_cuota_social_activo_por_categoria(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CUOTA-SOCIAL",
			"Cuota social agosto 2026",
			categoria_socio="Activo",
		)
		self.assertEqual(label, "Cuota Social Activo")

	def test_cuota_social_menor_por_categoria(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CUOTA-SOCIAL",
			"Cuota Social Menor 08/2026",
			categoria_socio="Menor",
		)
		self.assertEqual(label, "Cuota Social Menor")

	def test_cuota_social_adherente_inferida_desde_descripcion(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CUOTA-SOCIAL",
			"Cuota Social Adherente (08/2026)",
		)
		self.assertEqual(label, "Cuota Social Adherente")

	def test_adicional_basquet_escuelita_desde_item(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-BASQUET-ESCUELITA",
			"Arancel básquet escuelita",
		)
		self.assertEqual(label, "Adicional Basquet Escuelita")

	def test_feder_voley_desde_item(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CUOTA-FEDERATIVA-voley",
			"Cuota federativa vóley",
		)
		self.assertEqual(label, "CUOTA FEDER VOLEY")

	def test_feder_basquet_masc_desde_descripcion(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CUOTA-FEDERATIVA-basquet-masculino",
			"C FED U15/U17 MASC 08/2026",
		)
		self.assertEqual(label, "C FED U15/U17 MASC")

	def test_cto_comp_desde_descripcion_sin_periodo(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CARGO-VARIOS",
			"CTO COMP BASQ TIRA A/B/FLEX (08/2026)",
		)
		self.assertEqual(label, "CTO COMP BASQ TIRA A/B/FLEX")

	def test_cto_comp_normaliza_basquet_en_descripcion(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-CARGO-VARIOS",
			"CTO COMP BASQUET TIRA A/B/FLEX (08/2026)",
		)
		self.assertEqual(label, "CTO COMP BASQ TIRA A/B/FLEX")

	def test_expediente_febamba_desde_item(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-MULTA",
			"Expediente FEBAMBA cuota 1",
		)
		self.assertEqual(label, "EXPEDIENTE FEBAMBA")

	def test_fallback_descripcion_limpia(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si(
			"ICDPE-OTRO-ITEM",
			"  Multa por atraso  ",
		)
		self.assertEqual(label, "Multa por atraso")

	def test_fallback_item_code_sin_descripcion(self) -> None:
		label = etiqueta_concepto_informe_desde_linea_si("ICDPE-DANZA", None)
		self.assertEqual(label, "ARANCEL DANZA")

	def test_agrupacion_tipo_cuota(self) -> None:
		self.assertEqual(agrupacion_tipo_concepto("Cuota Social Menor"), "Cuota")

	def test_agrupacion_tipo_cto_comp(self) -> None:
		self.assertEqual(agrupacion_tipo_concepto("CTO COMP VOLEY ESC"), "CTO COMP")

	def test_agrupacion_tipo_arancel(self) -> None:
		self.assertEqual(agrupacion_tipo_concepto("Adicional Basquet Escuelita"), "Arancel")

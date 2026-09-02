"""Tests mapeo concepto informe ↔ ítem.

Spec: `club_management/specs/informe_concepto_cobranza.md`
"""

from __future__ import annotations

from club_management.members.test_helpers import MembersTestCase
from club_management.scripts.informe_concepto_cobranza import (
	cuotas_complementarias_equivalentes,
	es_cuota_complementaria,
	normalizar_clave_cuota_complementaria,
	normalizar_concepto_informe,
	resolver_item_codes_concepto,
)


class TestInformeConceptoCobranzaHelpers(MembersTestCase):
	def test_normalizar_quita_acentos_y_colapsa(self) -> None:
		self.assertEqual(normalizar_concepto_informe("  Adicional Patin 1° Nivel  "), "ADICIONAL PATIN 1 NIVEL")
		self.assertEqual(normalizar_concepto_informe("C.FED U21 MASC"), "C.FED U21 MASC")

	def test_resolver_gimnasia_artistica_dos_clases(self) -> None:
		codes = resolver_item_codes_concepto("GIMNASIA ARTISTICA")
		self.assertEqual(codes, ("ICDPE-GIMNASIA-ARTISTICA-2-CLASES",))

	def test_resolver_boxeo_tres_veces(self) -> None:
		codes = resolver_item_codes_concepto("BOXEO 3 VECES")
		self.assertEqual(codes, ("ICDPE-BOXEO-3-CLASES",))

	def test_resolver_pre_mini_b_u9_minibasquet(self) -> None:
		codes = resolver_item_codes_concepto("PRE-MINI B U9")
		self.assertEqual(codes, ("ICDPE-BASQUET-MASCULINO-MINIBASQUET",))

	def test_resolver_premini_a_y_mini_a_minibasquet_no_escuelita(self) -> None:
		self.assertEqual(
			resolver_item_codes_concepto("PRE-MINI A U9"),
			("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
		)
		self.assertEqual(
			resolver_item_codes_concepto("MINI A U11"),
			("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
		)
		self.assertEqual(
			resolver_item_codes_concepto("INFA A U13"),
			("ICDPE-BASQUET-MASCULINO-MINIBASQUET",),
		)
		self.assertEqual(
			resolver_item_codes_concepto("CADETES A U15"),
			("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
		)
		self.assertEqual(
			resolver_item_codes_concepto("JUVENILES A U17"),
			("ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",),
		)
		self.assertNotIn("ICDPE-BASQUET-ESCUELITA", resolver_item_codes_concepto("PRE-MINI A U9"))

	def test_resolver_adicional_basquet(self) -> None:
		codes = resolver_item_codes_concepto("Adicional Basquet Escuelita")
		self.assertIn("ICDPE-BASQUET-ESCUELITA", codes)

	def test_resolver_feder_voley(self) -> None:
		codes = resolver_item_codes_concepto("CUOTA FEDER VOLEY")
		self.assertEqual(codes, ("ICDPE-CUOTA-FEDERATIVA-voley",))

	def test_resolver_feder_basquet_masc(self) -> None:
		codes = resolver_item_codes_concepto("C FED U15/U17 MASC")
		self.assertEqual(codes, ("ICDPE-CUOTA-FEDERATIVA-basquet-masculino",))

	def test_resolver_feder_basquet_fem(self) -> None:
		codes = resolver_item_codes_concepto("C.FED U13 FEM")
		self.assertEqual(codes, ("ICDPE-CUOTA-FEDERATIVA-basquet-femenino",))

	def test_resolver_cuota_social_menor(self) -> None:
		codes = resolver_item_codes_concepto("Cuota Social Menor")
		self.assertTrue(codes)

	def test_resolver_u17_flex(self) -> None:
		codes = resolver_item_codes_concepto("U17 FLEX")
		self.assertIn("ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX", codes)

	def test_resolver_funcional_gap(self) -> None:
		codes = resolver_item_codes_concepto("FUNCIONAL GAP")
		self.assertIn("ICDPE-FUNCIONAL-1-CLASE", codes)

	def test_resolver_adicional_voley_menor_federado(self) -> None:
		codes = resolver_item_codes_concepto("Adicional Voley Menor")
		self.assertEqual(codes, ("ICDPE-VOLEY-FEDERADO",))

	def test_cto_comp_no_resuelve_arancel(self) -> None:
		self.assertTrue(es_cuota_complementaria("CTO COMP VOLEY ESC"))
		self.assertEqual(resolver_item_codes_concepto("CTO COMP VOLEY ESC"), ())

	def test_cto_comp_equivalencia_descripcion(self) -> None:
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP BASQ TIRA A/B/FLEX",
				"CTO COMP BASQUET TIRA A/B/FLEX (08/2026)",
			)
		)
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP FUT ESC",
				"CTO COMP FUTBOL ESC (08/2026)",
			)
		)
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP FUTBOL FAFI/TABI",
				"CTO COMP FUTBOL TABI/FAFI (08/2026)",
			)
		)
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP BASQ TIRA A y B",
				"CTO COMP BASQ TIRA A/B/FLEX (08/2026)",
			)
		)
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP BASQ TIRA A/B/FLEX",
				"CTO COMP BASQUE TIRA A/B/FLEX (08/2026)",
			)
		)
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP BASQ ESC/FEM",
				"CTO COMP BASQ/FEM (08/2026)",
			)
		)
		self.assertFalse(
			cuotas_complementarias_equivalentes(
				"CTO COMP VOLEY",
				"CTO COMP VOLEY ESC (08/2026)",
			)
		)

	def test_normalizar_clave_cto_comp(self) -> None:
		self.assertEqual(
			normalizar_clave_cuota_complementaria("CTO COMP BASQ TIRA A y B"),
			"CTO COMP BASQ TIRA A/B/FLEX",
		)
		self.assertEqual(
			normalizar_clave_cuota_complementaria("CTO COMP BASQUE TIRA A/B/FLEX (08/2026)"),
			"CTO COMP BASQ TIRA A/B/FLEX",
		)

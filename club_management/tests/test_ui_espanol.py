"""Tests GF-7: UI siempre en español argentino (sin inglés visible)."""

from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

# Tests estáticos de i18n: solo leen archivos de la app (sin DB ni sitio).
# La raíz del paquete `club_management` es el padre de `tests/`.
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

# Términos en inglés que NO pueden aparecer como texto visible.
ENGLISH_BLOCKLIST = (
	"Purchase Invoice",
	"Sales Invoice",
	"Payment Entry",
	"Cost Center",
	"Account",
	"Invoice",
	"Payment",
)

# Traducciones mínimas requeridas para DocTypes financieros.
REQUIRED_TRANSLATIONS = {
	"Purchase Invoice": "Factura de compra",
	"Sales Invoice": "Factura de venta",
	"Payment Entry": "Pago / cobro",
	"Account": "Cuenta contable",
	"Cost Center": "Centro de costo",
}

# Nombres de módulo que deben mostrarse en español (GF-7b).
REQUIRED_MODULE_TRANSLATIONS = {
	"Finance": "Finanzas",
	"Members": "Socios",
	"Activities": "Actividades",
	"Club Management": "SICLUB",
}


def _read_es_csv() -> dict[str, str]:
	mapping: dict[str, str] = {}
	with _app_path("translations", "es.csv").open(encoding="utf-8") as fh:
		for row in csv.reader(fh):
			if len(row) >= 2 and row[0].strip():
				mapping[row[0].strip()] = row[1].strip()
	return mapping


def _app_path(*parts: str) -> Path:
	return PACKAGE_ROOT.joinpath(*parts)


class TestUiEspanol(unittest.TestCase):
	def test_workspace_tesoreria_labels_en_espanol(self) -> None:
		data = json.loads(
			_app_path("finance", "workspace", "tesoreria", "tesoreria.json").read_text(encoding="utf-8")
		)
		labels = [link.get("label", "") for link in data.get("links", [])]
		labels += [sc.get("label", "") for sc in data.get("shortcuts", [])]
		self.assertTrue(labels, "El workspace Tesorería no tiene labels")
		for label in labels:
			for termino in ENGLISH_BLOCKLIST:
				self.assertNotIn(
					termino,
					label,
					f"Label en inglés detectado en workspace Tesorería: {label!r}",
				)

	def test_workspace_tesoreria_conserva_link_to_tecnico(self) -> None:
		data = json.loads(
			_app_path("finance", "workspace", "tesoreria", "tesoreria.json").read_text(encoding="utf-8")
		)
		link_tos = {link.get("link_to") for link in data.get("links", [])}
		# Los identificadores técnicos deben permanecer (no visibles).
		self.assertIn("Purchase Invoice", link_tos)
		self.assertIn("Payment Entry", link_tos)

	def test_translations_es_csv_cubre_doctypes_financieros(self) -> None:
		self.assertTrue(_app_path("translations", "es.csv").exists(), "Falta translations/es.csv")
		mapping = _read_es_csv()
		for source, esperado in REQUIRED_TRANSLATIONS.items():
			self.assertEqual(
				mapping.get(source),
				esperado,
				f"Traducción faltante o incorrecta para {source!r}",
			)

	def test_translations_es_csv_cubre_modulos(self) -> None:
		mapping = _read_es_csv()
		for source, esperado in REQUIRED_MODULE_TRANSLATIONS.items():
			self.assertEqual(
				mapping.get(source),
				esperado,
				f"Traducción de módulo faltante o incorrecta para {source!r}",
			)

	def test_app_title_es_siclub(self) -> None:
		hooks = _app_path("hooks.py").read_text(encoding="utf-8")
		self.assertIn('app_title = "SICLUB"', hooks, "app_title debe ser 'SICLUB'")
		self.assertNotIn(
			'app_title = "Club Management"',
			hooks,
			"app_title en inglés ('Club Management')",
		)

	def test_panel_actividades_sin_ingles(self) -> None:
		js = _app_path("public", "js", "gestion_actividades_workspace_panel.js").read_text(encoding="utf-8")
		self.assertNotIn("Abrir en Desk", js, "Término en inglés 'Abrir en Desk'")
		self.assertNotIn("Crear ítem ERP", js, "Término en inglés 'Crear ítem ERP'")
		self.assertIn("Abrir ficha", js, "Falta 'Abrir ficha' en español")
		self.assertIn("Crear ítem de arancel", js, "Falta 'Crear ítem de arancel' en español")

	def test_banner_boton_factura_en_espanol(self) -> None:
		js = _app_path("public", "js", "secretaria_workspace_panel.js").read_text(encoding="utf-8")
		self.assertNotIn(
			"Nueva Purchase Invoice",
			js,
			"El botón del banner usa un término en inglés",
		)
		self.assertIn(
			"Nueva factura de compra",
			js,
			"Falta el botón 'Nueva factura de compra' en español",
		)

	def test_mensaje_recordatorio_sueldos_en_espanol(self) -> None:
		# GF-6: el mensaje visible del banner no debe decir "Purchase Invoice".
		src = _app_path("finance", "services", "recordatorio_sueldos.py").read_text(encoding="utf-8")
		self.assertNotIn(
			"cargá la Purchase Invoice",
			src,
			"El mensaje del recordatorio usa un término en inglés",
		)
		self.assertIn(
			"cargá la factura de compra",
			src,
			"Falta el copy en español 'cargá la factura de compra'",
		)

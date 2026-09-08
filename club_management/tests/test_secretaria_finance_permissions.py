"""Tests GF-6: permisos operativos de Finanzas para Secretaría (lógica pura)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from club_management.finance.setup.purchase_invoice_permissions import (
	PERMISOS as PI_PERMISOS,
)
from club_management.finance.setup.secretaria_finance_permissions import (
	DOCTYPES_EN_MODO_CUSTOM,
	OPERATIVE_PERMS,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class TestSecretariaFinancePerms(unittest.TestCase):
	def test_solo_toca_doctypes_en_modo_custom(self) -> None:
		# No agregar Custom DocPerm a DocTypes con permisos estándar (los borraría).
		for doctype in OPERATIVE_PERMS:
			self.assertIn(
				doctype,
				DOCTYPES_EN_MODO_CUSTOM,
				f"{doctype} no está en modo custom: agregar Custom DocPerm rompería sus permisos estándar",
			)

	def test_secretaria_pi_draft_only(self) -> None:
		# Secretaría crea/edita en Borrador, sin submit ni cancel.
		self.assertNotIn(
			"Purchase Invoice",
			OPERATIVE_PERMS,
			"Purchase Invoice se gestiona en purchase_invoice_permissions.py",
		)
		pi = PI_PERMISOS["Secretaria"]
		for flag in ("read", "create", "write"):
			self.assertEqual(pi.get(flag), 1, f"Falta permiso {flag} en Purchase Invoice")
		self.assertNotEqual(pi.get("submit"), 1, "Secretaría NO debe poder Presentar (submit)")
		self.assertNotEqual(pi.get("cancel"), 1, "Secretaría NO debe poder Cancelar")

	def test_tesoreria_pi_full(self) -> None:
		pi = PI_PERMISOS["Tesoreria"]
		for flag in ("read", "create", "write", "submit", "cancel"):
			self.assertEqual(pi.get(flag), 1, f"Tesorería debe tener {flag} en Purchase Invoice")

	def test_pago_operativo(self) -> None:
		pe = OPERATIVE_PERMS["Payment Entry"]
		for flag in ("read", "create", "write", "submit"):
			self.assertEqual(pe.get(flag), 1, f"Falta permiso {flag} en Payment Entry")

	def test_masters_lectura_y_item_creable(self) -> None:
		for master in ("Account", "Cost Center", "Company", "Mode of Payment"):
			perms = OPERATIVE_PERMS[master]
			self.assertEqual(perms.get("read"), 1, f"{master} debe ser legible")
			self.assertEqual(perms.get("select"), 1, f"{master} debe ser seleccionable en Links")
			self.assertNotEqual(perms.get("create"), 1, f"{master} no debe ser creable por Secretaría")
			self.assertNotEqual(perms.get("write"), 1, f"{master} no debe ser editable por Secretaría")

		item = OPERATIVE_PERMS["Item"]
		for flag in ("read", "select", "create", "write"):
			self.assertEqual(item.get(flag), 1, f"Item debe tener {flag} para Secretaría")
		self.assertNotEqual(item.get("delete"), 1, "Secretaría no debe poder borrar Items")

	def test_no_incluye_flujo_ni_reportes_pyl(self) -> None:
		# Secretaría no recibe permiso operativo sobre reportes/flujo (siguen por rol).
		self.assertNotIn("Proyeccion Flujo de Fondos", OPERATIVE_PERMS)
		self.assertNotIn("GL Entry", OPERATIVE_PERMS)

	def test_workspace_incluye_rol_secretaria(self) -> None:
		data = json.loads(
			(PACKAGE_ROOT / "finance" / "workspace" / "tesoreria" / "tesoreria.json").read_text(
				encoding="utf-8"
			)
		)
		roles = {r.get("role") for r in data.get("roles", [])}
		self.assertIn("Secretaria", roles)
		self.assertIn("Tesoreria", roles)


def _load_workspace(*parts: str) -> dict:
	path = PACKAGE_ROOT.joinpath(*parts)
	return json.loads(path.read_text(encoding="utf-8"))


class TestWorkspaceTesoreriaLayout(unittest.TestCase):
	"""GF-6 UX: workspace Tesorería con panel custom (botones + listas), sin render nativo."""

	def setUp(self) -> None:
		self.data = _load_workspace("finance", "workspace", "tesoreria", "tesoreria.json")
		self.content = json.loads(self.data.get("content") or "[]")
		self.js = (PACKAGE_ROOT / "public" / "js" / "tesoreria_workspace_panel.js").read_text(
			encoding="utf-8"
		)

	def test_workspace_sin_render_nativo(self) -> None:
		# El panel custom reemplaza el render nativo: content vacío, sin shortcuts/quick lists.
		self.assertEqual(self.content, [], "El content debe estar vacío (lo maneja el panel)")
		self.assertEqual(self.data.get("shortcuts", []), [])
		self.assertEqual(self.data.get("quick_lists", []), [])

	def test_panel_botones_operaciones(self) -> None:
		# El club dejó de usar Purchase Order: solo queda "Crear Factura de Compra".
		self.assertNotIn("Crear Orden de Compra", self.js)
		self.assertNotIn('frappe.new_doc("Purchase Order")', self.js)
		self.assertIn("Crear Factura de Compra", self.js)
		self.assertIn('frappe.new_doc("Purchase Invoice")', self.js)

	def test_panel_listas_operaciones(self) -> None:
		self.assertIn("borradores_pendientes", self.js)
		self.assertIn("facturas_pagas", self.js)
		self.assertIn("cobros_recibidos", self.js)
		# Las listas exponen plan de cuenta y centro de costo.
		self.assertIn("Plan de cuenta", self.js)
		self.assertIn("Centro de costo", self.js)

	def test_panel_titulos_listas(self) -> None:
		self.assertIn("PAGOS PENDIENTES", self.js)
		self.assertIn("PAGOS REALIZADOS", self.js)
		self.assertIn("COBRANZA", self.js)

	def test_panel_incluido_en_bundle(self) -> None:
		bundle = (PACKAGE_ROOT / "public" / "js" / "club_management.bundle.js").read_text(
			encoding="utf-8"
		)
		self.assertIn("tesoreria_workspace_panel.js", bundle)


class TestWorkspaceTesoreriaFullWidth(unittest.TestCase):
	"""GF-6 UX: el panel de Tesorería ocupa todo el ancho vía SCSS scopeado."""

	def test_scss_full_width(self) -> None:
		scss = (
			PACKAGE_ROOT / "public" / "scss" / "tesoreria_workspace_panel.scss"
		).read_text(encoding="utf-8")
		self.assertIn("club-tesoreria-workspace-body", scss)
		self.assertIn("max-width: none", scss)

	def test_scss_incluido_en_bundle(self) -> None:
		bundle = (
			PACKAGE_ROOT / "public" / "scss" / "club_management.bundle.scss"
		).read_text(encoding="utf-8")
		self.assertIn("tesoreria_workspace_panel", bundle)


class TestNavegacionTesoreria(unittest.TestCase):
	"""GF-6: la navegación del club reconoce Tesorería (para cargar el sidebar)."""

	def test_nav_reconoce_tesoreria(self) -> None:
		js = (PACKAGE_ROOT / "public" / "js" / "club_desk_navigation.js").read_text(
			encoding="utf-8"
		)
		self.assertIn('active === "Tesorería"', js, "is_club_workspace debe reconocer Tesorería")
		self.assertIn('workspace: "Tesorería"', js, "Debe existir la pestaña de Tesorería")

	def test_pestana_tesoreria_con_emoji_banco(self) -> None:
		js = (PACKAGE_ROOT / "public" / "js" / "club_desk_navigation.js").read_text(
			encoding="utf-8"
		)
		self.assertIn('emoji: "🏦"', js, "La pestaña Tesorería debe usar el emoji del banco")
		self.assertIn("club-desk-nav-emoji", js, "El nav debe renderizar el emoji de la pestaña")


class TestWorkspaceSecretariaAccesoTesoreria(unittest.TestCase):
	"""GF-6: el acceso a Tesorería es por la pestaña del sidebar (sin botón en Secretaría)."""

	def test_sin_boton_en_panel_secretaria(self) -> None:
		# El acceso pasa a ser sólo la pestaña del sidebar; se quitó el botón del panel.
		js = (PACKAGE_ROOT / "public" / "js" / "secretaria_workspace_panel.js").read_text(
			encoding="utf-8"
		)
		self.assertNotIn(
			"club-secretaria-tesoreria", js, "No debe quedar el botón de Tesorería en Secretaría"
		)


if __name__ == "__main__":
	unittest.main()

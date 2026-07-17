"""Patch GF-6: acceso operativo de Secretaría a Finanzas.

- Agrega permisos operativos (crear/leer Facturas de compra, Pagos, proveedores).
- Re-sincroniza el workspace Tesorería para que incluya el rol Secretaria.

El flujo de fondos y los reportes P&L siguen protegidos (rol Tesoreria en el
reporte y gate `ensure_tesoreria_access`), por lo que los links correspondientes
se ocultan para Secretaría al filtrarse por permiso.
"""

from __future__ import annotations

from club_management.finance.setup.secretaria_finance_permissions import (
	ensure_secretaria_finance_permissions,
)
from club_management.patches.v1_0.sync_tesoreria_workspace import execute as sync_workspace


def execute() -> None:
	ensure_secretaria_finance_permissions()
	sync_workspace()

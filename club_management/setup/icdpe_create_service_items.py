"""
ICDPE — creación idempotente de Items (servicios) con defaults contables por compañía.

Ejecución típica (desde el contenedor bench):

  1) Copiá este archivo dentro de tu app instalada en bench (recomendado), por ejemplo:
     `apps/club_management/club_management/setup/icdpe_create_service_items.py`

  2) Ejecutá:

     bench --site <tu_sitio> execute club_management.setup.icdpe_create_service_items.run

Notas ERPNext 16:
- Los defaults por compañía viven en la child table `Item Default` (`tabItem Default`):
  - `income_account`
  - `selling_cost_center`
- `default_income_account` / `default_cost_center` a nivel Item pueden existir en UI según versión,
  pero lo robusto es mantener `Item Default` consistente (lo hace este script).

Requisitos:
- Cuentas importadas (números según `Chart of Accounts Importer - ICDPE.csv`)
- Centros de costo importados (names = `Identificador` del CSV, ej: `Futbol - ICDPE`)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re
import unicodedata

import frappe

from club_management.setup.basquet_cost_center import BASQUET_COST_CENTER
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.activities.data.arancel_item_spec import format_arancel_mensual_item_name
from club_management.finance.setup.icdpe_income_item_groups import (
	LEAF_CARGOS,
	ensure_ingresos_item_group_tree,
	resolve_ingreso_leaf_for_item,
)

# Raíz estándar ERPNext para Item Group (si no existe, se crea bajo "All Item Groups")
DEFAULT_ITEM_GROUP_ROOT = "All Item Groups"

# Cuenta de ingreso para conceptos generales (multas / cargos varios a socios).
OTROS_CARGOS_ACCOUNT_NUMBER = "491003"
OTROS_CARGOS_ACCOUNT_LABEL = "Multas y cargos a socios"
OTROS_INGRESOS_PARENT_NUMBER = "4900"


@dataclass(frozen=True)
class ServiceItemSpec:
    item_code: str
    item_name: str
    item_group: str
    income_account_number: str
    cost_center_name: str  # ERPNext `tabCost Center.name` (en tu import: `Identificador`)


def _slugify_item_code_part(text: str) -> str:
    """
    Genera un sufijo seguro para `item_code` (ASCII, sin espacios raros).
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("&", "y")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text


def _ensure_uom(uom_name: str) -> None:
    if frappe.db.exists("UOM", uom_name):
        return
    frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)


def _ensure_item_group(name: str) -> None:
    if frappe.db.exists("Item Group", name):
        return

    if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
        frappe.throw(f"No existe el Item Group raíz '{DEFAULT_ITEM_GROUP_ROOT}'")

    doc = frappe.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": name,
            "parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
            "is_group": 0,
        }
    )
    doc.insert(ignore_permissions=True)


def _resolve_income_account(company: str, account_number: str) -> str:
    rows = frappe.get_all(
        "Account",
        filters={"company": company, "account_number": account_number, "is_group": 0},
        pluck="name",
        limit=2,
    )
    if not rows:
        frappe.throw(f"No encuentro cuenta de ingreso para company={company!r} y account_number={account_number!r}")
    if len(rows) > 1:
        frappe.throw(
            f"Hay más de una cuenta con account_number={account_number!r} en company={company!r}: {rows}"
        )
    return rows[0]


def _ensure_otros_cargos_account(company: str) -> str:
    """Cuenta de ingreso para multas/cargos varios (idempotente)."""
    existing = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": OTROS_CARGOS_ACCOUNT_NUMBER, "is_group": 0},
        "name",
    )
    if existing:
        return existing

    parent = frappe.db.get_value(
        "Account",
        {"company": company, "account_number": OTROS_INGRESOS_PARENT_NUMBER, "is_group": 1},
        "name",
    )
    if not parent:
        frappe.throw(
            f"No existe la cuenta padre «Otros ingresos» ({OTROS_INGRESOS_PARENT_NUMBER}) "
            f"para company={company!r}."
        )

    doc = frappe.get_doc(
        {
            "doctype": "Account",
            "account_name": OTROS_CARGOS_ACCOUNT_LABEL,
            "parent_account": parent,
            "company": company,
            "account_number": OTROS_CARGOS_ACCOUNT_NUMBER,
            "root_type": "Income",
            "account_type": "Income Account",
            "is_group": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _resolve_cost_center(company: str, cost_center_name: str) -> None:
    if not frappe.db.exists("Cost Center", cost_center_name):
        frappe.throw(
            "No existe el Cost Center "
            f"{cost_center_name!r} para company={company!r}. "
            "Verificá que el import haya creado el CC con ese `name` (Identificador)."
        )


def _upsert_item_default(item_name: str, company: str, income_account: str, selling_cc: str) -> None:
    item = frappe.get_doc("Item", item_name)

    row = None
    for d in item.get("item_defaults") or []:
        if d.company == company:
            row = d
            break

    if row is None:
        item.append(
            "item_defaults",
            {
                "company": company,
                "income_account": income_account,
                "selling_cost_center": selling_cc,
            },
        )
    else:
        row.income_account = income_account
        row.selling_cost_center = selling_cc

    item.save(ignore_permissions=True)


def upsert_service_item(spec: ServiceItemSpec) -> str:
    ensure_ingresos_item_group_tree()
    leaf = resolve_ingreso_leaf_for_item(spec.item_code)
    company = resolve_icdpe_company()
    _resolve_cost_center(company, spec.cost_center_name)
    income_account = _resolve_income_account(company, spec.income_account_number)

    if frappe.db.exists("Item", spec.item_code):
        item = frappe.get_doc("Item", spec.item_code)
        changed = False

        if item.item_name != spec.item_name:
            item.item_name = spec.item_name
            changed = True
        if item.item_group != leaf:
            item.item_group = leaf
            changed = True
        if int(item.is_stock_item or 0) != 0:
            item.is_stock_item = 0
            changed = True
        if item.stock_uom != "Servicio":
            item.stock_uom = "Servicio"
            changed = True
        if int(item.is_sales_item or 0) != 1:
            item.is_sales_item = 1
            changed = True

        if changed:
            item.save(ignore_permissions=True)

        _upsert_item_default(spec.item_code, company, income_account, spec.cost_center_name)
        return "updated"

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": spec.item_code,
            "item_name": spec.item_name,
            "item_group": leaf,
            "is_stock_item": 0,
            "is_sales_item": 1,
            "stock_uom": "Servicio",
            "include_item_in_manufacturing": 0,
            "item_defaults": [
                {
                    "company": company,
                    "income_account": income_account,
                    "selling_cost_center": spec.cost_center_name,
                }
            ],
        }
    )
    item.insert(ignore_permissions=True)
    _upsert_item_default(spec.item_code, company, income_account, spec.cost_center_name)
    return "created"


def _specs() -> list[ServiceItemSpec]:
    # item_group en specs es informativo; upsert resuelve la hoja por item_code.
    def _sg(code: str, name: str, account: str, cc: str) -> ServiceItemSpec:
        return ServiceItemSpec(
            item_code=code,
            item_name=name,
            item_group=resolve_ingreso_leaf_for_item(code),
            income_account_number=account,
            cost_center_name=cc,
        )

    # --- Institucional ---
    institutional: list[ServiceItemSpec] = [
        _sg("ICDPE-CUOTA-SOCIAL", "Cuota social", "411001", "Administración - ICDPE"),
        _sg("ICDPE-INSCRIPCION", "Inscripción / matrícula", "411002", "Administración - ICDPE"),
    ]

    # --- Deportes (aranceles mensuales + federativo; sin packs) ---
    # (cc, slug_label, segmentos nombre arancel)
    sports_cc: list[tuple[str, str, tuple[str, ...]]] = [
        ("Futbol - ICDPE", "Futbol", ("FUTBOL",)),
        (BASQUET_COST_CENTER, "Basquet Masculino", ("BASQUET", "MASCULINO")),
        (BASQUET_COST_CENTER, "Basquet Escuelita", ("BASQUET", "MIXTO", "ESCUELITA")),
        (BASQUET_COST_CENTER, "Basquet Femenino", ("BASQUET", "FEMENINO")),
        ("Voley - ICDPE", "Voley", ("VOLEY", "FEMENINO")),
        ("Patin - ICDPE", "Patin", ("PATIN ARTISTICO",)),
        ("Boxeo - ICDPE", "Boxeo", ("BOXEO",)),
        ("Gimnasia Artistica - ICDPE", "Gimnasia Artistica", ("GIMNASIA ARTISTICA",)),
        ("Taekwondo - ICDPE", "Taekwondo", ("TAEKWONDO",)),
        ("Shui Lu - ICDPE", "Shui Lu", ("SHUI LU",)),
    ]

    sports_items: list[ServiceItemSpec] = []
    for cc, label, name_segments in sports_cc:
        slug = _slugify_item_code_part(label)
        sports_items += [
            _sg(
                f"ICDPE-ARANCEL-MENSUAL-{slug}",
                format_arancel_mensual_item_name(*name_segments),
                "412001",
                cc,
            ),
            _sg(
                f"ICDPE-CUOTA-FEDERATIVA-{slug}",
                f"Cuota federativa — {label}",
                "413001",
                cc,
            ),
        ]

    # --- Actividades (aranceles mensuales) ---
    act_cc = [
        ("Iniciacion Deportiva - ICDPE", ("INICIACION DEPORTIVA",)),
        ("Danza - ICDPE", ("DANZA",)),
        ("Yoga - ICDPE", ("YOGA",)),
        ("CrossFit - ICDPE", ("CROSSFIT",)),
        ("Funcional - ICDPE", ("FUNCIONAL",)),
        ("Ritmos Latinos - ICDPE", ("RITMOS LATINOS",)),
        ("Zumba - ICDPE", ("ZUMBA",)),
    ]
    act_items: list[ServiceItemSpec] = []
    for cc, name_segments in act_cc:
        label = cc.replace(" - ICDPE", "")
        slug = _slugify_item_code_part(label)
        act_items += [
            _sg(
                f"ICDPE-ARANCEL-MENSUAL-ACT-{slug}",
                format_arancel_mensual_item_name(*name_segments),
                "412001",
                cc,
            ),
        ]

    # --- Fitness ---
    fitness_items = [
        _sg(
            "ICDPE-ARANCEL-MENSUAL-FITNESS-MUSC",
            format_arancel_mensual_item_name("GIMNASIO FITNESS"),
            "412001",
            "Gimnasio de Musculacion - ICDPE",
        ),
    ]

    # --- Gastronomía (POS) ---
    gastro_items = [
        _sg("ICDPE-POS-BUFFET", "Venta mostrador (POS) — Buffet", "441001", "Buffet - ICDPE"),
        _sg(
            "ICDPE-POS-PENA-ROCK",
            "Venta mostrador (POS) — Peña de Rock",
            "441001",
            "Peña de Rock - ICDPE",
        ),
        _sg(
            "ICDPE-POS-RESTAURANTE",
            "Venta mostrador (POS) — Restaurante",
            "441001",
            "Restaurante - ICDPE",
        ),
    ]

    # --- Alquileres ---
    rental_items = [
        _sg(
            "ICDPE-ALQ-ARS-TEMP",
            "Alquiler canchas / espacios (ARS) — Temporal",
            "421001",
            "Temporal - ICDPE",
        ),
        _sg(
            "ICDPE-ALQ-ARS-REC",
            "Alquiler canchas / espacios (ARS) — Recurrente",
            "421001",
            "Recurrente - ICDPE",
        ),
        _sg(
            "ICDPE-ALQ-USD-TEMP",
            "Alquiler canchas / espacios (USD) — Temporal",
            "421002",
            "Temporal - ICDPE",
        ),
        _sg(
            "ICDPE-ALQ-USD-REC",
            "Alquiler canchas / espacios (USD) — Recurrente",
            "421002",
            "Recurrente - ICDPE",
        ),
    ]

    # --- Comercial / otros ---
    other_items = [
        _sg("ICDPE-VENTA-INDUMENTARIA", "Venta indumentaria", "451002", "Administración - ICDPE"),
        _sg(
            "ICDPE-COLONIAS",
            "Colonias",
            "431002",
            "Iniciacion Deportiva - ICDPE",
        ),
        _sg("ICDPE-EVENTOS", "Eventos", "431003", "Danza - ICDPE"),
    ]

    # --- Conceptos generales para cargos extra (sin actividad) ---
    cargos_varios_items = [
        _sg("ICDPE-MULTA", "Multa", OTROS_CARGOS_ACCOUNT_NUMBER, "Administración - ICDPE"),
        _sg("ICDPE-CARGO-VARIOS", "Cargo varios", OTROS_CARGOS_ACCOUNT_NUMBER, "Administración - ICDPE"),
    ]

    return (
        institutional
        + sports_items
        + act_items
        + fitness_items
        + gastro_items
        + rental_items
        + other_items
        + cargos_varios_items
    )


def run() -> dict[str, object]:
    _ensure_uom("Servicio")
    ensure_ingresos_item_group_tree()

    company = resolve_icdpe_company()
    _ensure_otros_cargos_account(company)
    results: list[dict[str, str]] = []
    for spec in _specs():
        action = upsert_service_item(spec)
        income_account = _resolve_income_account(company, spec.income_account_number)
        results.append(
            {
                "item_code": spec.item_code,
                "action": action,
                "item_group": resolve_ingreso_leaf_for_item(spec.item_code),
                "income_account_number": spec.income_account_number,
                "income_account": income_account,
                "selling_cost_center": spec.cost_center_name,
            }
        )

    return {"company": company, "count": len(results), "items": results}


def ensure_cargos_varios_items() -> dict[str, object]:
    """Crea (idempotente) solo la cuenta y los ítems generales para cargos extra.

    No depende del resto del catálogo deportivo, por lo que es seguro de correr
    como patch aunque falten centros de costo de otras áreas.
    """
    _ensure_uom("Servicio")
    ensure_ingresos_item_group_tree()
    company = resolve_icdpe_company()
    _ensure_otros_cargos_account(company)

    results: list[dict[str, str]] = []
    for spec in _specs():
        if resolve_ingreso_leaf_for_item(spec.item_code) != LEAF_CARGOS:
            continue
        if spec.item_code not in ("ICDPE-MULTA", "ICDPE-CARGO-VARIOS"):
            continue
        results.append({"item_code": spec.item_code, "action": upsert_service_item(spec)})
    return {"company": company, "items": results}


def print_summary(items: Iterable[dict[str, str]]) -> None:
    # Salida pensada para copiar/pegar en una planilla
    print("item_code\taction\titem_group\tincome_account_number\tincome_account\tselling_cost_center")
    for row in items:
        print(
            "\t".join(
                [
                    row["item_code"],
                    row["action"],
                    row["item_group"],
                    row["income_account_number"],
                    row["income_account"],
                    row["selling_cost_center"],
                ]
            )
        )


if __name__ == "__main__":
    # `bench execute` invoca `run` automáticamente si existe; este bloque queda por si lo corrés como script.
    out = run()
    print_summary(out["items"])  # type: ignore[index]

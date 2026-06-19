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
- Centros de costo importados (names = `Identificador` del CSV, ej: `Deportes - Futbol - ICDPE`)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re
import unicodedata

import frappe


COMPANY = "Institución Cultural y Deportiva Pedro Echagüe"

# Raíz estándar ERPNext para Item Group (si no existe, se crea bajo "All Item Groups")
DEFAULT_ITEM_GROUP_ROOT = "All Item Groups"


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
    _ensure_item_group(spec.item_group)
    _resolve_cost_center(COMPANY, spec.cost_center_name)
    income_account = _resolve_income_account(COMPANY, spec.income_account_number)

    if frappe.db.exists("Item", spec.item_code):
        item = frappe.get_doc("Item", spec.item_code)
        changed = False

        if item.item_name != spec.item_name:
            item.item_name = spec.item_name
            changed = True
        if item.item_group != spec.item_group:
            item.item_group = spec.item_group
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

        _upsert_item_default(spec.item_code, COMPANY, income_account, spec.cost_center_name)
        return "updated"

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": spec.item_code,
            "item_name": spec.item_name,
            "item_group": spec.item_group,
            "is_stock_item": 0,
            "is_sales_item": 1,
            "stock_uom": "Servicio",
            "include_item_in_manufacturing": 0,
            "item_defaults": [
                {
                    "company": COMPANY,
                    "income_account": income_account,
                    "selling_cost_center": spec.cost_center_name,
                }
            ],
        }
    )
    item.insert(ignore_permissions=True)
    _upsert_item_default(spec.item_code, COMPANY, income_account, spec.cost_center_name)
    return "created"


def _specs() -> list[ServiceItemSpec]:
    # --- Institucional ---
    institutional: list[ServiceItemSpec] = [
        ServiceItemSpec(
            item_code="ICDPE-CUOTA-SOCIAL",
            item_name="Cuota social",
            item_group="ICDPE / Cuotas y membresías",
            income_account_number="411001",
            cost_center_name="Administración - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-INSCRIPCION",
            item_name="Inscripción / matrícula",
            item_group="ICDPE / Cuotas y membresías",
            income_account_number="411002",
            cost_center_name="Administración - ICDPE",
        ),
    ]

    # --- Deportes (aranceles / packs / federativo) ---
    sports_cc = [
        "Deportes - Futbol - ICDPE",
        "Deportes - Basquet Masculino - ICDPE",
        "Deportes - Basquet Femenino - ICDPE",
        "Deportes - Voley - ICDPE",
        "Deportes - Patin - ICDPE",
        "Deportes - Boxeo - ICDPE",
        "Deportes - Gimnasia Artistica - ICDPE",
        "Deportes - Taekwondo - ICDPE",
        "Deportes - Shui Lu - ICDPE",
    ]

    sports_items: list[ServiceItemSpec] = []
    for cc in sports_cc:
        label = cc.replace("Deportes - ", "").replace(" - ICDPE", "")
        slug = _slugify_item_code_part(label)
        sports_items += [
            ServiceItemSpec(
                item_code=f"ICDPE-ARANCEL-MENSUAL-{slug}",
                item_name=f"Arancel mensual actividad — {label}",
                item_group="ICDPE / Aranceles deportes",
                income_account_number="412001",
                cost_center_name=cc,
            ),
            ServiceItemSpec(
                item_code=f"ICDPE-PACKS-CLASES-{slug}",
                item_name=f"Packs CLASES — {label}",
                item_group="ICDPE / Packs deportes",
                income_account_number="412002",
                cost_center_name=cc,
            ),
            ServiceItemSpec(
                item_code=f"ICDPE-CUOTA-FEDERATIVA-{slug}",
                item_name=f"Cuota federativa — {label}",
                item_group="ICDPE / Federaciones deportes",
                income_account_number="413001",
                cost_center_name=cc,
            ),
        ]

    # --- Actividades (aranceles / packs; federativo normalmente no aplica) ---
    act_cc = [
        "Actividades - Iniciacion Deportiva - ICDPE",
        "Actividades - Danza - ICDPE",
        "Actividades - Yoga - ICDPE",
        "Actividades - CrossFit - ICDPE",
        "Actividades - Funcional - ICDPE",
        "Actividades - Ritmos Latinos - ICDPE",
        "Actividades - Zumba - ICDPE",
    ]
    act_items: list[ServiceItemSpec] = []
    for cc in act_cc:
        label = cc.replace("Actividades - ", "").replace(" - ICDPE", "")
        slug = _slugify_item_code_part(label)
        act_items += [
            ServiceItemSpec(
                item_code=f"ICDPE-ARANCEL-MENSUAL-ACT-{slug}",
                item_name=f"Arancel mensual actividad — {label}",
                item_group="ICDPE / Aranceles actividades",
                income_account_number="412001",
                cost_center_name=cc,
            ),
            ServiceItemSpec(
                item_code=f"ICDPE-PACKS-CLASES-ACT-{slug}",
                item_name=f"Packs CLASES — {label}",
                item_group="ICDPE / Packs actividades",
                income_account_number="412002",
                cost_center_name=cc,
            ),
        ]

    # --- Fitness ---
    fitness_items = [
        ServiceItemSpec(
            item_code="ICDPE-ARANCEL-MENSUAL-FITNESS-MUSC",
            item_name="Arancel mensual actividad — Gimnasio de musculación",
            item_group="ICDPE / Aranceles fitness",
            income_account_number="412001",
            cost_center_name="Fitness - Gimnasio de Musculacion - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-PACKS-CLASES-FITNESS-MUSC",
            item_name="Packs CLASES — Gimnasio de musculación",
            item_group="ICDPE / Packs fitness",
            income_account_number="412002",
            cost_center_name="Fitness - Gimnasio de Musculacion - ICDPE",
        ),
    ]

    # --- Gastronomía (POS) ---
    gastro_items = [
        ServiceItemSpec(
            item_code="ICDPE-POS-BUFFET",
            item_name="Venta mostrador (POS) — Buffet",
            item_group="ICDPE / Gastronomía POS",
            income_account_number="441001",
            cost_center_name="Gastronomía - Buffet - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-POS-PENA-ROCK",
            item_name="Venta mostrador (POS) — Peña de Rock",
            item_group="ICDPE / Gastronomía POS",
            income_account_number="441001",
            cost_center_name="Gastronomía - Peña de Rock - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-POS-RESTAURANTE",
            item_name="Venta mostrador (POS) — Restaurante",
            item_group="ICDPE / Gastronomía POS",
            income_account_number="441001",
            cost_center_name="Gastronomía - Restaurante - ICDPE",
        ),
    ]

    # --- Alquileres ---
    rental_items = [
        ServiceItemSpec(
            item_code="ICDPE-ALQ-ARS-TEMP",
            item_name="Alquiler canchas / espacios (ARS) — Temporal",
            item_group="ICDPE / Alquileres",
            income_account_number="421001",
            cost_center_name="Alquileres - Temporal - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-ALQ-ARS-REC",
            item_name="Alquiler canchas / espacios (ARS) — Recurrente",
            item_group="ICDPE / Alquileres",
            income_account_number="421001",
            cost_center_name="Alquileres - Recurrente - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-ALQ-USD-TEMP",
            item_name="Alquiler canchas / espacios (USD) — Temporal",
            item_group="ICDPE / Alquileres",
            income_account_number="421002",
            cost_center_name="Alquileres - Temporal - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-ALQ-USD-REC",
            item_name="Alquiler canchas / espacios (USD) — Recurrente",
            item_group="ICDPE / Alquileres",
            income_account_number="421002",
            cost_center_name="Alquileres - Recurrente - ICDPE",
        ),
    ]

    # --- Comercial / otros ---
    other_items = [
        ServiceItemSpec(
            item_code="ICDPE-SPONSOR-PUB",
            item_name="Sponsors / Publicidad",
            item_group="ICDPE / Comercial",
            income_account_number="451001",
            cost_center_name="Administración - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-VENTA-INDUMENTARIA",
            item_name="Venta indumentaria",
            item_group="ICDPE / Comercial",
            income_account_number="451002",
            cost_center_name="Administración - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-COLONIAS",
            item_name="Colonias",
            item_group="ICDPE / Actividades puntuales",
            income_account_number="431002",
            cost_center_name="Actividades - Iniciacion Deportiva - ICDPE",
        ),
        ServiceItemSpec(
            item_code="ICDPE-EVENTOS",
            item_name="Eventos",
            item_group="ICDPE / Actividades puntuales",
            income_account_number="431003",
            cost_center_name="Actividades - Danza - ICDPE",
        ),
    ]

    return institutional + sports_items + act_items + fitness_items + gastro_items + rental_items + other_items


def run() -> dict[str, object]:
    _ensure_uom("Servicio")

    results: list[dict[str, str]] = []
    for spec in _specs():
        action = upsert_service_item(spec)
        income_account = _resolve_income_account(COMPANY, spec.income_account_number)
        results.append(
            {
                "item_code": spec.item_code,
                "action": action,
                "item_group": spec.item_group,
                "income_account_number": spec.income_account_number,
                "income_account": income_account,
                "selling_cost_center": spec.cost_center_name,
            }
        )

    return {"company": COMPANY, "count": len(results), "items": results}


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

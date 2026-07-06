# Spec: Cost Center único básquet ICDPE (BL-4)

Consolida los tres centros de costo ERPNext de básquet legacy en uno solo,
alineado con la actividad única **Basquet** (`basquet_estructura_unificada.md`).

**Relacionado:** `basquet_aranceles_icdpe.md`, `icdpe_create_service_items.py`

**Estado:** implementado (BL-4).

---

## Modelo objetivo

| Antes (legacy) | Después |
|----------------|---------|
| `Deportes - Basquet Masculino - ICDPE` | `Deportes - Basquet - ICDPE` |
| `Deportes - Basquet Escuelita - ICDPE` | *(mismo)* |
| `Deportes - Basquet Femenino - ICDPE` | *(mismo)* |

Los **ítems** de arancel (`ICDPE-BASQUET-*`, `ICDPE-ARANCEL-MENSUAL-basquet-*`,
`ICDPE-CUOTA-FEDERATIVA-basquet-*`) conservan su `item_code`; solo cambia el
`selling_cost_center` en `Item Default`.

---

## Scenario: CC unificado existe bajo Deportes

Given la Company ICDPE y el CC padre `Deportes - ICDPE`
When corre `ensure_basquet_unified_cost_center`
Then existe `Deportes - Basquet - ICDPE` con `parent_cost_center = Deportes - ICDPE`
And `is_group = 0`.

---

## Scenario: ítems básquet apuntan al CC unificado

Given ítems con `Item Default.selling_cost_center` en uno de los tres CC legacy
When corre `consolidate_basquet_cost_centers`
Then cada fila `Item Default` ICDPE de esos ítems usa `Deportes - Basquet - ICDPE`
And `BASQUET_ITEM_SPECS` en código referencia solo el CC unificado.

---

## Scenario: CC legacy deshabilitados

Given la consolidación aplicada sin transacciones GL abiertas en los CC legacy
When se deshabilitan los tres CC antiguos
Then `disabled = 1` en cada CC legacy de básquet
And el CC unificado permanece habilitado.

---

## Scenario: seed aranceles básquet idempotente

Given patch `sync_basquet_aranceles_icdpe`
When crea o actualiza ítems `ICDPE-BASQUET-*`
Then todos usan `Deportes - Basquet - ICDPE` como centro de costo de venta.

---

## Scenario: verificación pre-purga básquet legacy

Given migración de inscripciones y consolidación de CC aplicadas
When corre `verify_basquet_legacy_cleanup`
Then no hay `Inscripcion Actividad` (activas ni dadas de baja) en actividades legacy
And no hay `Sales Invoice` con saldo pendiente vinculada a ítems/CC legacy de básquet
And no hay `Item Default` con `selling_cost_center` en los tres CC legacy
And los CC legacy están deshabilitados y las actividades legacy deshabilitadas
And existe el CC unificado `Deportes - Basquet - ICDPE`.

---

## Scenario: purga tras verificación OK

Given `verify_basquet_legacy_cleanup` devuelve `ok = true`
When se ejecuta `purge_basquet_legacy_disabled` con `confirm = PURGE_BASQUET_LEGACY`
Then se eliminan actividades, grupos, equipos y CC legacy **deshabilitados**
And no se tocan inscripciones ni facturas (ya verificadas en cero).

Ejecución:

```bash
# Solo verificar
bench --site <sitio> execute \\
  club_management.activities.setup.verify_and_purge_basquet_legacy.run \\
  --kwargs '{"dry_run": true}'

# Verificar + purga
bench --site <sitio> execute \\
  club_management.activities.setup.verify_and_purge_basquet_legacy.run \\
  --kwargs '{"dry_run": false, "purge": true, "confirm": "PURGE_BASQUET_LEGACY"}'
```

# Spec: Aplanar y renombrar Cost Centers ICDPE

El árbol de Cost Centers de la Company ICDPE elimina el nodo intermedio
`Main - ICDPE` y acorta los nombres de las hojas quitando el prefijo de área
(p. ej. `Deportes - Futbol - ICDPE` → `Futbol - ICDPE`).

**Decisión:** el sufijo ` - ICDPE` (abreviación de Company) lo impone ERPNext
y **no se elimina**.

**Relacionado:** `basquet_cost_center_consolidado.md`, `centro_costo_arancel_actividad.md`,
`items_finance_cost_center.md`

---

## Árbol objetivo

```
…Pedro Echagüe - ICDPE
  Administración - ICDPE
  Cuotas Sociales - ICDPE
  Deportes - ICDPE (grupo)
    Futbol / Basquet / Voley / Patin / Boxeo / Gimnasia Artistica / Taekwondo / Shui Lu
  Actividades - ICDPE (grupo)
    Iniciacion Deportiva / Danza / Yoga / CrossFit / Funcional / Ritmos Latinos / Zumba
  Fitness - ICDPE (grupo)
    Gimnasio de Musculacion
  Gastronomía - ICDPE (grupo)
    Buffet / Peña de Rock / Restaurante
  Alquileres - ICDPE (grupo)
    Temporal / Recurrente
```

---

## Scenario: Main deja de ser padre

Given Cost Centers ICDPE con hijos bajo `Main - ICDPE`
When corre la migración `flatten_rename_icdpe_cost_centers`
Then Administración, Deportes, Actividades, Fitness, Gastronomía, Alquileres y
Cuotas Sociales tienen `parent_cost_center` = raíz de la Company
And `Main - ICDPE` no tiene hijos activos (disabled o eliminado)

---

## Scenario: hojas con nombre corto

Given hojas con prefijo de área (`Deportes - Futbol - ICDPE`, …)
When corre la migración
Then cada hoja activa del mapa se renombra al `name` corto (`Futbol - ICDPE`, …)
And `cost_center_name` queda sin el prefijo de área (`Futbol`, …)
And los grupos de área conservan su `name` (`Deportes - ICDPE`, …)

---

## Scenario: referencias de Item Default

Given un `Item Default.selling_cost_center` apuntando a un CC con nombre largo
When corre el rename
Then el `Item Default` apunta al nuevo `name` corto

---

## Scenario: CrossFit y Funcional bajo Fitness

Given `CrossFit - ICDPE` y `Funcional - ICDPE` (tras el rename corto)
When corre la migración (o el refine)
Then ambos tienen `parent_cost_center = Fitness - ICDPE`
And ya no cuelgan de `Actividades - ICDPE`

---

## Scenario: Administración y Cuotas Sociales arriba

Given la raíz contable `…Pedro Echagüe - ICDPE`
When corre el reorden de hojas institucionales
Then los dos primeros hijos (por `lft`) son `Administración - ICDPE` y
`Cuotas Sociales - ICDPE`

### Qué representan

| Centro | Uso |
|--------|-----|
| **Administración** | Gastos/ingresos de estructura del club (defaults de Company, round-off, cargos varios, sponsors, etc.). |
| **Cuotas Sociales** | Ingreso de la cuota social del socio, separado de Administración para el estado de resultados. |

---

## Nota UI: doble carpeta con el nombre del club

En Desk a veces se ve:

1. `Institución Cultural y Deportiva Pedro Echagüe` (rótulo de Company / raíz del treeview)
2. `Institución Cultural y Deportiva Pedro Echagüe - ICDPE` (Cost Center contable raíz que crea ERPNext)

Es **correcto** en ERPNext: el sufijo `- ICDPE` es la abreviación de la Company en el `name` del documento. No se elimina sin hackear core.

---

## Scenario: idempotente

Given la migración ya aplicada
When se vuelve a ejecutar
Then no falla y el árbol permanece estable

---

## Mapa rename (activo)

| old | new |
|-----|-----|
| `Deportes - Futbol - ICDPE` | `Futbol - ICDPE` |
| `Deportes - Basquet - ICDPE` | `Basquet - ICDPE` |
| `Deportes - Voley - ICDPE` | `Voley - ICDPE` |
| `Deportes - Patin - ICDPE` | `Patin - ICDPE` |
| `Deportes - Boxeo - ICDPE` | `Boxeo - ICDPE` |
| `Deportes - Gimnasia Artistica - ICDPE` | `Gimnasia Artistica - ICDPE` |
| `Deportes - Taekwondo - ICDPE` | `Taekwondo - ICDPE` |
| `Deportes - Shui Lu - ICDPE` | `Shui Lu - ICDPE` |
| `Actividades - Iniciacion Deportiva - ICDPE` | `Iniciacion Deportiva - ICDPE` |
| `Actividades - Danza - ICDPE` | `Danza - ICDPE` |
| `Actividades - Yoga - ICDPE` | `Yoga - ICDPE` |
| `Actividades - CrossFit - ICDPE` | `CrossFit - ICDPE` |
| `Actividades - Funcional - ICDPE` | `Funcional - ICDPE` |
| `Actividades - Ritmos Latinos - ICDPE` | `Ritmos Latinos - ICDPE` |
| `Actividades - Zumba - ICDPE` | `Zumba - ICDPE` |
| `Fitness - Gimnasio de Musculacion - ICDPE` | `Gimnasio de Musculacion - ICDPE` |
| `Gastronomía - Buffet - ICDPE` | `Buffet - ICDPE` |
| `Gastronomía - Peña de Rock - ICDPE` | `Peña de Rock - ICDPE` |
| `Gastronomía - Restaurante - ICDPE` | `Restaurante - ICDPE` |
| `Alquileres - Temporal - ICDPE` | `Temporal - ICDPE` |
| `Alquileres - Recurrente - ICDPE` | `Recurrente - ICDPE` |

Legacy básquet disabled (`…Basquet Masculino/Escuelita/Femenino…`) no se reactivan.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Migración | `setup/flatten_rename_icdpe_cost_centers.py` |
| Patch | `patches/v1_0/flatten_rename_icdpe_cost_centers.py` |
| Tests | `tests/test_cost_centers_aplanar_renombrar.py` |

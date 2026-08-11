# Matriz: Item → Item Group hoja (ingresos)

Fuente: specs de aranceles + `icdpe_create_service_items` / FIN seed.
Migración: `icdpe_income_item_groups.ITEM_TO_LEAF` + reglas por prefijo.

## Socios

| Item | Hoja |
|------|------|
| `ICDPE-CUOTA-SOCIAL` | Cuotas sociales |
| `ICDPE-INSCRIPCION` | Cuotas sociales |
| `ICDPE-MULTA` | Cargos extras y mora |
| `ICDPE-CARGO-VARIOS` | Cargos extras y mora |
| `RECARGO-MORA` | Cargos extras y mora |

## Deportes

| Prefijo / códigos | Hoja |
|-------------------|------|
| `ICDPE-BASQUET-*`, `ICDPE-ARANCEL-MENSUAL-basquet*` | Básquet |
| `ICDPE-FUTBOL-*`, `ICDPE-ARANCEL-MENSUAL-futbol*` | Fútbol |
| `ICDPE-VOLEY-*`, `ICDPE-ARANCEL-MENSUAL-voley*` | Vóley |
| `ICDPE-PATIN-*`, `ICDPE-ARANCEL-MENSUAL-patin*`, `…PATIN-*` | Patín |
| `ICDPE-BOXEO-*`, `ICDPE-ARANCEL-MENSUAL-boxeo*` | Boxeo |
| `ICDPE-TAEKWONDO*`, `…taekwondo*` | Taekwondo |
| `ICDPE-SHUI-LU*`, `…shui*` | Shui Lu |
| `ICDPE-GIMNASIA-ARTISTICA-*` | Gimnasia artística |

## Fitness y actividades

| Prefijo / códigos | Hoja |
|-------------------|------|
| `ICDPE-GYM-*`, `…FITNESS*`, `…GIMNASIO*` | Gimnasio |
| `ICDPE-YOGA-*` | Yoga |
| `ICDPE-DANZA`, `…DANZA*` | Danza |
| `ICDPE-RITMOS-LATINOS*` | Ritmos latinos |
| `ICDPE-INICIACION-DEPORTIVA-*` | Iniciación deportiva |
| `ICDPE-FUNCIONAL-*`, `ICDPE-ARANCEL-MENSUAL-FUNCIONAL*`, `…ACT-funcional`, `…ACT-crossfit` | Funcional y CrossFit |
| `ICDPE-ARANCEL-MENSUAL-FITNESS*` | Gimnasio |

## Otros actividades

| Item / prefijo | Hoja |
|----------------|------|
| `ICDPE-CUOTA-FEDERATIVA-*` | Cuotas federativas |
| `ICDPE-COLONIAS`, `ICDPE-EVENTOS` | Actividades puntuales |

## Comerciales

| Item | Hoja |
|------|------|
| `ICDPE-ALQ-*`, `ICDPE-FIN-ALQUILER-TEMP` | Alquileres |
| `ICDPE-POS-*`, `ICDPE-FIN-BUFFET`, `ICDPE-FIN-RESTAURANTE`, `ICDPE-FIN-CANON-CONCESION` | Gastronomía |
| `ICDPE-FIN-SPONSOR`, `ICDPE-FIN-INDUMENTARIA` | Sponsors y ventas (canónicos) |
| `ICDPE-SPONSOR-PUB`, `ICDPE-VENTA-INDUMENTARIA` | Sponsors y ventas (**disabled** legacy) |
| `ICDPE-FIN-ENTRADAS` | Entradas y eventos |

## Institucionales

| Item | Hoja |
|------|------|
| `ICDPE-FIN-SUBSIDIO` | Subsidios |
| `ICDPE-FIN-DONACION` | Donaciones |
| `ICDPE-FIN-EVENTO-RECAUDACION` | Recaudación institucional |

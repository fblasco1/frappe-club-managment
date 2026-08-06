# Spec: Convención de nombres de aranceles mensuales (Item.item_name)

Los productos de arancel mensual deben compartir la misma lógica de nombre
visible en Desk / facturas, independiente del `item_code` (que permanece estable).

## Formato

```
ARANCEL MENSUAL - {ACTIVIDAD}/{RAMA}/{TIPO}/{GRUPO_O_TIRA}/{EQUIPO}
```

| Segmento | Valores | Cuándo |
|----------|---------|--------|
| ACTIVIDAD | `BASQUET`, `VOLEY`, `FUTBOL`, `PATIN ARTISTICO`, … | Siempre |
| RAMA | `MASCULINO`, `FEMENINO`, `MIXTO` | Si aplica |
| TIPO | `FORMATIVAS`, `MINIBASQUET`, `ESCUELITA`, `SUPERIOR`, … | Si aplica |
| GRUPO_O_TIRA | `AZUL`, `TABI A`, `TIRA`, frecuencias, … | Si aplica |
| EQUIPO | p. ej. `U11` | Solo si el ítem es 1:1 con un equipo |

**Reglas:**

1. Prefijo literal `ARANCEL MENSUAL - ` (espacio, guión, espacio).
2. Segmentos en **MAYÚSCULAS**, sin tildes (ASCII).
3. Omitir segmentos vacíos: no usar `N/A` ni dejar `//`.
4. El `item_code` **no** se renombra.

Helper: `format_arancel_mensual_item_name(*segments)` en `activities/data/arancel_item_spec.py`.

---

## Scenario: formatea nombre omitiendo vacíos

Given segmentos `BASQUET`, `MASCULINO`, `FORMATIVAS`, `AZUL`
When se formatea el nombre
Then el resultado es `ARANCEL MENSUAL - BASQUET/MASCULINO/FORMATIVAS/AZUL`

Given segmentos `DANZA` solamente
When se formatea
Then el resultado es `ARANCEL MENSUAL - DANZA`

Given un segmento vacío o None intercalado
When se formatea
Then no aparecen dobles barras

---

## Scenario: sincroniza item_name desde specs canónicos

Given Items existentes cuyo `item_code` figura en las specs de aranceles
And el `item_name` en DB difiere del de la spec
When corre `run_sync_arancel_item_names`
Then `Item.item_name` queda igual al de la spec
And el `item_code` no cambia

---

## Mapa canónico (resumen)

| item_code | item_name |
|-----------|-----------|
| `ICDPE-BASQUET-MASCULINO-MINIBASQUET` | `ARANCEL MENSUAL - BASQUET/MASCULINO/MINIBASQUET` |
| `ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL` | `ARANCEL MENSUAL - BASQUET/MASCULINO/FORMATIVAS/AZUL` |
| `ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA` | `ARANCEL MENSUAL - BASQUET/MASCULINO/FORMATIVAS/AMARILLA` |
| `ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX` | `ARANCEL MENSUAL - BASQUET/MASCULINO/FORMATIVAS/FLEX` |
| `ICDPE-BASQUET-ESCUELITA` | `ARANCEL MENSUAL - BASQUET/MIXTO/ESCUELITA` |
| `ICDPE-BASQUET-FEMENINO-SUP` | `ARANCEL MENSUAL - BASQUET/FEMENINO/SUPERIOR` |
| `ICDPE-VOLEY-TIRA-21500` | `ARANCEL MENSUAL - VOLEY/FEMENINO/TIRA/U11-U12` (legacy) |
| `ICDPE-VOLEY-TIRA-30500` | `ARANCEL MENSUAL - VOLEY/FEMENINO/TIRA/FORMATIVAS` |
| `ICDPE-VOLEY-ESCUELA-ADOLESCENTE` | `ARANCEL MENSUAL - VOLEY/FEMENINO/ESCUELA ADOLESCENTE` |
| `ICDPE-VOLEY-ESCUELITA-MINIVOLEY` | `ARANCEL MENSUAL - VOLEY/FEMENINO/ESCUELITA/MINIVOLEY` |
| `ICDPE-FUTBOL-FAFI` | `ARANCEL MENSUAL - FUTBOL/FAFI` |
| `ICDPE-FUTBOL-TABI-A` | `ARANCEL MENSUAL - FUTBOL/TABI A` |
| `ICDPE-FUTBOL-TABI-B` | `ARANCEL MENSUAL - FUTBOL/ESCUELITA/TABI B` |
| `ICDPE-PATIN-*` | `ARANCEL MENSUAL - PATIN ARTISTICO/{NIVEL}` |
| frecuencias (boxeo/yoga/…) | `ARANCEL MENSUAL - {ACT}/{N CLASE(S) POR SEMANA}` |
| planas (danza, taekwondo, …) | `ARANCEL MENSUAL - {ACT}` |

Nota: `ICDPE-BASQUET-ESCUELITA` también se usó históricamente en formativas femeninas; el label oficial refleja **MIXTO/ESCUELITA**.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Helper + spec dataclass | `activities/data/arancel_item_spec.py` |
| Specs de datos | `activities/data/*_aranceles_icdpe.py` |
| Sync | `activities/services/sync_arancel_item_names.py` |
| Patch | `patches/v1_0/sync_arancel_item_names.py` |
| Tests | `tests/test_arancel_item_naming.py` |

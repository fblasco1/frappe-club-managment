# Spec: Cobro del Gimnasio de Musculación (socios y no socios)

El club comienza a cobrar el **Gimnasio Fitness** (gimnasio de musculación) a
socios y no socios. Aranceles:

| Concepto | Precio | Cómo se modela |
|----------|--------|----------------|
| No socio (mensual) | 49.000 | Grupo `Gimnasio Fitness / No Socio` (`ICDPE-GYM-PASE-LIBRE-NO-SOCIO`) |
| Socio (mensual) | 24.000 | Grupo `Gimnasio Fitness / Socio` (`ICDPE-GYM-PASE-LIBRE-SOCIO`) |
| No socio con descuento | 44.100 | Grupo No Socio + **Bonificacion Recurrente** 10 % |
| Socio con descuento | 21.600 | Grupo Socio + **Bonificacion Recurrente** 10 % |
| Quincena (15 días) | 31.000 | `Cargo Socio` Único `Quincena Gimnasio` (`ICDPE-GYM-QUINCENA-NO-SOCIO`) |
| Entrenamiento por hora | 5.000 | `Cargo Socio` Único `Entrenamiento por Hora Gimnasio` (`ICDPE-GYM-ENTRENAMIENTO-HORA-NO-SOCIO`) |

El antiguo "Pase por día" se reemplaza por **Entrenamiento por hora**: el patch
`gimnasio_precios_entrenamiento_hora` renombra el ítem
`ICDPE-GYM-PASE-DIARIO-NO-SOCIO` y el tipo de cargo `Pase Diario Gimnasio`.

**Relacionado:** `patin_otras_actividades_aranceles_icdpe.md`,
`socios_categoria_validacion.md`, `cargo_extra_conceptos_y_facturacion.md`,
`beca_socio.md`, `bonificacion_arancel_al_cobro.md`, `cobranza_periodica_mensual.md`

---

## Modelo

### Practicante No Socio

- Es un `Socio` con `categoria = "No Socio"` (base única de practicantes).
- `name` con serie propia `NS-#####`; `numero_socio` vacío (no consume la
  numeración de socios ni aparece en el padrón).
- Cuota social = 0 (`resolve_cuota_social` → `(0, None)`).
- Solo puede inscribirse en actividades con `Actividad.admite_no_socios = 1`
  (hoy: Gimnasio Fitness) y en grupos con `Grupo Actividad.condicion_socio = "No Socio"`.
- No es solicitable en flujos públicos (Solicitud de Asociación / alta grupo familiar).

### Condición del grupo

`Grupo Actividad.condicion_socio` (`""` / `Socio` / `No Socio`):

- `No Socio` → solo practicantes No Socio.
- `Socio` → solo socios (cualquier categoría salvo No Socio).
- vacío → sin restricción por condición (resto de actividades: solo socios, ver regla de actividad).

### Quincena y Entrenamiento por hora

- Solo practicantes No Socio registrados; no exigen inscripción activa.
- Se generan desde Secretaría como `Cargo Socio` `modo_cobro = Unico` (factura al crearse).
- Opcionalmente se registra el pago en el mismo paso (`Payment Entry`).
- Monto: `Item Price` / `standard_rate` del ítem (editable); si es 0, se rechaza
  hasta que Secretaría cargue el precio (o se informa un monto explícito).

### Sincronización de precios

`sincronizar_precios_gimnasio()` aplica los precios de la tabla a los cuatro
ítems del gimnasio en todos los lugares donde se leen: `Item.standard_rate`, los
`Item Price` existentes y el `cost` del `Subscription Plan` del ítem, si existe.

### Bonificacion Recurrente

DocType `Bonificacion Recurrente` (`BRE-{YYYY}-{#####}`):

| Campo | Rol |
|-------|-----|
| `socio` | Obligatorio |
| `actividad` | Obligatorio (default Gimnasio Fitness) |
| `grupo_actividad` | Opcional: restringe a un grupo |
| `tipo_descuento` | `Porcentaje` \| `Monto fijo` |
| `valor` | % (0–100] o monto; default 10 |
| `fecha_desde` / `fecha_hasta` | Vigencia (`fecha_hasta` opcional = sin vencimiento) |
| `estado` | `Activa` / `Anulada` |
| `motivo` | Obligatorio |

- Se aplica **al generar la deuda** (`build_invoice_items_for_socio`), solo a la
  línea de arancel de la inscripción que coincide (actividad y, si se indicó, grupo).
- No aplica a cuota social, cargos extra, Quincena ni Entrenamiento por hora.
- **No se acumula con Beca:** si hay `Beca Socio` vigente, se aplica la beca y la
  bonificación se ignora.
- No puede haber dos bonificaciones Activas solapadas para el mismo socio y actividad.

---

## Scenario: alta de practicante No Socio

Given rol Secretaria
When crea un practicante No Socio con datos personales válidos
Then se crea un `Socio` con `categoria = "No Socio"` y `name` que empieza con `NS-`
And `numero_socio` queda vacío
And el estado queda `Activo` y existe su `Customer`
And queda inscripto en Gimnasio Fitness, grupo No Socio.

## Scenario: No Socio no consume numeración de socios

Given el máximo número de socio es N
When se crea un practicante No Socio y luego un socio sin número
Then el socio recibe el número N + 1.

## Scenario: No Socio sin cuota social

Given un practicante No Socio Activo inscripto en el gimnasio
When se arman las líneas de la deuda mensual
Then no hay línea de cuota social
And hay una línea con el arancel `ICDPE-GYM-PASE-LIBRE-NO-SOCIO`.

## Scenario: No Socio solo en actividades que admiten no socios

Given un practicante No Socio
When se lo inscribe en una actividad sin `admite_no_socios`
Then se rechaza la inscripción.

## Scenario: correspondencia grupo ↔ condición

Given un practicante No Socio
When se lo inscribe en Gimnasio Fitness / Socio
Then se rechaza.
Given un socio (categoría Activo)
When se lo inscribe en Gimnasio Fitness / No Socio
Then se rechaza
And en Gimnasio Fitness / Socio se acepta.

## Scenario: Entrenamiento por hora para No Socio con cobro inmediato

Given un practicante No Socio y los ítems del gimnasio sincronizados
When Secretaría genera el cargo `Entrenamiento por Hora Gimnasio` con `registrar_pago = 1`
Then se crea un `Cargo Socio` Único Facturado por 5.000 con su `Sales Invoice`
And se crea un `Payment Entry` que salda la factura.

## Scenario: Quincena sin pago inmediato

Given un practicante No Socio
When Secretaría genera `Quincena Gimnasio` con `registrar_pago = 0`
Then se crea el cargo facturado por 31.000 y la factura queda impaga.

## Scenario: socio no puede comprar Quincena / Entrenamiento por hora

Given un socio (categoría distinta de No Socio)
When se intenta crear un `Cargo Socio` de tipo `Quincena Gimnasio` o `Entrenamiento por Hora Gimnasio`
Then se rechaza.

## Scenario: sincronizar precios del gimnasio

Given el ítem `ICDPE-GYM-PASE-LIBRE-SOCIO` con `Item Price` y `Subscription Plan` en 22.000
When se ejecuta `sincronizar_precios_gimnasio()`
Then `standard_rate`, el `Item Price` y el `cost` del plan quedan en 24.000
And No Socio queda en 49.000, Quincena en 31.000 y Entrenamiento por hora en 5.000.

## Scenario: migración del pase diario

Given existe el ítem `ICDPE-GYM-PASE-DIARIO-NO-SOCIO` y cargos `Pase Diario Gimnasio`
When corre el patch `gimnasio_precios_entrenamiento_hora`
Then el ítem pasa a llamarse `ICDPE-GYM-ENTRENAMIENTO-HORA-NO-SOCIO`
And los cargos quedan con tipo `Entrenamiento por Hora Gimnasio`.

## Scenario: precio no configurado

Given el ítem de Quincena con precio 0
When Secretaría genera el cargo sin monto explícito
Then se rechaza indicando configurar el precio.

## Scenario: bonificación recurrente vigente

Given un socio inscripto en Gimnasio Fitness / Socio (24.000) y en otra actividad
And una `Bonificacion Recurrente` Activa 10 % para Gimnasio Fitness vigente
When se arman las líneas de la deuda mensual
Then la línea del gimnasio es 21.600 con descripción que indica la bonificación
And la otra actividad no cambia.

## Scenario: bonificación fuera de vigencia o anulada

Given una bonificación cuya vigencia terminó o en estado Anulada
When se arman las líneas
Then el arancel del gimnasio sale completo.

## Scenario: beca vigente + bonificación

Given un socio con `Beca Socio` vigente y una bonificación recurrente vigente
When se arman las líneas
Then se aplica solo la beca.

## Scenario: solapamiento

Given una bonificación Activa para socio S y Gimnasio Fitness desde 01/06 sin fin
When se crea otra Activa para S y Gimnasio Fitness desde 01/09
Then se rechaza.

## Scenario: conversión No Socio → Socio

Given un practicante No Socio `NS-00001` con Customer, facturas e inscripciones
When Secretaría lo convierte a socio con categoría `Activo`
Then el documento se renombra al próximo número de socio
And `numero_socio` toma ese número y la categoría pasa a `Activo`
And Customer, facturas e inscripciones apuntan al nuevo nombre.

## Scenario: corregir número no aplica a No Socio

Given un practicante No Socio
When Secretaría intenta «Corregir número de socio»
Then se rechaza indicando usar «Convertir a socio».

## Scenario: exclusiones de padrón

Given practicantes No Socio activos
When se calculan los KPIs de socios del panel de Secretaría (total, altas)
Then los No Socio no se cuentan
And `No Socio` no figura entre las categorías solicitables públicamente.

Nota: hoy no existe job de promoción a Vitalicio; cuando se implemente
(`socios_categoria_validacion.md`) debe excluir la categoría No Socio.

---

## Seguridad

- Crear practicantes, cargos de gimnasio, convertir y crear bonificaciones exige
  `ensure_secretaria_operacion_access` (Secretaria / System Manager).
- API Desk de cargos de gimnasio verifica `frappe.has_permission("Cargo Socio", "create")`.
- `Bonificacion Recurrente`: un usuario Socio solo lee las propias
  (`permission_query_conditions` + `has_permission`); no puede crear.
- Diálogos Desk escapan los datos de usuario (`frappe.utils.escape_html`).

---

## Artefactos

| Pieza | Ubicación |
|-------|-----------|
| Spec | este archivo |
| Practicante No Socio | `members/services/practicante_no_socio.py` |
| Condición inscripción | `activities/doctype/inscripcion_actividad/inscripcion_actividad.py` |
| Pases | `members/services/gimnasio_pases.py`, `members/api/gimnasio_desk.py` |
| Bonificación | `members/doctype/bonificacion_recurrente/`, `members/services/bonificacion_recurrente.py` |
| Tests | `members/tests/test_practicante_no_socio.py`, `activities/tests/test_gimnasio_inscripcion_condicion.py`, `members/doctype/bonificacion_recurrente/test_bonificacion_recurrente.py`, `members/tests/test_gimnasio_pase_quincena.py` |

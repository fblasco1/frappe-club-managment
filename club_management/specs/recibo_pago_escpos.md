# Spec: Recibo de pago térmico (ESC/POS)

Al registrar un cobro manual, Secretaría debe poder entregar al socio un
comprobante impreso en la impresora térmica **Star Micronics BSC-10UD**
(lenguaje ESC/POS, papel 58 mm u 80 mm).

---

## Configuración en `Club Settings`

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `recibo_institucion_nombre` | Data | ICDPE (ver seed) | Nombre en encabezado |
| `recibo_institucion_direccion` | Data | PORTELA 836 - CABA | Dirección |
| `recibo_cuit` | Data | — | CUIT del club |
| `recibo_condicion_iva` | Data | IVA EXENTO | Leyenda fiscal |
| `recibo_mensaje_pie` | Small Text | SOMOS ECHAGUE... | Pie del recibo |
| `recibo_ancho_papel_mm` | Select (58, 80) | 58 | Ancho del rollo |
| `recibo_impresora_url` | Data | vacío | URL Star WebPRNT opcional |

---

## Scenario: datos del recibo tras registrar cobro

Given un `Socio` con factura pendiente y líneas de concepto (cuota, arancel, etc.)
And Secretaría registra el cobro vía `registrar_cobro_manual`
When la API `registrar_cobro` responde con éxito
Then incluye un objeto `recibo` con:
  - `comprobante` = nombre del `Payment Entry`
  - `fecha` y `hora` del cobro (posting_date + hora local)
  - `lineas[]` con `concepto` y `monto` de cada ítem de la factura pagada
  - `total` = suma de montos
  - `texto` = vista previa en texto plano
  - `escpos_base64` = bytes ESC/POS codificados en base64
  - `ancho_papel_mm` según Club Settings

---

## Scenario: líneas del recibo con período y mora

Given un cobro que saldó una cuota de período `03/2026` y su SI de ajuste de mora
When se genera el recibo
Then cada línea de concepto incluye el **período** (p. ej. prefijo `03/2026 · …`)
And la línea de mora muestra la **composición** del recargo (valor × factores)
And el orden de líneas sigue el período calendario (más antiguo primero).

---

## Scenario: formato del texto del recibo

Given Club Settings con encabezado ICDPE configurado
And un cobro por $50.500 con dos conceptos
When se genera el recibo
Then el texto incluye (en este orden):
  1. Nombre de la institución (centrado)
  2. Dirección (centrado)
  3. CUIT y condición IVA
  4. Separador `---`
  5. `COMPROBANTE` y número
  6. Fecha y hora
  7. Tabla `CONCEPTO` / `VALOR` con cada línea y total
  8. Mensaje de pie

And los montos usan formato argentino (`$29.000`).

---

## Scenario: ESC/POS válido

Given un recibo generado
When se decodifica `escpos_base64`
Then los bytes comienzan con inicialización ESC/POS (`ESC @`)
And terminan con corte de papel (`GS V`)
And el texto legible del cuerpo coincide con `texto` (sin códigos de control).

---

## Scenario: ancho de papel

Given `recibo_ancho_papel_mm = 58`
When se formatea una línea concepto + monto
Then el ancho máximo es 32 caracteres.

Given `recibo_ancho_papel_mm = 80`
Then el ancho máximo es 48 caracteres.

---

## Scenario: permisos API recibo

Given usuario con rol `Secretaria`
When llama a `get_recibo_pago(payment_entry)` de un cobro existente
Then recibe el objeto recibo.

Given usuario sin rol Secretaría / System Manager
When llama a `get_recibo_pago`
Then error de permiso.

---

## Scenario: impresión automática en Desk tras cobro

Given cobro registrado desde formulario `Socio`
When la API devuelve `recibo`
Then el cliente envía la impresión de inmediato (sin diálogo de confirmación)
And si `recibo_impresora_url` está configurada, envía ESC/POS vía Star WebPRNT
And si no hay URL, abre vista previa imprimible (CSS 58/80 mm) vía `window.print()`.

---

## Artefactos

| Artefacto | Ubicación |
|-----------|-----------|
| Spec | `specs/recibo_pago_escpos.md` |
| Servicio | `members/services/recibo_pago.py` |
| API | `members/api/cobranza_desk.py` |
| Club Settings | `members/doctype/club_settings/` |
| Tests | `members/tests/test_recibo_pago.py` |
| Cliente | `public/js/recibo_pago_escpos.js`, `socio.js` |

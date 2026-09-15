# Spec: Reporte PDF de ocupación de espacios

**Épica base:** Épica 4 de `spaces_sprint_gestion.md` (exportar ocupación del día).
**Fuera de este slice:** email a coordinadores / WhatsApp — solo descarga PDF.

**Roles con lectura Spaces:** Secretaria, Coordinacion, Tesoreria, System Manager.
**Ventana:** misma que `/desk/ocupacion-espacios` — **08:00–04:00** (día siguiente).

**API:** `club_management.spaces.api.ocupacion_reporte.download_ocupacion_pdf`
**Servicio:** `club_management.spaces.services.ocupacion_reporte_pdf`

---

## Scenario: Secretaria exporta PDF de un día

Given un usuario con rol **Secretaria** (o Coordinacion / Tesoreria / System Manager)
And existen espacios habilitados y ocupación para la fecha `2026-09-05`
When llama a `download_ocupacion_pdf` con `fecha=2026-09-05`
Then recibe un archivo PDF descargable (bytes que empiezan con `%PDF`)
And el contenido refleja la planilla del día (espacios como columnas, franjas 08:00–04:00)
And cada bloque muestra título y tipo/categoría
And reservas **Pendiente** vs **Confirmada** se distinguen visualmente en el HTML/PDF si aplica.

---

## Scenario: rango o lista de fechas

Given un usuario autorizado
When exporta con `fecha_desde` + `fecha_hasta` (p. ej. 2 días consecutivos)
Or con una lista `fechas` de hasta **31** días
Then el PDF incluye una planilla por cada día del rango/lista
And el PDF no está vacío
When el rango supera 31 días
Then el sistema rechaza con ValidationError.

---

## Scenario: XSS — títulos y arrendatario escapados

Given un bloque de ocupación cuyo título o `arrendatario_nombre` contiene `<script>alert(1)</script>`
When se construye el HTML del reporte
Then el texto aparece escapado (`&lt;script&gt;…`)
And no se inyecta markup ejecutable en el HTML.

---

## Scenario: sin rol Spaces → PermissionError

Given un usuario **Socio** (u otro sin roles de lectura Spaces)
When intenta descargar el PDF de ocupación
Then recibe **PermissionError**.

---

## Scenario: Guest → PermissionError

Given sesión **Guest**
When llama a `download_ocupacion_pdf`
Then recibe **PermissionError**.

---

## Scenario: UI Desk — botón Exportar PDF

Given Secretaria en `/desk/ocupacion-espacios`
When usa el botón **Exportar PDF**
Then un diálogo pide fecha desde / fecha hasta (default = fecha actual de la planilla)
And al confirmar se descarga el PDF del rango.

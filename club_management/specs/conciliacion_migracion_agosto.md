# Spec: Conciliación migración cobranzas agosto 2026

Cierre de la migración histórica: cruzar el CSV consolidado de agosto
contra Payment Entries `INF-*` del sistema, por **concepto** y por
**equipo/grupo** (alias de arancel del informe).

**Relacionado:** `carga_masiva_cobranzas.md`, `informe_concepto_cobranza.md`,
`pagos_por_equipo.md`

---

## Scenario: faltante a imputar

Given una fila del CSV de agosto con concepto y monto M
And no existe `Payment Entry` `docstatus=1` en el rango de cobro cuyo
  `reference_no` parsea al mismo socio / período / concepto / monto (±$0.50)
When se ejecuta la conciliación de cierre
Then la fila aparece en el log de **faltantes** con bucket `sin_pe_inf`
And el monto queda en el subtotal de faltantes.

---

## Scenario: cuadratura por concepto

Given el CSV con subtotales por concepto normalizado
And los PE `INF-*` del rango agrupados por el concepto parseado de `reference_no`
When se compara CSV vs sistema
Then cada concepto con `|gap| > $0.50` entra en el log de gaps por concepto
And el resumen incluye total CSV, total PE y gap global.

---

## Scenario: cuadratura por equipo/grupo (aranceles de tira)

Given conceptos del informe que son alias de equipo/tira (p. ej. `U17 FLEX`, `SUPERIOR B`)
When se agrupa el CSV y los PE `INF-*` por ese alias
Then los gaps por alias quedan en el log de equipo/grupo
And conceptos que no son alias de arancel (cuota, CTO COMP, federativa) no entran en ese corte.

---

## Scenario: pe_monto_distinto alineado con PE de mora

Given una fila CSV con monto M (base+mora) y un PE `INF-*` con `paid_amount` = base
And existe PE submitted contra la SI mora del mismo origen por el gap
And el concepto **sí** admite mora (cuota social / arancel; **no** C FED ni CTO COMP)
When corre la conciliación
Then la fila queda bucket `ok` (o `ok_con_mora`) con paid efectivo = base+mora
And **no** entra al listado de diferencias pendientes.

---

## Scenario: C FED y CTO COMP no aplican mora

Given concepto federativa (`C FED …`) o `CTO COMP …`
When se analiza un gap CSV vs PE INF
Then no se interpreta como mora legítima del tramo 10%/15%
And si el total INF+PE-mora cierra el CSV, se marca alineado con nota de split indebido
And los outliers históricos (BOXEO 12275, PATIN 8770, CTO COMP VOLEY 12235)
  quedan registrados con resolución de cierre (ya no pendientes de Desk).

---

## Scenario: cierre outliers manuales agosto 2026

Given los tres outliers de `pe_monto_distinto` tras alineación de mora
When el club confirma el criterio de cierre
Then **BOXEO 12275** queda `resuelto_manual` (ajuste Desk ya aplicado)
And **PATIN INTERMEDIO 8770** queda `ignorado_error_cobrador` (cobró 10% con fecha post-día-20; se asume error del cobrador)
And **CTO COMP VOLEY ESC 12235** queda `liquidado_a_4000` (SI/PE a $4.000 Paid; el CSV $4.300 se descarta)
And `outlier_pendiente(...)` es False para los tres.

---

## Scenario: errores de mapeo

Given filas cuyo concepto no resuelve a ítem (y no es CTO COMP)
When corre la conciliación
Then se listan en el log como `concepto_sin_mapeo` / socio no encontrado.

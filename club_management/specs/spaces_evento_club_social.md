# Spec: Eventos sociales del club (Evento club recurrente)

Actividades sociales de la grilla CSV (p. ej. **CENA SEMANAL VITALICIOS**,
**CENTRO DE JUBILADOS**) deben modelarse como **`Reserva Espacio` tipo
`Evento club`** con **recurrencia semanal**, no como fila de grilla
`Horario Entrenamiento`.

**Relacionado:** `spaces_ocupacion_dashboard.md`, `spaces_catalogo_ocupacion.md`

---

## Scenario: CSV importa cena vitalicios como Evento club

Given una fila CSV `VIERNES;SALA ALBAMONTE;DESDE 20.00;CENA SEMANAL VITALICIOS;`
When se ejecuta `import_horarios_csv`
Then se crea (o actualiza) una `Reserva Espacio` Confirmada tipo `Evento club`
con `recurrencia_semanal = 1`, día `Viernes`, 20:00–22:00 y motivo «CENA SEMANAL VITALICIOS»
And **no** se agrega esa actividad a la grilla semanal del espacio.

---

## Scenario: detección de evento social por palabras clave

Given actividades cuyo texto contiene `CENA`, `VITALICIO`, `JUBILADOS`, `FIESTA` o `ASADO`
When se parsea la fila CSV
Then se clasifica como evento club social (no entrenamiento ni alquiler ALQ.*).

---

## Scenario: evento club recurrente ocupa el día de la semana

Given `Reserva Espacio` Confirmada tipo `Evento club` con `recurrencia_semanal = 1`,
`fecha_desde = 2026-01-01`, `fecha_hasta = 2026-12-31`, día `Viernes`, 20:00–22:00
When se consulta ocupación para un viernes dentro del rango
Then el slot aparece como reserva `Evento club` en el dashboard.

---

## Scenario: superposición — elegir qué evento modificar

Given dos bloques solapados en la misma columna de espacio en la planilla
When Coordinación hace clic en uno de ellos
Then se muestra un diálogo listando **todos** los eventos del solape
And al elegir uno se abre la acción correspondiente (formulario Reserva / reubicar grilla / excepción).

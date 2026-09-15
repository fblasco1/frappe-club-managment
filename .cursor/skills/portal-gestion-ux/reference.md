# Tokens y markup — portal gestión

## Tokens

```scss
body.club-portal-theme {
  --bg-color: #f3f4f6;
  --club-radius: 10px;
  --club-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
  --club-accent: /* según --socios|actividades|espacios|tesoreria */;
}
```

## Markup mínimo de pantalla

```html
<div class="club-mi-modulo">
  <div class="club-portal-toolbar">
    <div class="club-portal-field">
      <label for="filtro-a">Fecha</label>
      <input id="filtro-a" type="date" class="form-control form-control-sm">
    </div>
    <div class="club-portal-field">
      <label for="filtro-b">Espacio</label>
      <select id="filtro-b" class="form-control form-control-sm">
        <option value="">Todos</option>
      </select>
    </div>
    <span class="club-portal-chip">Sábado</span>
  </div>

  <div class="row">
    <section class="club-portal-panel col">
      <h5 class="club-portal-panel-title">Pendientes</h5>
      …
    </section>
    <section class="club-portal-panel col">
      <h5 class="club-portal-panel-title">Agenda</h5>
      …
    </section>
  </div>

  <div class="club-portal-cta-row">
    <button type="button" class="btn btn-default btn-sm">Secundaria</button>
    <button type="button" class="btn btn-primary btn-sm">Primaria</button>
  </div>
</div>
```

## Activación

No hace falta setear clases a mano en cada page: `club_desk_navigation.apply_portal_theme()` corre en cada `refresh` si `is_club_desk_page()`.

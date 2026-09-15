/* global frappe */

(function () {
	frappe.provide("club_management.espacios_dashboard_page");

	club_management.espacios_dashboard_page = {
		page: null,
		_fecha: null,
		_espacio: "",
		_data: null,

		init(page) {
			this.page = page;
			page.main.addClass("club-espacios-dashboard");
			this._fecha = frappe.datetime.get_today();
			this._espacio = "";
			this._build_layout();
			this.load();
		},

		refresh() {
			if (this.page) {
				this.load();
			}
		},

		_build_layout() {
			const page = this.page;
			page.set_primary_action(__("Actualizar"), () => this.load(), "refresh");
			page.add_inner_button(__("Listado de espacios"), () => {
				frappe.set_route("List", "Espacio");
			});
			page.add_inner_button(__("Ocupación de Espacios"), () => {
				frappe.set_route("ocupacion-espacios");
			});

			const $body = $(`
				<div class="club-espacios-dash">
					<div class="club-espacios-dash-toolbar">
						<div class="club-espacios-field">
							<label for="club-espacios-fecha">${__("Fecha")}</label>
							<input id="club-espacios-fecha" type="date" class="form-control form-control-sm club-espacios-fecha">
						</div>
						<div class="club-espacios-field">
							<label for="club-espacios-filtro">${__("Espacio")}</label>
							<select id="club-espacios-filtro" class="form-control form-control-sm club-espacios-filtro">
								<option value="">${__("Todos")}</option>
							</select>
						</div>
						<span class="club-espacios-dia-label"></span>
					</div>
					<div class="club-espacios-dash-grid">
						<section class="club-espacios-panel">
							<h5 class="club-espacios-panel-title">${__("Solicitudes de reserva pendientes")}</h5>
							<div class="club-espacios-pendientes"></div>
						</section>
						<section class="club-espacios-panel">
							<h5 class="club-espacios-panel-title">${__("Actividades del día")}</h5>
							<div class="club-espacios-agenda"></div>
						</section>
					</div>
				</div>
			`);
			// Conservar la barra club-desk-nav si ya está montada en page.main.
			page.main.children().not("#club-desk-nav").remove();
			page.main.append($body);
			club_management.club_desk_navigation?.schedule_refresh?.();
			$body.find(".club-espacios-fecha").val(this._fecha).on("change", (e) => {
				this._fecha = e.target.value;
				this.load();
			});
			$body.find(".club-espacios-filtro").on("change", (e) => {
				this._espacio = e.target.value || "";
				this.load();
			});
		},

		load() {
			frappe.call({
				method: "club_management.spaces.api.espacios_desk_dashboard.get_espacios_desk_dashboard",
				args: { fecha: this._fecha, espacio: this._espacio || null },
				freeze: true,
				callback: (r) => {
					this._data = r.message || {};
					this._render();
				},
			});
		},

		_render() {
			const data = this._data || {};
			const $main = this.page.main;
			$main.find(".club-espacios-dia-label").text(data.dia_semana || "");

			const $sel = $main.find(".club-espacios-filtro");
			const current = this._espacio;
			$sel.empty().append(`<option value="">${__("Todos")}</option>`);
			(data.espacios || []).forEach((esp) => {
				const label = esp.titulo || esp.name;
				$sel.append(`<option value="${frappe.utils.escape_html(esp.name)}">${frappe.utils.escape_html(label)}</option>`);
			});
			$sel.val(current);

			const pendientes = data.pendientes || [];
			const $pend = $main.find(".club-espacios-pendientes").empty();
			if (!pendientes.length) {
				$pend.append(`<p class="text-muted">${__("No hay solicitudes pendientes.")}</p>`);
			} else {
				const $ul = $("<ul class='list-unstyled'>");
				pendientes.forEach((row) => {
					const hora = `${(row.hora_desde || "").toString().slice(0, 5)}–${(row.hora_hasta || "").toString().slice(0, 5)}`;
					const title = frappe.utils.escape_html(row.motivo || row.tipo || row.name);
					const meta = frappe.utils.escape_html(`${row.espacio || ""} · ${row.fecha || ""} · ${hora}`);
					$ul.append(
						`<li class="mb-2">
							<a href="/app/reserva-espacio/${encodeURIComponent(row.name)}">${title}</a>
							<div class="text-muted small">${meta}</div>
						</li>`
					);
				});
				$pend.append($ul);
			}

			const agenda = data.actividades_dia || [];
			const $agenda = $main.find(".club-espacios-agenda").empty();
			if (!agenda.length) {
				$agenda.append(`<p class="text-muted">${__("Sin actividades para el día seleccionado.")}</p>`);
			} else {
				const $table = $(`
					<table class="table table-bordered table-sm">
						<thead>
							<tr>
								<th>${__("Hora")}</th>
								<th>${__("Espacio")}</th>
								<th>${__("Actividad")}</th>
							</tr>
						</thead>
						<tbody></tbody>
					</table>
				`);
				const $tbody = $table.find("tbody");
				agenda.forEach((row) => {
					const hora = `${row.hora_desde || ""}–${row.hora_hasta || ""}`;
					$tbody.append(
						`<tr>
							<td>${frappe.utils.escape_html(hora)}</td>
							<td>${frappe.utils.escape_html(row.espacio_titulo || row.espacio || "")}</td>
							<td>${frappe.utils.escape_html(row.titulo || "")}</td>
						</tr>`
					);
				});
				$agenda.append($table);
			}
		},
	};
})();

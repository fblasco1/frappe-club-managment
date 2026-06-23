/* global frappe */

(function () {
	frappe.provide("club_management.valores_cuota_social_page");

	club_management.valores_cuota_social_page = {
		_state: null,

		init(page) {
			this.page = page;
			page.main.addClass("club-valores-cuota-page");
			this.load();
		},

		load() {
			frappe.call({
				method: "club_management.members.api.secretaria_workspace.get_cuotas_sociales",
				callback: (r) => {
					if (r.message) {
						this._state = r.message;
						this.render();
					}
				},
			});
		},

		render() {
			const cuotas = this._state?.cuotas || [];
			if (!cuotas.length) {
				this.page.main.html(
					`<p class="text-muted">${__("No hay categorías de cuota configuradas.")}</p>`
				);
				return;
			}

			const rows = cuotas
				.map(
					(row) => `
				<tr data-categoria="${frappe.utils.escape_html(row.categoria)}">
					<td>${frappe.utils.escape_html(row.categoria)}</td>
					<td>
						<input type="number" class="form-control form-control-sm club-cuota-monto"
							min="0" step="0.01" value="${frappe.utils.escape_html(String(row.monto || 0))}">
					</td>
					<td class="text-muted small">${frappe.utils.escape_html(row.item || this._state.item_cuota_social_default || "")}</td>
				</tr>`
				)
				.join("");

			this.page.main.html(`
				<div class="club-valores-cuota-card">
					<p class="text-muted club-valores-cuota-intro">
						${__("Montos mensuales de cuota social por categoría de socio. Los cambios se sincronizan con ERPNext.")}
					</p>
					<div class="table-responsive">
						<table class="table table-sm club-cuotas-table mb-3">
							<thead>
								<tr>
									<th>${__("Categoría")}</th>
									<th>${__("Monto mensual")}</th>
									<th>${__("Ítem ERPNext")}</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
						</table>
					</div>
					<button type="button" class="btn btn-primary club-valores-cuota-save">
						${__("Guardar cuotas")}
					</button>
				</div>
			`);

			this.page.main.find(".club-valores-cuota-save").on("click", () => this.save());
		},

		save() {
			const rows = [];
			this.page.main.find(".club-cuotas-table tbody tr").each((_, tr) => {
				const $tr = $(tr);
				rows.push({
					categoria: $tr.data("categoria"),
					monto: parseFloat($tr.find(".club-cuota-monto").val()) || 0,
				});
			});

			frappe.call({
				method: "club_management.members.api.secretaria_workspace.save_cuotas_sociales",
				args: { rows },
				freeze: true,
				callback: (r) => {
					if (r.message) {
						this._state = r.message;
						frappe.show_alert({ message: __("Cuotas guardadas"), indicator: "green" });
						this.render();
					}
				},
			});
		},
	};
})();

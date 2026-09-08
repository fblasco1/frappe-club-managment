/* global frappe */

frappe.ui.form.on("Equipo Actividad", {
	refresh(frm) {
		club_equipo_actividad_add_actions(frm);
		club_equipo_actividad_load_arancel(frm);
		club_equipo_actividad_load_roster(frm);
	},

	grupo_actividad(frm) {
		if (frm.is_new()) {
			club_equipo_actividad_load_roster(frm);
		} else {
			club_equipo_actividad_load_arancel(frm);
		}
	},

	item(frm) {
		club_equipo_actividad_load_arancel(frm);
	},
});

function club_equipo_actividad_add_actions(frm) {
	frm.add_custom_button(__("Volver al catálogo"), () => {
		frappe.set_route("catalogo-actividades");
	});
	if (!frm.is_new()) {
		frm.add_custom_button(__("Nueva bonificación arancel"), () => {
			frappe.route_options = {
				equipo_actividad: frm.doc.name,
				grupo_actividad: frm.doc.grupo_actividad,
				actividad: frm.doc.actividad,
			};
			frappe.new_doc("Bonificacion Arancel");
		});
	}
}

function club_equipo_actividad_arancel_panel(frm) {
	const $anchor =
		frm.fields_dict.item?.$wrapper ||
		frm.fields_dict.grupo_actividad?.$wrapper?.closest(".form-section");
	let $panel = frm.layout.wrapper.find(".club-equipo-actividad-arancel");
	if (!$panel.length && $anchor?.length) {
		$panel = $(
			'<div class="club-equipo-actividad-arancel" style="margin: 0.5rem 0 1rem;"></div>'
		);
		if (frm.fields_dict.item?.$wrapper?.length) {
			frm.fields_dict.item.$wrapper.after($panel);
		} else {
			$anchor.after($panel);
		}
	}
	return $panel;
}

function club_equipo_actividad_format_arancel(arancel) {
	const data = arancel || {};
	// Preferir texto plano del servidor (evita HTML de Currency + escape_html).
	if (data.resumen_texto) {
		return data.resumen_texto;
	}
	if (!data.item) {
		return __("Sin arancel asignado (equipo / grupo / actividad).");
	}
	const label = data.item_name || data.item;
	const rateNum = Number(data.rate || 0);
	const rateLabel = rateNum.toLocaleString(undefined, {
		minimumFractionDigits: 0,
		maximumFractionDigits: 2,
	});
	return __("Arancel efectivo: {0} — ${1} (origen: {2})", [
		label,
		rateLabel,
		data.origen || __("Sin arancel"),
	]);
}

function club_equipo_actividad_load_arancel(frm) {
	const $panel = club_equipo_actividad_arancel_panel(frm);
	if (!$panel.length) {
		return;
	}
	if (frm.is_new() || !frm.doc.name) {
		$panel
			.show()
			.html(
				`<div class="text-muted small">${__(
					"Guardá el equipo para ver el arancel efectivo de cobro."
				)}</div>`
			);
		return;
	}

	$panel.show().html(`<p class="text-muted small">${__("Cargando arancel…")}</p>`);
	frappe.call({
		method: "club_management.activities.api.equipo_actividad_desk.get_arancel_resumen",
		args: { equipo_actividad: frm.doc.name },
		callback(res) {
			const text = club_equipo_actividad_format_arancel(res.message || {});
			$panel.html(
				`<div class="alert alert-info small mb-0" style="padding: 0.5rem 0.75rem;">${frappe.utils.escape_html(
					text
				)}</div>`
			);
		},
	});
}

function club_equipo_actividad_roster_panel(frm) {
	const $anchor = frm.fields_dict.grupo_actividad?.$wrapper?.closest(".form-section");
	let $panel = frm.layout.wrapper.find(".club-equipo-actividad-roster");
	if (!$panel.length && $anchor?.length) {
		$panel = $(
			'<div class="club-equipo-actividad-roster" style="margin-top: 0.75rem; margin-bottom: 1rem;"></div>'
		);
		$anchor.after($panel);
	}
	return $panel;
}

function club_equipo_actividad_load_roster(frm) {
	const $panel = club_equipo_actividad_roster_panel(frm);
	if (!$panel.length) {
		return;
	}

	const grupo = frm.doc.grupo_actividad;
	const equipo = frm.doc.name;
	if (!grupo && !equipo) {
		$panel.empty().hide();
		return;
	}

	$panel.show().html(`<p class="text-muted small">${__("Cargando socios inscriptos…")}</p>`);

	frappe.call({
		method: "club_management.activities.api.equipo_actividad_desk.list_socios_grupo_equipo",
		args: {
			grupo_actividad: grupo,
			equipo_actividad: equipo || null,
		},
		callback(res) {
			club_equipo_actividad_render_roster($panel, res.message || [], {
				grupo,
				equipo,
			});
		},
	});
}

function club_equipo_actividad_render_roster($panel, rows, ctx) {
	const scope_label = ctx.equipo ? __("este equipo") : __("este grupo / tira");

	if (!rows.length) {
		$panel.html(
			`<div class="text-muted small">${__(
				"No hay socios con inscripción activa en {0}.",
				[scope_label]
			)}</div>`
		);
		return;
	}

	const body = rows
		.map((row) => {
			const fecha = row.ult_fecha_pago
				? frappe.datetime.str_to_user(row.ult_fecha_pago)
				: "";
			return `<tr>
				<td><a href="/app/socio/${encodeURIComponent(row.socio)}">${frappe.utils.escape_html(
					row.socio
				)}</a></td>
				<td>${frappe.utils.escape_html(row.nombre || "")}</td>
				<td>${frappe.utils.escape_html(row.apellido || "")}</td>
				<td>${frappe.utils.escape_html(row.dni || "")}</td>
				<td>${frappe.utils.escape_html(row.telefono_movil || "")}</td>
				<td>${frappe.utils.escape_html(fecha)}</td>
			</tr>`;
		})
		.join("");

	$panel.html(`
		<div class="small text-muted" style="margin-bottom: 0.35rem;">
			${__("Socios inscriptos")} (${rows.length}) — ${scope_label}
		</div>
		<div class="table-responsive">
			<table class="table table-bordered table-sm club-equipo-actividad-roster-table">
				<thead>
					<tr>
						<th>${__("ID")}</th>
						<th>${__("Nombre")}</th>
						<th>${__("Apellido")}</th>
						<th>${__("DNI")}</th>
						<th>${__("Teléfono móvil")}</th>
						<th>${__("Últ. fecha pago")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</div>
	`);
}

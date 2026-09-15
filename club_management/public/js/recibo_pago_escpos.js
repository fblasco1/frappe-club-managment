/** Impresión de recibo térmico ESC/POS tras cobro manual. */
frappe.provide("club_management_recibo_pago");

club_management_recibo_pago._ancho_mm_css = function (ancho_mm) {
	return ancho_mm === 80 ? "80mm" : "58mm";
};

club_management_recibo_pago._get_print_frame = function () {
	let frame = document.getElementById("club-recibo-print-frame");
	if (!frame) {
		frame = document.createElement("iframe");
		frame.id = "club-recibo-print-frame";
		frame.setAttribute("title", __("Recibo de pago"));
		frame.style.cssText =
			"position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;";
		document.body.appendChild(frame);
	}
	return frame;
};

club_management_recibo_pago.imprimir_html = function (recibo) {
	const ancho = club_management_recibo_pago._ancho_mm_css(recibo.ancho_papel_mm);
	const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${__(
		"Recibo"
	)}</title><style>
@page { size: ${ancho} auto; margin: 2mm; }
body { font-family: "Courier New", Courier, monospace; font-size: 11px; width: ${ancho}; margin: 0 auto; white-space: pre-wrap; }
</style></head><body>${frappe.utils.escape_html(recibo.texto || "")}</body></html>`;
	const frame = club_management_recibo_pago._get_print_frame();
	const win = frame.contentWindow;
	if (!win) {
		frappe.msgprint(__("No se pudo abrir la vista previa del recibo."));
		return;
	}
	win.document.open();
	win.document.write(html);
	win.document.close();
	win.focus();
	// iframe evita el bloqueo de popups tras frappe.call (callback asíncrono).
	setTimeout(() => {
		try {
			win.print();
		} catch (err) {
			frappe.msgprint(__("No se pudo iniciar la impresión del recibo."));
		}
	}, 250);
};

club_management_recibo_pago.imprimir_escpos_webprnt = function (recibo) {
	const url = (recibo.impresora_url || "").trim();
	if (!url || !recibo.escpos_base64) {
		return Promise.resolve(false);
	}
	const body = `<?xml version="1.0" encoding="utf-8"?>
<StarWebPrintData>
  <rawdata>${recibo.escpos_base64}</rawdata>
</StarWebPrintData>`;
	return fetch(url, {
		method: "POST",
		headers: { "Content-Type": "text/xml; charset=utf-8" },
		body,
		mode: "cors",
	})
		.then((res) => res.ok)
		.catch(() => false);
};

club_management_recibo_pago.imprimir = function (recibo) {
	if (!recibo) return;
	const url = (recibo.impresora_url || "").trim();
	if (url) {
		club_management_recibo_pago.imprimir_escpos_webprnt(recibo).then((ok) => {
			if (ok) {
				frappe.show_alert({ message: __("Recibo enviado a la impresora"), indicator: "green" });
			} else {
				frappe.show_alert({
					message: __("Impresora Star no disponible; abriendo vista previa"),
					indicator: "orange",
				});
				club_management_recibo_pago.imprimir_html(recibo);
			}
		});
		return;
	}
	club_management_recibo_pago.imprimir_html(recibo);
};

club_management_recibo_pago.imprimir_despues_cobro = function (recibo) {
	if (!recibo) {
		frappe.show_alert({ message: __("Cobro sin datos de recibo"), indicator: "orange" });
		return;
	}
	club_management_recibo_pago.imprimir(recibo);
};

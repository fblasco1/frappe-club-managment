"""Sincroniza cuotas sociales en Club Settings con el ítem de suscripción único."""



from __future__ import annotations



import frappe

from frappe.utils import flt



from club_management.members.data.cuotas_sociales_vigentes import (

	CUOTA_SOCIAL_ITEM_CODE,

	CUOTAS_SOCIALES_VIGENTES,

)

from club_management.setup.suscripciones_cobro_mensual import setup_cuota_social_item_and_plan





def _resolve_reference_rate(settings) -> float:

	"""Tarifa referencia del ítem: monto de categoría Activo en Club Settings."""

	by_categoria = {row.categoria: row for row in (settings.cuotas_categoria or [])}

	activo = by_categoria.get("Activo")

	if activo and flt(activo.monto) > 0:

		return flt(activo.monto)

	for categoria, monto in CUOTAS_SOCIALES_VIGENTES:

		if categoria == "Activo":

			return flt(monto)

	return 0.0





def sync_cuotas_sociales_erpnext(*, reference_rate: float | None = None) -> dict[str, float | str]:

	"""

	Alinea Item, Item Price y vínculos de Club Settings con los montos guardados.



	El plan usa `Based On Price List`; el monto real por socio se resuelve al facturar.

	"""

	settings = frappe.get_single("Club Settings")

	rate = flt(reference_rate) if reference_rate is not None else _resolve_reference_rate(settings)

	if rate <= 0:

		frappe.throw(frappe._("No hay monto de referencia para la cuota social (categoría Activo)."))



	setup = setup_cuota_social_item_and_plan(reference_rate=rate)

	item_code = setup.get("item") or CUOTA_SOCIAL_ITEM_CODE



	settings.item_cuota_social = item_code

	for row in settings.cuotas_categoria or []:

		row.item = item_code

	settings.save(ignore_permissions=True)



	return {

		"item": item_code,

		"plan": setup.get("plan", ""),

		"reference_rate": rate,

	}





def sync_cuotas_sociales_club(*, update_montos_from_vigentes: bool = False) -> dict[str, int | float | str]:

	"""

	Asegura ítem/plan de cuota social y actualiza montos por categoría en Club Settings.



	Cada fila de `cuotas_categoria` apunta al mismo ítem (`CLUB-Cuota-Social-Base`);

	el monto distingue la categoría del socio en cobranza/suscripción.



	Con `update_montos_from_vigentes=True` (bootstrap/patches) sobrescribe montos desde

	`CUOTAS_SOCIALES_VIGENTES`. Tras guardar desde Secretaría, usar `False` para

	preservar los montos editados.

	"""

	if not frappe.db.exists("DocType", "Club Settings"):

		return {"updated": 0, "item": CUOTA_SOCIAL_ITEM_CODE}



	settings = frappe.get_single("Club Settings")

	if not settings.company:

		company = frappe.db.get_value("Company", {}, "name")

		if company:

			settings.company = company



	by_categoria = {row.categoria: row for row in (settings.cuotas_categoria or [])}

	updated = 0



	for categoria, monto in CUOTAS_SOCIALES_VIGENTES:

		row = by_categoria.get(categoria)

		if row:

			if update_montos_from_vigentes and flt(row.monto) != flt(monto):

				row.monto = monto

				updated += 1

			if not row.item:

				row.item = CUOTA_SOCIAL_ITEM_CODE

				updated += 1

		else:

			settings.append(

				"cuotas_categoria",

				{"categoria": categoria, "monto": monto, "item": CUOTA_SOCIAL_ITEM_CODE},

			)

			updated += 1



	if updated:

		settings.save(ignore_permissions=True)



	result = sync_cuotas_sociales_erpnext()

	result["updated"] = updated

	return result



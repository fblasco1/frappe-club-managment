"""Informe «Deuda de socios»: cuota social + arancel por socio o por actividad (spec deuda_socios.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from club_management.activities.data.basquet_aranceles_icdpe import expand_arancel_item_codes_for_pagos
from club_management.activities.services.inscripcion_socio import INSCRIPCION_DOCTYPE
from club_management.members.doctype.socio.socio import format_socio_nombre_completo
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	erpnext_cobranza_disponible,
)
from club_management.members.services.liquidacion_equipo import _cuota_social_item_codes, _fmt_socios_deudores
from club_management.members.services.mora_al_cobro import parse_periodo_cobro
from club_management.scripts.informe_concepto_cobranza import _cobros_imputados_por_linea

VISTA_ARBOL = "Por actividad"
VISTA_LISTA = "Lista de socios"
CONCEPTO_TODO = "Todo"
CONCEPTO_CUOTA = "Solo cuota social"
CONCEPTO_ARANCEL = "Solo arancel"
ESTADO_BAJA = "Baja"
_TOLERANCIA = 0.005

InsKey = tuple[str, str, str]


@dataclass
class _Socio:
	name: str
	nombre: str
	categoria: str
	estado: str
	telefono: str
	inscripciones: list[dict[str, Any]] = field(default_factory=list)
	cuota: float = 0.0
	arancel_por_ins: list[float] = field(default_factory=list)
	periodos: set[str] = field(default_factory=set)

	@property
	def arancel(self) -> float:
		return flt(sum(self.arancel_por_ins), 2)

	@property
	def total(self) -> float:
		return flt(self.cuota + self.arancel, 2)

	@property
	def actividades(self) -> list[str]:
		return list(dict.fromkeys(str(ins.actividad or "") for ins in self.inscripciones))


# --- filtros -----------------------------------------------------------------


def _filtro_periodo(filters: dict[str, Any], key: str) -> date | None:
	raw = (filters.get(key) or "").strip()
	if not raw:
		return None
	parsed = parse_periodo_cobro(raw)
	if not parsed:
		frappe.throw(_("Período inválido «{0}»: usá el formato MM/AAAA.").format(raw), frappe.ValidationError)
	return parsed


def _normalizar(filters: dict[str, Any] | None) -> frappe._dict:
	f = frappe._dict(filters or {})
	f.vista = f.get("vista") or VISTA_ARBOL
	f.concepto = f.get("concepto") or CONCEPTO_TODO
	if f.vista not in (VISTA_ARBOL, VISTA_LISTA):
		frappe.throw(_("Vista inválida «{0}».").format(f.vista), frappe.ValidationError)
	if f.concepto not in (CONCEPTO_TODO, CONCEPTO_CUOTA, CONCEPTO_ARANCEL):
		frappe.throw(_("Concepto inválido «{0}».").format(f.concepto), frappe.ValidationError)
	f.desde = _filtro_periodo(f, "periodo_desde")
	f.hasta = _filtro_periodo(f, "periodo_hasta")
	if f.desde and f.hasta and f.hasta < f.desde:
		frappe.throw(_("El período hasta debe ser posterior o igual al período desde."), frappe.ValidationError)
	return f


def _filtro_ubicacion(f: frappe._dict) -> bool:
	return bool(f.get("actividad") or f.get("grupo_actividad") or f.get("equipo_actividad"))


def _ins_coincide(ins: dict[str, Any], f: frappe._dict) -> bool:
	return (
		(not f.get("actividad") or ins.actividad == f.actividad)
		and (not f.get("grupo_actividad") or ins.grupo_actividad == f.grupo_actividad)
		and (not f.get("equipo_actividad") or ins.equipo_actividad == f.equipo_actividad)
	)


# --- datos base ----------------------------------------------------------------


def _socios_filtrados(f: frappe._dict) -> dict[str, _Socio]:
	socio_filters: dict[str, Any] = {}
	if f.get("categoria"):
		socio_filters["categoria"] = f.categoria
	socio_filters["estado"] = f.estado if f.get("estado") else ["!=", ESTADO_BAJA]
	if f.get("socio"):
		socio_filters["name"] = f.socio
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters=socio_filters,
		fields=["name", "nombre", "apellido", "categoria", "estado", "telefono_movil"],
	)
	return {
		row.name: _Socio(
			name=row.name,
			nombre=format_socio_nombre_completo(row.apellido, row.nombre) or row.name,
			categoria=row.categoria or "",
			estado=row.estado or "",
			telefono=row.telefono_movil or "",
		)
		for row in rows
	}


def _asignar_inscripciones(socios: dict[str, _Socio], f: frappe._dict) -> None:
	"""Inscripciones activas; los socios en Baja usan las dadas de baja si no tienen activas."""
	estados = ["Activa", ESTADO_BAJA] if f.get("estado") == ESTADO_BAJA else ["Activa"]
	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"estado": ["in", estados]},
		fields=["name", "socio", "actividad", "grupo_actividad", "equipo_actividad", "estado"],
		order_by="creation asc, name asc",
	)
	activas: dict[str, list[dict[str, Any]]] = {}
	bajas: dict[str, list[dict[str, Any]]] = {}
	for ins in rows:
		if ins.socio not in socios:
			continue
		(activas if ins.estado == "Activa" else bajas).setdefault(ins.socio, []).append(ins)
	for name, socio in socios.items():
		socio.inscripciones = activas.get(name) or (bajas.get(name, []) if socio.estado == ESTADO_BAJA else [])


class _ArancelCodes:
	"""Ítems de arancel por (actividad, grupo, equipo): equipo → grupo → actividad, con alias."""

	def __init__(self) -> None:
		self._items = {
			doctype: dict(frappe.get_all(doctype, fields=["name", "item"], as_list=True))
			for doctype in ("Actividad", "Grupo Actividad", "Equipo Actividad")
		}
		self._cache: dict[InsKey, set[str]] = {}

	def para(self, key: InsKey) -> set[str]:
		if key not in self._cache:
			actividad, grupo, equipo = key
			item = (
				(equipo and self._items["Equipo Actividad"].get(equipo))
				or (grupo and self._items["Grupo Actividad"].get(grupo))
				or self._items["Actividad"].get(actividad)
			)
			self._cache[key] = set(expand_arancel_item_codes_for_pagos(item)) if item else set()
		return self._cache[key]

	def todos(self) -> set[str]:
		out: set[str] = set()
		for items in self._items.values():
			for item in items.values():
				if item:
					out |= expand_arancel_item_codes_for_pagos(item)
		return out


def _ins_key(ins: dict[str, Any]) -> InsKey:
	return (str(ins.actividad or ""), str(ins.grupo_actividad or ""), str(ins.equipo_actividad or ""))


def _lineas_impagas(socios: dict[str, _Socio], codes: set[str], f: frappe._dict) -> list[dict[str, Any]]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not socios or not codes or not campo_socio:
		return []
	periodo_sql = f"si.{campo_periodo}" if campo_periodo else "''"
	params: dict[str, Any] = {"codes": tuple(sorted(codes))}
	socio_cond = ""
	if f.get("socio"):
		socio_cond = f"and si.{campo_socio} = %(socio)s"
		params["socio"] = f.socio
	rows = frappe.db.sql(
		f"""
		select si.name as invoice, {periodo_sql} as periodo, si.grand_total, si.outstanding_amount,
			si.{campo_socio} as socio, sii.item_code, sii.amount
		from "tab{SALES_INVOICE_DOCTYPE} Item" sii
		join "tab{SALES_INVOICE_DOCTYPE}" si on si.name = sii.parent
		where si.docstatus = 1 and si.is_return = 0 and si.outstanding_amount > 0
			and sii.item_code in %(codes)s {socio_cond}
		order by si.name, sii.idx
		""",
		params,
		as_dict=True,
	)
	out = []
	for row in rows:
		if row.socio not in socios:
			continue
		if f.desde or f.hasta:
			periodo = parse_periodo_cobro(row.periodo)
			if not periodo or (f.desde and periodo < f.desde) or (f.hasta and periodo > f.hasta):
				continue
		out.append(row)
	return out


def _saldos_por_linea(lineas: list[dict[str, Any]], codes: set[str]) -> list[tuple[str, str, str, float]]:
	"""(socio, periodo, item_code, saldo); con cobros parciales imputa por línea."""
	out: list[tuple[str, str, str, float]] = []
	parciales: dict[str, dict[str, Any]] = {}
	for row in lineas:
		if flt(row.outstanding_amount) + _TOLERANCIA < flt(row.grand_total):
			parciales.setdefault(row.invoice, row)
			continue
		out.append((row.socio, row.periodo or "", row.item_code, flt(row.amount)))
	for invoice, row in parciales.items():
		for imputada in _cobros_imputados_por_linea(invoice):
			code = imputada.get("item_code") or ""
			if code in codes:
				out.append((row.socio, row.periodo or "", code, flt(imputada.get("restante"))))
	return out


def _calcular_deuda(socios: dict[str, _Socio], f: frappe._dict, aranceles: _ArancelCodes) -> None:
	cuota_codes = _cuota_social_item_codes()
	codes = cuota_codes | aranceles.todos()
	ubicacion = _filtro_ubicacion(f)
	incluye_cuota = f.concepto in (CONCEPTO_TODO, CONCEPTO_CUOTA)
	incluye_arancel = f.concepto in (CONCEPTO_TODO, CONCEPTO_ARANCEL)

	codes_por_socio: dict[str, list[set[str]]] = {}
	for name, socio in socios.items():
		usados = set(cuota_codes)
		por_ins: list[set[str]] = []
		for ins in socio.inscripciones:
			ins_codes = aranceles.para(_ins_key(ins)) - usados
			usados |= ins_codes
			por_ins.append(ins_codes if (not ubicacion or _ins_coincide(ins, f)) else set())
		codes_por_socio[name] = por_ins
		socio.arancel_por_ins = [0.0] * len(por_ins)

	for socio_name, periodo, code, saldo in _saldos_por_linea(_lineas_impagas(socios, codes, f), codes):
		if saldo <= _TOLERANCIA:
			continue
		socio = socios[socio_name]
		if code in cuota_codes:
			if incluye_cuota:
				socio.cuota = flt(socio.cuota + saldo, 2)
				socio.periodos.add(periodo)
			continue
		if not incluye_arancel:
			continue
		for idx, ins_codes in enumerate(codes_por_socio[socio_name]):
			if code in ins_codes:
				socio.arancel_por_ins[idx] = flt(socio.arancel_por_ins[idx] + saldo, 2)
				socio.periodos.add(periodo)
				break


def _socios_en_alcance(socios: dict[str, _Socio], f: frappe._dict) -> dict[str, _Socio]:
	if not _filtro_ubicacion(f):
		return socios
	return {
		name: socio
		for name, socio in socios.items()
		if any(_ins_coincide(ins, f) for ins in socio.inscripciones)
	}


def _titulos(doctype: str, names: set[str]) -> dict[str, str]:
	names = {n for n in names if n}
	if not names:
		return {}
	rows = frappe.get_all(doctype, filters={"name": ["in", list(names)]}, fields=["name", "titulo"])
	return {row.name: str(row.titulo or row.name) for row in rows}


def _fmt_periodos(periodos: set[str]) -> str:
	ordenados = sorted(periodos, key=lambda p: parse_periodo_cobro(p) or date.min)
	return ", ".join(p or _("(sin período)") for p in ordenados)


# --- columnas ----------------------------------------------------------------


def _columnas_monto(concepto: str) -> list[dict[str, Any]]:
	cuota = {"label": _("Cuota social"), "fieldname": "deuda_cuota_social", "fieldtype": "Currency", "width": 130}
	arancel = {"label": _("Arancel"), "fieldname": "deuda_arancel", "fieldtype": "Currency", "width": 130}
	total = {"label": _("Total"), "fieldname": "deuda_total", "fieldtype": "Currency", "width": 130}
	if concepto == CONCEPTO_CUOTA:
		return [cuota]
	if concepto == CONCEPTO_ARANCEL:
		return [arancel]
	return [cuota, arancel, total]


def get_columns(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	f = frappe._dict(filters or {})
	concepto = f.get("concepto") or CONCEPTO_TODO
	periodos = {"label": _("Períodos adeudados"), "fieldname": "periodos", "fieldtype": "Data", "width": 200}
	estado = {"label": _("Estado"), "fieldname": "estado", "fieldtype": "Data", "width": 90}
	telefono = {"label": _("Teléfono"), "fieldname": "telefono", "fieldtype": "Data", "width": 120}
	actividades = {"label": _("Actividades"), "fieldname": "actividades", "fieldtype": "Data", "width": 170}
	if (f.get("vista") or VISTA_ARBOL) == VISTA_LISTA:
		return [
			{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 100},
			{"label": _("Apellido y nombre"), "fieldname": "nombre", "fieldtype": "Data", "width": 220},
			{"label": _("Categoría"), "fieldname": "categoria", "fieldtype": "Data", "width": 110},
			estado,
			telefono,
			actividades,
			periodos,
			{"label": _("Cant."), "fieldname": "cantidad_periodos", "fieldtype": "Int", "width": 60},
			*_columnas_monto(concepto),
		]
	return [
		{"label": _("Nivel"), "fieldname": "nivel", "fieldtype": "Data", "width": 300},
		{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 100},
		estado,
		telefono,
		actividades,
		periodos,
		*_columnas_monto(concepto),
		{"label": _("Socios deudores"), "fieldname": "socios_deudores", "fieldtype": "Data", "width": 120},
		{"label": _("indent"), "fieldname": "indent", "fieldtype": "Int", "width": 0, "hidden": 1},
	]


# --- vistas ------------------------------------------------------------------


def _montos(cuota: float, arancel: float) -> dict[str, float]:
	return {
		"deuda_cuota_social": flt(cuota, 2),
		"deuda_arancel": flt(arancel, 2),
		"deuda_total": flt(cuota + arancel, 2),
	}


def _lista(deudores: list[_Socio], titulos_act: dict[str, str]) -> list[dict[str, Any]]:
	data = [
		{
			"socio": s.name,
			"nombre": s.nombre,
			"categoria": s.categoria,
			"estado": s.estado,
			"telefono": s.telefono,
			"actividades": ", ".join(titulos_act.get(a, a) for a in s.actividades if a),
			"periodos": _fmt_periodos(s.periodos),
			"cantidad_periodos": len(s.periodos),
			**_montos(s.cuota, s.arancel),
		}
		for s in deudores
	]
	data.sort(key=lambda r: (-r["cantidad_periodos"], -r["deuda_total"], (r["nombre"] or "").lower()))
	return data


def _fila_arbol(nivel: str, indent: int, cuota: float, arancel: float, socios_deudores: str = "", **extra: Any) -> dict[str, Any]:
	return {
		"nivel": nivel,
		"indent": indent,
		"socio": "",
		"estado": "",
		"telefono": "",
		"actividades": "",
		"periodos": "",
		"actividad": "",
		"grupo_actividad": "",
		"equipo_actividad": "",
		**_montos(cuota, arancel),
		"socios_deudores": socios_deudores,
		**extra,
	}


def _fila_socio(s: _Socio, indent: int, cuota: float, arancel: float, **extra: Any) -> dict[str, Any]:
	return _fila_arbol(
		s.nombre,
		indent,
		cuota,
		arancel,
		"1",
		socio=s.name,
		estado=s.estado,
		telefono=s.telefono,
		periodos=_fmt_periodos(s.periodos),
		**extra,
	)


def _arbol(
	alcance: dict[str, _Socio],
	f: frappe._dict,
	titulos_act: dict[str, str],
) -> list[dict[str, Any]]:
	ubicacion = _filtro_ubicacion(f)
	universo: dict[InsKey, set[str]] = {}
	buckets: dict[InsKey, dict[str, tuple[float, float]]] = {}
	multi_padron: set[str] = set()
	multi: list[_Socio] = []
	sin_padron: set[str] = set()
	sin_actividad: list[_Socio] = []

	for s in alcance.values():
		if not s.inscripciones:
			if not ubicacion:
				sin_padron.add(s.name)
				if s.total > _TOLERANCIA:
					sin_actividad.append(s)
			continue
		if len(s.actividades) > 1:
			multi_padron.add(s.name)
			if s.total > _TOLERANCIA:
				multi.append(s)
			continue
		cuota_pendiente = s.cuota
		for idx, ins in enumerate(s.inscripciones):
			if ubicacion and not _ins_coincide(ins, f):
				continue
			key = _ins_key(ins)
			universo.setdefault(key, set()).add(s.name)
			cuota, cuota_pendiente = cuota_pendiente, 0.0
			arancel = s.arancel_por_ins[idx]
			if cuota + arancel <= _TOLERANCIA:
				continue
			prev = buckets.setdefault(key, {}).get(s.name, (0.0, 0.0))
			buckets[key][s.name] = (prev[0] + cuota, prev[1] + arancel)

	if not buckets and not multi and not sin_actividad:
		return []

	titulos_grupo = _titulos("Grupo Actividad", {k[1] for k in buckets})
	titulos_equipo = _titulos("Equipo Actividad", {k[2] for k in buckets})

	def _padron(*parts: str) -> int:
		n = len(parts)
		return len(set().union(*[socios for key, socios in universo.items() if key[:n] == parts] or [set()]))

	def _sumar(montos: list[dict[str, tuple[float, float]]]) -> tuple[dict[str, tuple[float, float]], float, float]:
		unidos: dict[str, tuple[float, float]] = {}
		for socios in montos:
			for name, (c, a) in socios.items():
				prev = unidos.get(name, (0.0, 0.0))
				unidos[name] = (prev[0] + c, prev[1] + a)
		return unidos, sum(c for c, _a in unidos.values()), sum(a for _c, a in unidos.values())

	def _orden(names: Any) -> list[str]:
		return sorted(names, key=lambda n: alcance[n].nombre.lower())

	tree: dict[str, dict[str, dict[str, dict[str, tuple[float, float]]]]] = {}
	for (act, grupo, equipo), socios in buckets.items():
		tree.setdefault(act, {}).setdefault(grupo, {})[equipo] = socios

	body: list[dict[str, Any]] = []
	for act in sorted(tree, key=lambda a: titulos_act.get(a, a).lower()):
		socios_act, cuota, arancel = _sumar([s for g in tree[act].values() for s in g.values()])
		body.append(
			_fila_arbol(
				_("Subtotal {0}").format(titulos_act.get(act, act)),
				1,
				cuota,
				arancel,
				_fmt_socios_deudores(len(socios_act), _padron(act)),
				actividad=act,
			)
		)
		for grupo in sorted(tree[act], key=lambda g: titulos_grupo.get(g, g).lower()):
			socios_grupo, cuota, arancel = _sumar(list(tree[act][grupo].values()))
			label = titulos_grupo.get(grupo, grupo) if grupo else _("Sin grupo / tira")
			body.append(
				_fila_arbol(
					_("Subtotal {0}").format(label),
					2,
					cuota,
					arancel,
					_fmt_socios_deudores(len(socios_grupo), _padron(act, grupo)),
					actividad=act,
					grupo_actividad=grupo,
				)
			)
			for equipo in sorted(tree[act][grupo], key=lambda e: titulos_equipo.get(e, e).lower()):
				socios = tree[act][grupo][equipo]
				socio_indent = 3
				if equipo:
					_u, cuota, arancel = _sumar([socios])
					body.append(
						_fila_arbol(
							titulos_equipo.get(equipo, equipo),
							3,
							cuota,
							arancel,
							_fmt_socios_deudores(len(socios), _padron(act, grupo, equipo)),
							actividad=act,
							grupo_actividad=grupo,
							equipo_actividad=equipo,
						)
					)
					socio_indent = 4
				for name in _orden(socios):
					c, a = socios[name]
					body.append(
						_fila_socio(
							alcance[name],
							socio_indent,
							c,
							a,
							actividad=act,
							grupo_actividad=grupo,
							equipo_actividad=equipo,
						)
					)

	for etiqueta, deudores, padron in (
		(_("Multiactividad"), multi, len(multi_padron)),
		(_("Sin actividad"), sin_actividad, len(sin_padron)),
	):
		if not deudores:
			continue
		cuota = sum(s.cuota for s in deudores)
		arancel = sum(s.arancel for s in deudores)
		body.append(_fila_arbol(etiqueta, 1, cuota, arancel, _fmt_socios_deudores(len(deudores), padron)))
		for s in sorted(deudores, key=lambda s: s.nombre.lower()):
			body.append(
				_fila_socio(
					s,
					2,
					s.cuota,
					s.arancel,
					actividades=", ".join(titulos_act.get(a, a) for a in s.actividades if a),
				)
			)

	todos, cuota, arancel = _sumar([*buckets.values()])
	for s in (*multi, *sin_actividad):
		todos[s.name] = (s.cuota, s.arancel)
		cuota += s.cuota
		arancel += s.arancel
	padron_total = len(set().union(*universo.values(), multi_padron, sin_padron))
	total = _fila_arbol(_("Total"), 0, cuota, arancel, _fmt_socios_deudores(len(todos), padron_total))
	return [total, *body]


def get_report_summary(deudores: list[_Socio], concepto: str) -> list[dict[str, Any]]:
	cuota = flt(sum(s.cuota for s in deudores), 2)
	arancel = flt(sum(s.arancel for s in deudores), 2)
	summary: list[dict[str, Any]] = [
		{"label": _("Socios con deuda"), "value": len(deudores), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Períodos adeudados"),
			"value": sum(len(s.periodos) for s in deudores),
			"datatype": "Int",
			"indicator": "Orange",
		},
	]
	if concepto == CONCEPTO_TODO:
		summary += [
			{"label": _("Cuota social"), "value": cuota, "datatype": "Currency", "indicator": "Orange"},
			{"label": _("Arancel"), "value": arancel, "datatype": "Currency", "indicator": "Orange"},
		]
	summary.append(
		{"label": _("Total adeudado"), "value": flt(cuota + arancel, 2), "datatype": "Currency", "indicator": "Red"}
	)
	return summary


def get_deuda_socios(
	filters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], None, None, list[dict[str, Any]]]:
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de deuda requiere ERPNext (Sales Invoice)."), frappe.ValidationError)
	f = _normalizar(filters)
	socios = _socios_filtrados(f)
	_asignar_inscripciones(socios, f)
	_calcular_deuda(socios, f, _ArancelCodes())
	alcance = _socios_en_alcance(socios, f)
	deudores = [s for s in alcance.values() if s.total > _TOLERANCIA]

	titulos_act = _titulos("Actividad", {a for s in alcance.values() for a in s.actividades})
	if f.vista == VISTA_LISTA:
		data = _lista(deudores, titulos_act)
	else:
		data = _arbol(alcance, f, titulos_act)
	return get_columns(f), data, None, None, get_report_summary(deudores, f.concepto)

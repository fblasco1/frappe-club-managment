"""Importa el listado del Gimnasio de Musculación 2026 (spec import_gimnasio_2026.md).

Uso:

    bench --site dev.localhost execute \\
        club_management.members.ops.import_gimnasio_2026.run \\
        --kwargs '{"csv_path": "/workspace/development/frappe-bench/sites/gimnasio_2026.csv"}'

    bench --site dev.localhost execute \\
        club_management.members.ops.import_gimnasio_2026.run \\
        --kwargs '{"csv_path": "...", "apply": true, "confirm": "local-dev", "confirmados": {"NOMBRE CSV": "1234"}}'
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import unicodedata
from collections import Counter
from datetime import date
from typing import Any

import frappe

from club_management.members.doctype.socio.socio import CATEGORIA_NO_SOCIO
from club_management.members.services.practicante_no_socio import (
	ACTIVIDAD_GIMNASIO,
	CONDICION_SOCIO,
	crear_practicante_no_socio,
	grupo_gimnasio_por_condicion,
)
from club_management.members.setup.import_socios_padron import (
	MIGRATION_DNI_DORSO,
	MIGRATION_DNI_FRENTE,
	MIGRATION_FICHA_MEDICA,
	MIGRATION_FOTO_PERFIL,
)
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed

DEFAULT_CSV = "/workspace/development/frappe-bench/sites/gimnasio_2026.csv"
DNI_PROVISORIO_PREFIX = "GYM-PEND-"
SIMILITUD_MISMA_PERSONA = 0.85
SIMILITUD_PROBABLE = 0.8
MOTIVO = "Import listado Gimnasio de Musculación 2026"
_PRIORIDAD_MEMBRESIA = {"MES": 0, "QUINCENA": 1, "HORA": 2}
_PARTICULAS_APELLIDO = frozenset({"DE", "DEL", "DELLA", "DI", "DA", "LA", "LOS", "VAN", "VON"})


def normalizar_nombre(valor: str) -> str:
	texto = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode().upper()
	return " ".join(re.sub(r"[^A-Z ]", " ", texto).split())


def _clave_ordenada(nombre_norm: str) -> str:
	return " ".join(sorted(nombre_norm.split()))


def _misma_persona(a: str, b: str) -> bool:
	ratio = difflib.SequenceMatcher(None, _clave_ordenada(a), _clave_ordenada(b)).ratio()
	return ratio >= SIMILITUD_MISMA_PERSONA


def agrupar_no_socios(filas: list[tuple[str, str]]) -> list[dict[str, Any]]:
	"""Agrupa `(nombre, membresia)` de la misma persona; la membresía mensual tiene prioridad."""
	grupos: list[dict[str, Any]] = []
	for original, membresia in filas:
		norm = normalizar_nombre(original)
		membresia = (membresia or "").strip().upper()
		grupo = next((g for g in grupos if any(_misma_persona(norm, v) for v in g["variantes"])), None)
		if grupo is None:
			grupo = {"nombre": original.strip(), "variantes": [], "originales": [], "membresia": membresia}
			grupos.append(grupo)
		if norm not in grupo["variantes"]:
			grupo["variantes"].append(norm)
		grupo["originales"].append(original.strip())
		if _PRIORIDAD_MEMBRESIA.get(membresia, 9) < _PRIORIDAD_MEMBRESIA.get(grupo["membresia"], 9):
			grupo["membresia"] = membresia
			grupo["nombre"] = original.strip()
	return grupos


class _Padron:
	"""Índices de nombres del padrón para identificar personas del CSV."""

	def __init__(self) -> None:
		filas = frappe.get_all(
			"Socio", fields=["name", "nombre", "apellido", "categoria", "estado", "dni"]
		)
		self.socios: dict[str, list[dict[str, Any]]] = {}
		self.no_socios: dict[str, str] = {}
		self.freq_nombre: Counter[str] = Counter()
		self.freq_apellido: Counter[str] = Counter()
		for row in filas:
			nombre = normalizar_nombre(row.nombre)
			apellido = normalizar_nombre(row.apellido)
			self.freq_nombre.update(nombre.split())
			self.freq_apellido.update(apellido.split())
			claves = {f"{nombre} {apellido}".strip(), f"{apellido} {nombre}".strip()}
			if row.categoria == CATEGORIA_NO_SOCIO:
				for clave in claves:
					self.no_socios[_clave_ordenada(clave)] = row.name
				continue
			for clave in claves:
				self.socios.setdefault(clave, [])
				if row not in self.socios[clave]:
					self.socios[clave].append(row)
		self._claves_socios = list(self.socios)

	def exacto(self, nombre_norm: str) -> list[dict[str, Any]]:
		return self.socios.get(nombre_norm, [])

	def candidatos(self, nombre_norm: str) -> list[dict[str, Any]]:
		tokens = nombre_norm.split()
		invertido = " ".join(tokens[1:] + tokens[:1])
		vistos: dict[str, dict[str, Any]] = {}
		for clave in (nombre_norm, invertido):
			for match in difflib.get_close_matches(clave, self._claves_socios, n=3, cutoff=SIMILITUD_PROBABLE):
				for row in self.socios[match]:
					vistos.setdefault(row.name, row)
		return list(vistos.values())

	def no_socio_existente(self, variantes: list[str]) -> str | None:
		for variante in variantes:
			found = self.no_socios.get(_clave_ordenada(variante))
			if found:
				return found
		return None

	def separar_nombre(self, original: str) -> tuple[str, str]:
		"""Devuelve `(nombre, apellido)` a partir de «NOMBRE APELLIDO» (o invertido)."""
		palabras = original.strip().split()
		norm = [normalizar_nombre(p) for p in palabras]

		def parece_apellido(token: str) -> bool:
			return self.freq_apellido[token] > self.freq_nombre[token]

		def parece_nombre(token: str) -> bool:
			return self.freq_nombre[token] > self.freq_apellido[token]

		if len(palabras) == 2 and parece_nombre(norm[1]) and not parece_nombre(norm[0]):
			return palabras[1].title(), palabras[0].title()
		corte = len(palabras) - 1
		while corte > 1 and (parece_apellido(norm[corte - 1]) or norm[corte - 1] in _PARTICULAS_APELLIDO):
			corte -= 1
		return " ".join(palabras[:corte]).title(), " ".join(palabras[corte:]).title()


def _leer_csv(path: str) -> list[dict[str, Any]]:
	with open(path, encoding="utf-8-sig", newline="") as fh:
		reader = csv.DictReader(fh)
		filas = []
		for numero, row in enumerate(reader, start=2):
			lookup = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
			filas.append(
				{
					"linea": numero,
					"nombre": lookup.get("nombre y apellido", ""),
					"profesor": lookup.get("profesor / turno", ""),
					"condicion": normalizar_nombre(lookup.get("condición") or lookup.get("condicion") or ""),
					"membresia": (lookup.get("tipo de membresía") or lookup.get("tipo de membresia") or "").upper(),
				}
			)
	return [f for f in filas if f["nombre"]]


def _actividad_gimnasio() -> str:
	return frappe.db.get_value("Actividad", {"titulo": ACTIVIDAD_GIMNASIO}, "name") or ACTIVIDAD_GIMNASIO


def _tiene_inscripcion_gym(socio: str) -> bool:
	return bool(
		frappe.db.exists(
			"Inscripcion Actividad",
			{"socio": socio, "actividad": _actividad_gimnasio(), "estado": "Activa"},
		)
	)


def _siguiente_dni_provisorio() -> int:
	existentes = frappe.get_all(
		"Socio", filters={"dni": ["like", f"{DNI_PROVISORIO_PREFIX}%"]}, pluck="dni"
	)
	numeros = [int(d[len(DNI_PROVISORIO_PREFIX) :]) for d in existentes if d[len(DNI_PROVISORIO_PREFIX) :].isdigit()]
	return max(numeros, default=0) + 1


def _payload_no_socio(nombre: str, apellido: str, dni: str) -> dict[str, Any]:
	slug = dni.lower()
	return {
		"nombre": nombre,
		"apellido": apellido,
		"dni": dni,
		"nacionalidad": "Argentina",
		"fecha_nacimiento": date(2000, 1, 1),
		"genero": "Prefiero no decir",
		"email": f"gimnasio.{slug}@local.invalid",
		"telefono_movil": "1100000000",
		"calle": "Sin domicilio",
		"provincia": "CABA",
		"ciudad": "CABA",
		"localidad_barrio": "CABA",
		"codigo_postal": "0000",
		"foto_perfil": MIGRATION_FOTO_PERFIL,
		"dni_frente": MIGRATION_DNI_FRENTE,
		"dni_dorso": MIGRATION_DNI_DORSO,
		"ficha_medica": MIGRATION_FICHA_MEDICA,
	}


def _resumen_socio(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"socio": row.name,
		"nombre": f"{row.nombre} {row.apellido}",
		"categoria": row.categoria,
		"estado": row.estado,
	}


_PENDIENTE_NO_ENCONTRADO = (
	"Buscar por DNI. Si es socio, inscribirlo en Gimnasio / Socio; si no lo es, "
	"darlo de alta como practicante No Socio (arancel No Socio)."
)
_PENDIENTE_DATOS_NO_SOCIO = (
	"Completar DNI real, fecha de nacimiento, email, teléfono y domicilio "
	"(hoy tiene datos provisorios)."
)


def _situacion(situacion: str, *, socio: str = "", dni: str = "", detalle: str = "", pendiente: str = "") -> dict[str, Any]:
	return {"situacion": situacion, "socio": socio, "dni": dni, "detalle": detalle, "pendiente": pendiente}


def _candidatos_texto(rows: list[dict[str, Any]]) -> str:
	return "; ".join(f"#{r.name} {r.nombre} {r.apellido} ({r.categoria}, {r.estado})" for r in rows)


def _planear_no_socio(
	grupo: dict[str, Any],
	padron: _Padron,
	report: dict[str, Any],
	socios_a_inscribir: dict[str, dict[str, Any]],
	planear_socio: Any,
) -> dict[str, Any]:
	existente_socio = next((padron.exacto(v) for v in grupo["variantes"] if len(padron.exacto(v)) == 1), None)
	if existente_socio:
		row = existente_socio[0]
		if row.estado == "Baja" or row.categoria == "Menor":
			report["revisar"].append(
				{"csv": grupo["nombre"], "motivo": "Figura No socio y coincide con socio en Baja/Menor", **_resumen_socio(row)}
			)
			motivo = "en Baja" if row.estado == "Baja" else "de categoría Menor"
			return _situacion(
				f"Pendiente: coincide con un socio {motivo}",
				socio=row.name,
				detalle=f"Figura como No socio y coincide con #{row.name} {row.nombre} {row.apellido} ({row.categoria}, {row.estado}).",
				pendiente=(
					"Verificar si es la misma persona. Si lo es, reactivarla o inscribirla en Gimnasio / Socio; "
					"si no, darla de alta como practicante No Socio."
				),
			)
		return planear_socio(row, grupo["nombre"], "no_socio_ya_es_socio")

	ns = padron.no_socio_existente(grupo["variantes"])
	membresia = grupo["membresia"]
	mensual = membresia == "MES"
	if ns:
		report["no_socio_existente"].append({"csv": grupo["nombre"], "socio": ns, "membresia": membresia})
		if mensual and not _tiene_inscripcion_gym(ns):
			report["inscribir_socio"].append({"csv": grupo["nombre"], "socio": ns, "origen": "no_socio_existente"})
			socios_a_inscribir[ns] = {"grupo": "no_socio"}
		dni = frappe.db.get_value("Socio", ns, "dni") or ""
		pendiente = _PENDIENTE_DATOS_NO_SOCIO if dni.startswith(DNI_PROVISORIO_PREFIX) else ""
		return _situacion("Practicante No Socio ya registrado", socio=ns, dni=dni, pendiente=pendiente)

	nombre, apellido = padron.separar_nombre(grupo["nombre"])
	if mensual:
		titulo = "Alta No Socio e inscripción mensual (Gimnasio / No Socio)"
		pendiente = _PENDIENTE_DATOS_NO_SOCIO
	else:
		concepto = "Quincena" if membresia == "QUINCENA" else "Entrenamiento por hora"
		titulo = f"Alta No Socio sin inscripción mensual ({concepto})"
		pendiente = (
			_PENDIENTE_DATOS_NO_SOCIO
			+ f" Generar el cargo de {concepto} desde la ficha cada vez que corresponda."
		)
	situacion = _situacion(titulo, detalle=f"Nombre: {nombre} / Apellido: {apellido}.", pendiente=pendiente)
	report["crear_no_socio"].append(
		{"csv": grupo["nombre"], "nombre": nombre, "apellido": apellido, "membresia": membresia, "situacion": situacion}
	)
	return situacion


def _lineas_reporte(
	filas: list[dict[str, Any]],
	situacion_por_linea: dict[int, dict[str, Any]],
	situacion_por_variante: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
	lineas: list[dict[str, Any]] = []
	primera_linea: dict[int, int] = {}
	for fila in filas:
		situacion = situacion_por_linea.get(fila["linea"]) or situacion_por_variante.get(
			normalizar_nombre(fila["nombre"])
		) or _situacion("Sin procesar")
		item = {
			"linea": fila["linea"],
			"nombre": fila["nombre"],
			"condicion": fila["condicion"].title(),
			"profesor": fila["profesor"],
			"membresia": fila["membresia"],
			**situacion,
		}
		clave = id(situacion)
		if clave in primera_linea:
			item["detalle"] = f"Misma persona que la línea {primera_linea[clave]}. {item['detalle']}".strip()
		else:
			primera_linea[clave] = fila["linea"]
		lineas.append(item)
	return lineas


def run(
	*,
	csv_path: str | None = None,
	apply: bool = False,
	confirm: str = "",
	confirmados: dict[str, str] | None = None,
	report_path: str | None = None,
) -> dict[str, Any]:
	dry_run = not apply
	ensure_bulk_apply_allowed(dry_run=dry_run, confirm=confirm)
	confirmados = {normalizar_nombre(k): v for k, v in (confirmados or {}).items()}

	padron = _Padron()
	filas = _leer_csv(csv_path or DEFAULT_CSV)
	grupo_socio = grupo_gimnasio_por_condicion(CONDICION_SOCIO)

	report: dict[str, Any] = {
		"dry_run": dry_run,
		"inscribir_socio": [],
		"crear_no_socio": [],
		"no_socio_existente": [],
		"ya_inscripto": [],
		"probables": [],
		"no_encontrados": [],
		"revisar": [],
		"nombre_incompleto": [],
		"grupos_no_socio": [],
	}
	socios_a_inscribir: dict[str, dict[str, Any]] = {}
	situacion_por_socio: dict[str, dict[str, Any]] = {}
	situacion_por_linea: dict[int, dict[str, Any]] = {}

	def planear_socio(row: dict[str, Any], csv_nombre: str, origen: str) -> dict[str, Any]:
		if row.name in situacion_por_socio:
			return situacion_por_socio[row.name]
		resumen = _resumen_socio(row)
		descripcion = f"#{row.name} {resumen['nombre']} ({row.categoria}, {row.estado})"
		if row.estado == "Baja":
			report["revisar"].append({"csv": csv_nombre, "motivo": "Socio en Baja", **resumen})
			situacion = _situacion(
				"Pendiente: socio en Baja",
				socio=row.name,
				detalle=descripcion,
				pendiente="Decidir si se reactiva al socio (y se inscribe en Gimnasio / Socio) o se lo da de alta como practicante No Socio.",
			)
		elif _tiene_inscripcion_gym(row.name):
			report["ya_inscripto"].append({"csv": csv_nombre, **resumen})
			socios_a_inscribir[row.name] = {}
			situacion = _situacion("Ya estaba inscripto en el gimnasio", socio=row.name, detalle=descripcion)
		else:
			item = {"csv": csv_nombre, "origen": origen, **resumen}
			socios_a_inscribir[row.name] = item
			report["inscribir_socio"].append(item)
			pendiente = ""
			if origen == "no_socio_ya_es_socio":
				descripcion += ". En el listado figuraba como No socio."
				pendiente = "Confirmar con el profesor que es socio (se le cobra el arancel Socio)."
			elif origen == "confirmado":
				descripcion += ". Coincidencia aproximada confirmada."
			situacion = _situacion("Inscripto en Gimnasio / Socio", socio=row.name, detalle=descripcion, pendiente=pendiente)
		situacion_por_socio[row.name] = situacion
		return situacion

	no_socio_filas: list[tuple[str, str]] = []
	for fila in filas:
		norm = normalizar_nombre(fila["nombre"])
		linea = fila["linea"]
		if len(norm.split()) < 2:
			report["nombre_incompleto"].append({"csv": fila["nombre"], "membresia": fila["membresia"]})
			situacion_por_linea[linea] = _situacion(
				"Pendiente: nombre incompleto",
				detalle="El listado no trae apellido.",
				pendiente="Obtener apellido y DNI y darlo de alta como practicante No Socio.",
			)
			continue
		if fila["condicion"] != "SOCIO":
			no_socio_filas.append((fila["nombre"], fila["membresia"]))
			continue

		if norm in confirmados:
			name = confirmados[norm]
			row = frappe.db.get_value(
				"Socio", name, ["name", "nombre", "apellido", "categoria", "estado"], as_dict=True
			)
			if not row:
				report["revisar"].append({"csv": fila["nombre"], "motivo": f"Socio confirmado {name} inexistente"})
				situacion_por_linea[linea] = _situacion(
					"Pendiente: socio no encontrado",
					detalle=f"El socio #{name} indicado no existe.",
					pendiente=_PENDIENTE_NO_ENCONTRADO,
				)
				continue
			situacion_por_linea[linea] = planear_socio(row, fila["nombre"], "confirmado")
			continue

		exactos = padron.exacto(norm)
		if len(exactos) == 1:
			situacion_por_linea[linea] = planear_socio(exactos[0], fila["nombre"], "exacto")
			continue
		if len(exactos) > 1:
			report["probables"].append(
				{"csv": fila["nombre"], "motivo": "Homónimos", "candidatos": [_resumen_socio(r) for r in exactos]}
			)
			situacion_por_linea[linea] = _situacion(
				"Pendiente: homónimos en el padrón",
				detalle="Candidatos: " + _candidatos_texto(exactos),
				pendiente="Identificar al socio por DNI e inscribirlo en Gimnasio / Socio.",
			)
			continue
		candidatos = padron.candidatos(norm)
		if candidatos:
			report["probables"].append(
				{"csv": fila["nombre"], "motivo": "Parecido", "candidatos": [_resumen_socio(r) for r in candidatos]}
			)
			situacion_por_linea[linea] = _situacion(
				"Pendiente: coincidencia dudosa",
				detalle="Parecido a: " + _candidatos_texto(candidatos),
				pendiente="Verificar por DNI. Si es ese socio, inscribirlo en Gimnasio / Socio; si no, seguir como socio no encontrado.",
			)
		else:
			report["no_encontrados"].append({"csv": fila["nombre"]})
			situacion_por_linea[linea] = _situacion(
				"Pendiente: socio no encontrado",
				detalle="No hay ningún socio con ese nombre en el padrón.",
				pendiente=_PENDIENTE_NO_ENCONTRADO,
			)

	situacion_por_variante: dict[str, dict[str, Any]] = {}
	for grupo in agrupar_no_socios(no_socio_filas):
		if len(grupo["variantes"]) > 1:
			report["grupos_no_socio"].append({"nombre": grupo["nombre"], "filas": grupo["originales"]})
		situacion = _planear_no_socio(grupo, padron, report, socios_a_inscribir, planear_socio)
		for variante in grupo["variantes"]:
			situacion_por_variante[variante] = situacion

	if apply:
		from club_management.activities.services.inscripcion_socio import inscribir_actividades_desk

		for name, item in socios_a_inscribir.items():
			if not item:
				continue
			grupo = grupo_gimnasio_por_condicion("No Socio") if item.get("grupo") == "no_socio" else grupo_socio
			inscribir_actividades_desk(name, [{"actividad": ACTIVIDAD_GIMNASIO, "grupo": grupo}])

		siguiente = _siguiente_dni_provisorio()
		for item in report["crear_no_socio"]:
			dni = f"{DNI_PROVISORIO_PREFIX}{siguiente:03d}"
			siguiente += 1
			item["dni"] = dni
			item["socio"] = crear_practicante_no_socio(
				_payload_no_socio(item["nombre"], item["apellido"], dni),
				inscribir_gimnasio=item["membresia"] == "MES",
			)
			item["situacion"]["socio"] = item["socio"]
			item["situacion"]["dni"] = dni

	report["lineas"] = _lineas_reporte(filas, situacion_por_linea, situacion_por_variante)
	report["resumen"] = {
		"filas_csv": len(filas),
		**{k: len(v) for k, v in report.items() if isinstance(v, list)},
	}
	if report_path:
		with open(report_path, "w", encoding="utf-8") as fh:
			json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
	return report

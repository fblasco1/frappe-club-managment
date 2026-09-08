"""Tests de parsear_telefono y mapeo CSV → Socio."""

from __future__ import annotations

from club_management.members.services.telefono import (
	mapear_telefonos_desde_fila,
	parsear_telefono,
)
from club_management.members.setup.import_socios_padron import build_socio_payload
from club_management.members.test_helpers import MembersTestCase


class TestParsearTelefono(MembersTestCase):
	def test_limpia_y_clasifica_celular(self) -> None:
		parsed = parsear_telefono("011-4444-5555")
		self.assertIsNotNone(parsed)
		assert parsed is not None
		self.assertEqual(parsed.numero, "01144445555")
		self.assertEqual(parsed.tipo, "Celular")

	def test_fijo_sin_codigo_area(self) -> None:
		parsed = parsear_telefono("456-7890")
		self.assertIsNotNone(parsed)
		assert parsed is not None
		self.assertEqual(parsed.numero, "4567890")
		self.assertEqual(parsed.tipo, "Fijo")

	def test_celular_con_prefijo_pais(self) -> None:
		parsed = parsear_telefono("+54 11 5555-6677")
		self.assertIsNotNone(parsed)
		assert parsed is not None
		self.assertEqual(parsed.numero, "541155556677")
		self.assertEqual(parsed.tipo, "Celular")

	def test_vacio_retorna_none(self) -> None:
		self.assertIsNone(parsear_telefono(""))
		self.assertIsNone(parsear_telefono("---"))
		self.assertIsNone(parsear_telefono(None))

	def test_umbral_diez_digitos(self) -> None:
		nueve = parsear_telefono("123456789")
		self.assertIsNotNone(nueve)
		assert nueve is not None
		self.assertEqual(nueve.tipo, "Fijo")
		diez = parsear_telefono("1234567890")
		self.assertIsNotNone(diez)
		assert diez is not None
		self.assertEqual(diez.tipo, "Celular")


class TestMapearTelefonosDesdeFila(MembersTestCase):
	def test_fijo_historico_en_columna_telefono(self) -> None:
		fijo, movil, invalidos = mapear_telefonos_desde_fila(
			{"teléfono": "4567890", "tel_movil": ""}
		)
		self.assertEqual(fijo, "4567890")
		self.assertEqual(movil, "")
		self.assertEqual(invalidos, [])

	def test_numero_largo_en_telefono_va_a_movil(self) -> None:
		fijo, movil, invalidos = mapear_telefonos_desde_fila(
			{"teléfono": "1162251916", "tel_movil": ""}
		)
		self.assertEqual(fijo, "")
		self.assertEqual(movil, "1162251916")
		self.assertEqual(invalidos, [])

	def test_tel_movil_sobrescribe_movil(self) -> None:
		fijo, movil, invalidos = mapear_telefonos_desde_fila(
			{"teléfono": "01144445555", "tel_movil": "+541155566677"}
		)
		self.assertEqual(fijo, "")
		self.assertEqual(movil, "541155566677")
		self.assertEqual(invalidos, [])

	def test_corto_invalido_no_se_asigna(self) -> None:
		fijo, movil, invalidos = mapear_telefonos_desde_fila(
			{"teléfono": "12345", "tel_movil": ""}
		)
		self.assertEqual(fijo, "")
		self.assertEqual(movil, "")
		self.assertEqual(invalidos, ["12345"])


class TestImportSociosPadronTelefonos(MembersTestCase):
	def _base_row(self) -> dict[str, str]:
		return {
			"nro_socio": "100",
			"socio": "PEREZ JUAN",
			"fecha_alta": "2020-01-01",
			"fecha_nacimiento": "1990-05-05",
			"doc_identidad": "30123456",
			"categoria_socio": "ACTIVO",
			"matrícula": "",
			"cobrador": "",
			"teléfono": "",
			"tel_movil": "",
			"email": "",
			"cuenta": "",
			"foto": "NO",
			"notas": "",
			"calle": "San Martín",
			"numero": "100",
			"piso": "",
			"departamento": "",
			"provincia": "Buenos Aires",
			"ciudad": "La Plata",
			"localidad_barrio": "Centro",
			"codigo_postal": "1900",
		}

	def test_build_socio_payload_aplica_heuristica(self) -> None:
		row = self._base_row()
		row["teléfono"] = "456-7890"
		row["tel_movil"] = "+54 11 5555-6677"
		payload = build_socio_payload(row)
		self.assertEqual(payload["telefono_fijo"], "4567890")
		self.assertEqual(payload["telefono_movil"], "541155556677")

	def test_build_socio_payload_expone_telefonos_invalidos(self) -> None:
		row = self._base_row()
		row["teléfono"] = "12345"
		payload, invalidos = build_socio_payload(row, return_telefonos_invalidos=True)
		self.assertEqual(invalidos, ["12345"])
		self.assertEqual(payload["telefono_fijo"], "")
		self.assertEqual(payload["telefono_movil"], "")

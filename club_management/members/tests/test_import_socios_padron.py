"""Tests del mapeo CSV → Socio en importación de padrón."""

from __future__ import annotations

import frappe

from club_management.members.setup.import_socios_padron import build_socio_payload
from club_management.members.test_helpers import MembersTestCase


class TestImportSociosPadronContactoDomicilio(MembersTestCase):
    def test_mapea_telefonos_email_vacio_y_domicilio_estructurado(self) -> None:
        row = {
            "nro_socio": "100",
            "socio": "PEREZ JUAN",
            "fecha_alta": "2020-01-01",
            "fecha_nacimiento": "1990-05-05",
            "doc_identidad": "30123456",
            "categoria_socio": "ACTIVO",
            "matrícula": "",
            "cobrador": "",
            "teléfono": "01144445555",
            "tel_movil": "+541155566677",
            "email": "",
            "cuenta": "",
            "foto": "NO",
            "notas": "",
            "calle": "San Martín",
            "numero": "100",
            "piso": "2",
            "departamento": "A",
            "provincia": "Buenos Aires",
            "ciudad": "La Plata",
            "localidad_barrio": "Centro",
            "codigo_postal": "1900",
        }
        payload = build_socio_payload(row)
        self.assertEqual(payload["telefono_fijo"], "01144445555")
        self.assertEqual(payload["telefono_movil"], "+541155566677")
        self.assertEqual(payload["email"], "")
        self.assertEqual(payload["calle"], "San Martín")
        self.assertEqual(payload["numero"], "100")
        self.assertEqual(payload["piso"], "2")
        self.assertEqual(payload["departamento"], "A")
        self.assertEqual(payload["provincia"], "Buenos Aires")
        self.assertEqual(payload["ciudad"], "La Plata")
        self.assertEqual(payload["localidad_barrio"], "Centro")
        self.assertNotIn("domicilio", payload)
        self.assertNotIn("telefono", payload)

    def test_email_invalido_en_csv_falla_antes_de_insert(self) -> None:
        row = {
            "nro_socio": "101",
            "socio": "LOPEZ ANA",
            "fecha_alta": "",
            "fecha_nacimiento": "1995-01-01",
            "doc_identidad": "32123456",
            "categoria_socio": "ACTIVO",
            "matrícula": "",
            "cobrador": "",
            "teléfono": "",
            "tel_movil": "",
            "email": "correo-invalido",
            "cuenta": "",
            "foto": "NO",
            "notas": "",
            "calle": "",
            "numero": "",
            "piso": "",
            "departamento": "",
            "provincia": "",
            "ciudad": "",
            "localidad_barrio": "",
            "codigo_postal": "",
        }
        with self.assertRaises(frappe.ValidationError):
            build_socio_payload(row)

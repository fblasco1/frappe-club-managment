"""Tests de la página pública de solicitud de asociación (Sprint 1 Commit 2.5).

Cubre la plantilla `www/solicitud-asociacion.html` según
`specs/solicitud_asociacion_publica.md` — decisión C2.5 camino B:

- El archivo existe en el paquete de la app.
- Declara el método whitelisted `submit_solicitud` y la subida
  `frappe.handler.upload_file`.
- Expone los `fieldname` del DocType en el markup.

No ejecuta navegador ni E2E HTTP: solo contrato estático del prototipo UI.
"""

from __future__ import annotations

import os

import frappe
from frappe.tests.utils import FrappeTestCase

SUBMIT_METHOD = "club_management.members.api.solicitud_publica.submit_solicitud"
ACTIVIDADES_METHOD = (
	"club_management.members.api.solicitud_publica.get_actividades_asociacion"
)
UPLOAD_METHOD = "frappe.handler.upload_file"


def _solicitud_web_page_path() -> str:
    return os.path.join(
        frappe.get_app_path("club_management"),
        "www",
        "solicitud-asociacion.html",
    )


class TestSolicitudAsociacionWebPage(FrappeTestCase):
    def test_archivo_plantilla_existe(self) -> None:
        self.assertTrue(
            os.path.isfile(_solicitud_web_page_path()),
            "Debe existir www/solicitud-asociacion.html en el paquete club_management",
        )

    def test_plantilla_declara_submit_solicitud_y_upload(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        self.assertIn(SUBMIT_METHOD, body)
        self.assertIn(UPLOAD_METHOD, body)

    def test_plantilla_incluye_fieldnames_doc(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        required = [
            'name="nombre"',
            'name="apellido"',
            'name="dni"',
            'name="categoria_solicitada"',
            'id="ficha_medica"',
            'name="fecha_nacimiento"',
            'name="genero"',
            'name="email"',
        ]
        for snip in required:
            with self.subTest(fragment=snip):
                self.assertIn(snip, body)

    def test_plantilla_bloque_responsable_y_token_por_textcontent(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        self.assertIn('name="dni_tutor"', body)
        self.assertIn("club-sol-responsable-block", body)
        self.assertIn("Datos del responsable", body)
        self.assertIn("textContent", body)
        self.assertIn("club-sol-token", body)

    def test_plantilla_documentacion_responsable_y_cargar_archivo(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        self.assertIn("dni_frente_tutor", body)
        self.assertIn("foto_perfil_tutor", body)
        self.assertNotIn("ficha_medica_tutor", body)
        self.assertIn("Cargar Archivo", body)
        self.assertIn("club-file-btn", body)
        self.assertIn("club-sol-actions", body)

    def test_plantilla_vinculo_padre_madre_tutor(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        self.assertIn('value="Padre"', body)
        self.assertIn('value="Madre"', body)
        self.assertIn('value="Tutor"', body)

    def test_plantilla_direccion_calle_y_google_places(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        self.assertIn('name="calle"', body)
        self.assertIn('name="telefono_movil"', body)
        self.assertIn('name="localidad_barrio"', body)
        self.assertIn('name="provincia"', body)
        self.assertIn('name="calle_tutor"', body)
        self.assertIn('name="telefono_movil_tutor"', body)
        self.assertNotIn('name="domicilio"', body)
        self.assertIn("club-address-autocomplete", body)
        self.assertIn("parseGoogleAddressComponents", body)
        self.assertIn("google_maps_api_key", body)
        self.assertIn("maps.googleapis.com/maps/api/js", body)
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    frappe.get_app_path("club_management"),
                    "www",
                    "solicitud-asociacion.py",
                )
            )
        )

    def test_plantilla_categoria_por_edad_y_actividades_combobox(self) -> None:
        with open(_solicitud_web_page_path(), encoding="utf-8") as f:
            body = f.read()
        self.assertIn("syncCategoriaPorEdad", body)
        self.assertIn("CATEGORIAS_MENOR", body)
        self.assertIn(ACTIVIDADES_METHOD, body)
        self.assertIn("club-actividades-combobox", body)
        self.assertIn("club-ms-combobox", body)
        self.assertIn("renderActividadPills", body)
        self.assertNotIn('id="actividad_interes"', body)


if __name__ == "__main__":
    import unittest

    unittest.main()

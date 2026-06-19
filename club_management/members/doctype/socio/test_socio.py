"""Tests rojos del DocType `Socio` (Sprint 0).

Cubre los escenarios principales de `club_management/specs/socio_minimo.md`:
- `estado` no es editable desde el formulario.
- `fecha_alta` se setea solo la primera vez que `estado` llega a `Activo`.
- `dni` único.
- `email` puede repetirse entre Socios (familia).
- `Socio.user` es 1 a 1.
- `categoria = "Menor"` exige `tipo_tutor`, `tutor`, `grupo_familiar`.
- `ficha_medica` valida MIME y tamaño.

Estos tests están escritos antes de implementar el DocType: en el primer run
deben fallar con `DocType not found` o `MandatoryError`, lo que indica que la
fase Red está activa.

Ejecución:

    bench --site <site> run-tests --app club_management \
        --module club_management.members.doctype.socio.test_socio
"""

from __future__ import annotations

import datetime
import unittest

import frappe

from club_management.members.test_helpers import (
    DUMMY_DNI_DORSO,
    DUMMY_DNI_FRENTE,
    DUMMY_FICHA_MEDICA,
    DUMMY_FOTO_PERFIL,
    MembersTestCase,
    adult_birthdate,
    insert_grupo_familiar_solo_socio,
    insert_socio,
    insert_tutor_no_socio,
    make_socio_payload,
    minor_birthdate,
)


class TestSocioCamposObligatorios(MembersTestCase):
    """Sprint 0 — campos obligatorios y unicidad básica."""

    def test_alta_adulto_minima_es_valida(self) -> None:
        socio = insert_socio()
        self.assertTrue(socio.name.startswith("SOC-"))
        self.assertEqual(socio.estado, "Pendiente de Validación")
        self.assertFalse(socio.get("fecha_alta"))

    def test_nombre_completo_apellido_nombre(self) -> None:
        socio = insert_socio(apellido="García", nombre="Ana")
        self.assertEqual(socio.nombre_completo, "García, Ana")
        self.assertEqual(
            frappe.db.get_value("Socio", socio.name, "nombre_completo"),
            "García, Ana",
        )

    def test_dni_obligatorio(self) -> None:
        payload = make_socio_payload(dni="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_nacionalidad_obligatoria(self) -> None:
        payload = make_socio_payload(nacionalidad="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_categoria_obligatoria(self) -> None:
        payload = make_socio_payload(categoria="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_dni_unico(self) -> None:
        insert_socio()
        with self.assertRaises(frappe.UniqueValidationError):
            insert_socio(dni="30123456", email="otro@example.com")

    def test_email_puede_repetirse_entre_socios(self) -> None:
        insert_socio(dni="30123456", email="familia@example.com")
        otro = insert_socio(dni="30654321", email="familia@example.com")
        self.assertEqual(otro.email, "familia@example.com")


class TestSocioEstadoReadOnly(MembersTestCase):
    """`estado` se muta solo desde server-side, no desde el form."""

    def test_estado_inicial_es_pendiente_de_validacion(self) -> None:
        socio = insert_socio()
        self.assertEqual(socio.estado, "Pendiente de Validación")

    def test_edicion_directa_de_estado_desde_usuario_falla(self) -> None:
        socio = insert_socio()
        socio.reload()
        socio.estado = "Activo"
        with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
            socio.save()

    def test_vitalicio_no_asignable_manualmente(self) -> None:
        socio = insert_socio()
        socio.reload()
        socio.estado = "Vitalicio"
        with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
            socio.save()


class TestSocioFechaAlta(MembersTestCase):
    """`fecha_alta` se setea una sola vez al primer `Activo`."""

    def test_fecha_alta_se_setea_al_pasar_a_activo(self) -> None:
        from club_management.members.services.socio_transitions import (
            cambiar_estado,
        )

        socio = insert_socio()
        cambiar_estado(socio.name, "Activo", motivo="Pago confirmado SI-0001")
        socio.reload()
        self.assertEqual(socio.estado, "Activo")
        self.assertEqual(socio.fecha_alta, datetime.date.today())

    def test_fecha_alta_no_se_sobreescribe_en_segunda_activacion(self) -> None:
        from club_management.members.services.socio_transitions import (
            cambiar_estado,
        )

        socio = insert_socio()
        cambiar_estado(socio.name, "Activo", motivo="Pago 1")
        socio.reload()
        primera_fecha = socio.fecha_alta
        self.assertTrue(primera_fecha)

        cambiar_estado(socio.name, "Moroso", motivo="Período vencido")
        cambiar_estado(socio.name, "Activo", motivo="Pago 2")
        socio.reload()
        self.assertEqual(socio.fecha_alta, primera_fecha)


class TestSocioAuditoria(MembersTestCase):
    """`ultimo_cambio_estado_*` se completa en cada transición."""

    def test_transicion_registra_auditoria(self) -> None:
        from club_management.members.services.socio_transitions import (
            cambiar_estado,
        )

        socio = insert_socio()
        cambiar_estado(socio.name, "Pendiente de Pago", motivo="Validada SOL-0001")
        socio.reload()
        self.assertEqual(socio.ultimo_cambio_estado_por, frappe.session.user)
        self.assertTrue(socio.ultimo_cambio_estado_en)
        self.assertEqual(socio.motivo_ultimo_cambio_estado, "Validada SOL-0001")


class TestSocioMenorRequiereTutor(MembersTestCase):
    """Invariantes del menor."""

    def test_menor_sin_tutor_falla(self) -> None:
        payload = make_socio_payload(
            dni="55222222",
            email="hijo@example.com",
            fecha_nacimiento=minor_birthdate(12),
            categoria="Menor",
        )
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_menor_con_tutor_socio_sin_grupo_es_valido(self) -> None:
        tutor = insert_socio(dni="30111112", email="papa.sin.grupo@example.com")

        payload = make_socio_payload(
            dni="55222223",
            email="hijo.sin.grupo@example.com",
            fecha_nacimiento=minor_birthdate(12),
            categoria="Menor",
            tipo_tutor="Socio",
            tutor=tutor.name,
        )
        socio_menor = frappe.get_doc(payload)
        socio_menor.insert(ignore_permissions=True)
        self.assertEqual(socio_menor.tutor, tutor.name)
        self.assertFalse(socio_menor.grupo_familiar)

    def test_menor_con_tutor_socio_y_grupo_es_valido(self) -> None:
        tutor = insert_socio(dni="30111111", email="papa@example.com")
        grupo = insert_grupo_familiar_solo_socio(tutor.name)

        payload = make_socio_payload(
            dni="55222222",
            email="hijo@example.com",
            fecha_nacimiento=minor_birthdate(12),
            categoria="Menor",
            tipo_tutor="Socio",
            tutor=tutor.name,
            grupo_familiar=grupo.name,
        )
        socio_menor = frappe.get_doc(payload)
        socio_menor.insert(ignore_permissions=True)
        self.assertEqual(socio_menor.tipo_tutor, "Socio")
        self.assertEqual(socio_menor.tutor, tutor.name)

    def test_menor_con_tutor_no_socio_y_grupo_es_valido(self) -> None:
        from club_management.members.test_helpers import (
            insert_grupo_familiar_solo_tutor,
        )

        tutor = insert_tutor_no_socio()
        grupo = insert_grupo_familiar_solo_tutor(tutor.name)

        payload = make_socio_payload(
            dni="55222222",
            email="hijo@example.com",
            fecha_nacimiento=minor_birthdate(12),
            categoria="Menor",
            tipo_tutor="Tutor No Socio",
            tutor=tutor.name,
            grupo_familiar=grupo.name,
        )
        socio_menor = frappe.get_doc(payload)
        socio_menor.insert(ignore_permissions=True)
        self.assertEqual(socio_menor.tipo_tutor, "Tutor No Socio")

    def test_menor_con_tutor_menor_de_edad_falla(self) -> None:
        tutor_joven = insert_socio(
            dni="30111113",
            email="t.joven@example.com",
            fecha_nacimiento=adult_birthdate(17),
        )

        payload = make_socio_payload(
            dni="55222224",
            email="hijo.joven@example.com",
            fecha_nacimiento=minor_birthdate(10),
            categoria="Menor",
            tipo_tutor="Socio",
            tutor=tutor_joven.name,
        )
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_adulto_no_exige_tutor_ni_grupo(self) -> None:
        adulto = insert_socio(categoria="Adherente")
        self.assertFalse(adulto.get("tutor"))
        self.assertFalse(adulto.get("grupo_familiar"))


class TestSocioContactoDomicilio(MembersTestCase):
    """Contacto y domicilio estructurado (`socio_contacto_domicilio.md`)."""

    def test_meta_tiene_telefonos_separados_y_domicilio_desglosado(self) -> None:
        meta = frappe.get_meta("Socio")
        self.assertIsNotNone(meta.get_field("telefono_fijo"))
        self.assertIsNotNone(meta.get_field("telefono_movil"))
        self.assertIsNotNone(meta.get_field("calle"))
        self.assertIsNotNone(meta.get_field("numero"))
        self.assertIsNotNone(meta.get_field("piso"))
        self.assertIsNotNone(meta.get_field("departamento"))
        self.assertIsNotNone(meta.get_field("ciudad"))
        self.assertIsNotNone(meta.get_field("localidad_barrio"))
        self.assertIsNone(meta.get_field("telefono"))
        self.assertIsNone(meta.get_field("domicilio"))
        self.assertIsNone(meta.get_field("localidad"))

    def test_alta_sin_email_falla_en_flujo_normal(self) -> None:
        payload = make_socio_payload(dni="30999888", email="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_alta_sin_telefono_movil_falla_en_flujo_normal(self) -> None:
        payload = make_socio_payload(dni="30999887", telefono_movil="")
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(payload).insert(ignore_permissions=True)

    def test_migracion_padron_permite_email_y_movil_vacios(self) -> None:
        payload = make_socio_payload(dni="30999886", email="", telefono_movil="")
        doc = frappe.get_doc(payload)
        doc.flags.ignore_validate = True
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
        self.assertEqual(doc.email or "", "")
        self.assertEqual(doc.telefono_movil or "", "")

    def test_alta_con_domicilio_estructurado(self) -> None:
        socio = insert_socio(
            dni="30999777",
            email="con.domicilio@example.com",
            calle="Av. Corrientes",
            numero="1234",
            piso="5",
            departamento="B",
            provincia="CABA",
            ciudad="CABA",
            localidad_barrio="San Telmo",
            telefono_fijo="0114567890",
            telefono_movil="+541112345678",
        )
        self.assertEqual(socio.calle, "Av. Corrientes")
        self.assertEqual(socio.numero, "1234")
        self.assertEqual(socio.piso, "5")
        self.assertEqual(socio.departamento, "B")
        self.assertEqual(socio.provincia, "CABA")
        self.assertEqual(socio.ciudad, "CABA")
        self.assertEqual(socio.localidad_barrio, "San Telmo")
        self.assertEqual(socio.telefono_fijo, "0114567890")
        self.assertEqual(socio.telefono_movil, "+541112345678")


class TestSocioFichaMedica(MembersTestCase):
    """Validación de MIME y tamaño de la ficha médica."""

    def test_mime_invalido_es_rechazado(self) -> None:
        from club_management.members.validations import validate_ficha_medica

        with self.assertRaises(frappe.ValidationError):
            validate_ficha_medica(
                file_url="/files/ficha.exe",
                mime_type="application/x-msdownload",
                file_size_bytes=10_000,
            )

    def test_tamano_excesivo_es_rechazado(self) -> None:
        from club_management.members.validations import validate_ficha_medica

        with self.assertRaises(frappe.ValidationError):
            validate_ficha_medica(
                file_url="/files/ficha.pdf",
                mime_type="application/pdf",
                file_size_bytes=6 * 1024 * 1024,  # 6 MB
            )

    def test_pdf_valido_pasa(self) -> None:
        from club_management.members.validations import validate_ficha_medica

        validate_ficha_medica(
            file_url="/files/ficha.pdf",
            mime_type="application/pdf",
            file_size_bytes=1 * 1024 * 1024,
        )


if __name__ == "__main__":
    unittest.main()

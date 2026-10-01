"""Tests del job programado de deuda mensual (spec cobranza_periodica_mensual.md § Scheduler)."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from club_management.members.jobs import cobranza_periodica as job
from club_management.members.services import cobranza_periodica as service
from club_management.members.test_helpers import MembersTestCase

JOB_PATH = "club_management.members.jobs.cobranza_periodica"


class TestCobranzaPeriodicaJob(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		settings = frappe.get_single("Club Settings")
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 10
		settings.save(ignore_permissions=True)
		frappe.db.set_global(job.MARCA_DEUDA_MENSUAL, "")

	def _run(self, reference_date: str):
		with patch(f"{JOB_PATH}.frappe.enqueue") as enqueue:
			job.run_generar_deuda_si_corresponde(reference_date=reference_date)
		return enqueue

	def test_hooks_programa_deuda_y_no_recargo_legado(self) -> None:
		from club_management import hooks

		daily = hooks.scheduler_events["daily"]
		self.assertIn(f"{JOB_PATH}.run_generar_deuda_si_corresponde", daily)
		self.assertNotIn(f"{JOB_PATH}.run_recargos_si_corresponde", daily)

	def test_dia_generacion_encola_en_cola_long(self) -> None:
		enqueue = self._run("2026-06-01")
		enqueue.assert_called_once()
		args, kwargs = enqueue.call_args
		self.assertEqual(args[0], f"{JOB_PATH}.ejecutar_generacion_deuda_mensual")
		self.assertEqual(kwargs["queue"], "long")
		self.assertEqual(kwargs["timeout"], job.DEUDA_JOB_TIMEOUT)
		self.assertGreaterEqual(job.DEUDA_JOB_TIMEOUT, 2 * 60 * 60)
		self.assertEqual(kwargs["job_id"], "deuda_mensual_06-2026")
		self.assertTrue(kwargs["deduplicate"])
		self.assertEqual(kwargs["reference_date"], "2026-06-01")

	def test_reintento_dentro_de_ventana_si_no_esta_marcado(self) -> None:
		enqueue = self._run("2026-06-05")
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.kwargs["reference_date"], "2026-06-01")

	def test_no_encola_periodo_ya_marcado(self) -> None:
		frappe.db.set_global(job.MARCA_DEUDA_MENSUAL, "06/2026")
		self._run("2026-06-01").assert_not_called()
		self._run("2026-06-05").assert_not_called()

	def test_no_encola_fuera_de_ventana(self) -> None:
		self._run("2026-06-10").assert_not_called()
		self._run("2026-06-15").assert_not_called()

	def test_ejecucion_commit_por_socio_marca_y_resumen(self) -> None:
		resultado = {
			"periodo": "06/2026",
			"reference_date": "2026-06-01",
			"facturas_creadas": 3,
			"socios_omitidos": 1,
			"errores": 0,
			"invoice_names": [],
			"detalle_errores": [],
		}
		with (
			patch(f"{JOB_PATH}.generar_deuda_mensual_socios", return_value=resultado) as generar,
			patch.object(frappe.db, "commit"),
		):
			out = job.ejecutar_generacion_deuda_mensual(reference_date="2026-06-01")

		self.assertEqual(out, resultado)
		self.assertTrue(generar.call_args.kwargs["commit_por_socio"])
		self.assertEqual(str(generar.call_args.kwargs["reference_date"]), "2026-06-01")
		self.assertEqual(frappe.db.get_global(job.MARCA_DEUDA_MENSUAL), "06/2026")
		self.assertTrue(
			frappe.db.exists("Error Log", {"method": "Deuda mensual 06/2026 — resumen"})
		)


class TestGenerarDeudaCommitPorSocio(MembersTestCase):
	def test_rollback_solo_del_socio_con_error(self) -> None:
		def _fake(socio_name: str, **_kwargs):
			if socio_name == "S-ERR":
				raise frappe.ValidationError("falla")
			return f"SI-{socio_name}"

		with (
			patch.object(service, "socios_elegibles_deuda_mensual", return_value=["S-OK1", "S-ERR", "S-OK2"]),
			patch.object(service, "generar_deuda_mensual_socio", side_effect=_fake),
			patch.object(frappe.db, "commit") as commit,
			patch.object(frappe.db, "rollback") as rollback,
		):
			out = service.generar_deuda_mensual_socios(reference_date="2026-06-01", commit_por_socio=True)

		self.assertEqual(out["facturas_creadas"], 2)
		self.assertEqual(out["errores"], 1)
		rollback.assert_called_once()
		self.assertGreaterEqual(commit.call_count, 2)

	def test_sin_commit_por_defecto(self) -> None:
		with (
			patch.object(service, "socios_elegibles_deuda_mensual", return_value=["S-OK1"]),
			patch.object(service, "generar_deuda_mensual_socio", return_value="SI-1"),
			patch.object(frappe.db, "commit") as commit,
		):
			service.generar_deuda_mensual_socios(reference_date="2026-06-01")
		commit.assert_not_called()

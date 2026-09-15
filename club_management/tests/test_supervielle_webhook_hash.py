"""Regresión: el callback no acepta el contrato legacy cod_trx/hash."""

from __future__ import annotations

import unittest

from club_management.integrations.supervielle.reconciliation import validate_callback_payload
from club_management.integrations.supervielle_api import SupervielleIntegrationError


class TestSupervielleWebhookHash(unittest.TestCase):
	def test_rechaza_payload_legacy(self) -> None:
		payload = {
			"cuit": "30704950345",
			"cod_trx": "1234567890",
			"hash": "deadbeef",
		}
		with self.assertRaises(SupervielleIntegrationError):
			validate_callback_payload(payload, "secret")

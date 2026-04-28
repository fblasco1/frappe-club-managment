import unittest

from club_management.integrations.supervielle_webhook import (
    SupervielleWebhookAuthError,
    validate_webhook_hash,
)


class TestSupervielleWebhookHash(unittest.TestCase):
    def test_validate_webhook_hash_accepts_correct_hash(self) -> None:
        secret_key = "442FB495-C8CE42C1-86A4-3891E465D492"

        payload = {
            "cuit": "30704950345",
            "id_clave": "1234567890",
            "hash": "6d41f7f5c9c53666313b900957d3b3a3730305027aab04910d3e8777cef10e2e",
        }

        validate_webhook_hash(payload, secret_key=secret_key)

    def test_validate_webhook_hash_rejects_invalid_hash(self) -> None:
        secret_key = "442FB495-C8CE42C1-86A4-3891E465D492"

        payload = {
            "cuit": "30704950345",
            "id_clave": "1234567890",
            "hash": "deadbeef",
        }

        with self.assertRaises(SupervielleWebhookAuthError):
            validate_webhook_hash(payload, secret_key=secret_key)


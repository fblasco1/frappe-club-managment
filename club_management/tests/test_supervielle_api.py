import unittest

from club_management.integrations.supervielle_api import SupervielleAPI


class TestSupervielleAPIHash(unittest.TestCase):
    def test_generate_hash_concatenates_values_in_order_and_appends_secret(self) -> None:
        api = SupervielleAPI(secret_key="442FB495-C8CE42C1-86A4-3891E465D492")

        payload = {
            "cuit": "30704950345",
            "id_clave": "1234567890",
            "hash": "",
        }

        # SHA-256("30704950345" + "1234567890" + secret_key)
        expected = "6d41f7f5c9c53666313b900957d3b3a3730305027aab04910d3e8777cef10e2e"
        self.assertEqual(expected, api._generate_hash(payload))

    def test_generate_hash_skips_hash_key_case_insensitive(self) -> None:
        api = SupervielleAPI(secret_key="442FB495-C8CE42C1-86A4-3891E465D492")
        with_hash = {
            "cuit": "30704950345",
            "id_clave": "1234567890",
            "Hash": "should-be-ignored",
        }
        without = {"cuit": "30704950345", "id_clave": "1234567890"}
        self.assertEqual(api._generate_hash(with_hash), api._generate_hash(without))


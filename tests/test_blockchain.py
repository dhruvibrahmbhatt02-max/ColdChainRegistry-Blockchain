import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blockchain import ColdChainBlockchain, describe_transaction
from demo import load_demo_scenario


class BlockchainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = ColdChainBlockchain(Path(self.temp.name) / "ledger.json", difficulty=1)

    def tearDown(self):
        self.temp.cleanup()

    def add_sample(self):
        return self.ledger.add_transaction({
            "type": "BATCH_REGISTERED", "batch_id": "VAX-TEST",
            "vaccine_name": "Test vaccine", "manufacturer": "Test manufacturer",
            "min_temp": 2.0, "max_temp": 8.0, "expiry_date": "2030-01-01",
            "actor": "Manufacturer"
        })

    def record(self, kind, **fields):
        return self.ledger.add_transaction({"type": kind, "batch_id": "VAX-TEST", **fields})

    # ---- original six tests ----
    def test_genesis_block_valid(self):
        self.assertTrue(self.ledger.is_valid()[0])

    def test_new_block_links_to_previous(self):
        block = self.add_sample()
        self.assertEqual(block["previous_hash"], self.ledger.chain[0]["hash"])
        self.assertTrue(self.ledger.is_valid()[0])

    def test_batch_registration_is_reconstructed(self):
        self.add_sample()
        batch = self.ledger.find_batch("VAX-TEST")
        self.assertEqual(batch["status"], "Active")
        self.assertEqual(batch["vaccine_name"], "Test vaccine")

    def test_out_of_range_temperature_quarantines_batch(self):
        self.add_sample()
        self.record("TEMPERATURE_RECORDED", temperature=12.5, actor="Sensor Operator")
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["status"], "Quarantined")

    def test_in_range_temperature_keeps_batch_active(self):
        self.add_sample()
        self.record("TEMPERATURE_RECORDED", temperature=5.0, actor="Sensor Operator")
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["status"], "Active")

    def test_tampering_is_detected(self):
        self.add_sample()
        self.ledger.tamper_block_for_demo(1)
        self.assertFalse(self.ledger.is_valid()[0])

    # ---- new tests ----
    def test_in_range_reading_does_not_release_quarantine(self):
        self.add_sample()
        self.record("TEMPERATURE_RECORDED", temperature=12.5, actor="Sensor Operator")
        self.record("TEMPERATURE_RECORDED", temperature=5.0, actor="Sensor Operator")
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["status"], "Quarantined")

    def test_regulator_release_returns_quarantined_batch_to_active(self):
        self.add_sample()
        self.record("TEMPERATURE_RECORDED", temperature=12.5, actor="Sensor Operator")
        self.record("BATCH_RELEASED", actor="Regulator")
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["status"], "Active")

    def test_recalled_batch_stays_recalled_after_bad_reading_and_release(self):
        self.add_sample()
        self.record("BATCH_RECALLED", actor="Regulator")
        self.record("TEMPERATURE_RECORDED", temperature=20.0, actor="Sensor Operator")
        self.record("BATCH_RELEASED", actor="Regulator")
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["status"], "Recalled")

    def test_dispensed_batch_stays_dispensed_after_bad_reading(self):
        self.add_sample()
        self.record("BATCH_DISPENSED", actor="Regulator")
        self.record("TEMPERATURE_RECORDED", temperature=20.0, actor="Sensor Operator")
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["status"], "Dispensed")

    def test_custody_transfer_changes_custodian(self):
        self.add_sample()
        self.record("CUSTODY_TRANSFERRED", **{"from": "Manufacturer", "to": "Distributor", "actor": "Manufacturer"})
        self.assertEqual(self.ledger.find_batch("VAX-TEST")["custodian"], "Distributor")

    def test_unknown_batch_returns_none(self):
        self.assertIsNone(self.ledger.find_batch("NOPE"))

    def test_chain_persists_after_reload(self):
        self.add_sample()
        reloaded = ColdChainBlockchain(self.ledger.path, difficulty=1)
        self.assertEqual(len(reloaded.chain), 2)
        self.assertTrue(reloaded.is_valid()[0])

    def test_rebuilt_hash_breaks_next_link(self):
        """If an attacker recomputes one block's hash, the NEXT block's link fails."""
        self.add_sample()
        self.record("TEMPERATURE_RECORDED", temperature=5.0, actor="Sensor Operator")
        self.ledger.chain[1]["transactions"][0]["vaccine_name"] = "Forged"
        self.ledger._mine(self.ledger.chain[1])
        ok, msg = self.ledger.is_valid()
        self.assertFalse(ok)
        self.assertIn("link", msg)

    def test_verify_details_flags_only_the_tampered_block(self):
        self.add_sample()
        self.record("TEMPERATURE_RECORDED", temperature=5.0, actor="Sensor Operator")
        self.ledger.tamper_block_for_demo(1)
        flags = [r["ok"] for r in self.ledger.verify_details()]
        self.assertEqual(flags, [True, False, True])

    def test_undo_demo_tampering_restores_validity(self):
        self.add_sample()
        self.ledger.tamper_block_for_demo(1)
        self.assertFalse(self.ledger.is_valid()[0])
        self.assertEqual(self.ledger.undo_demo_tampering(), 1)
        self.assertTrue(self.ledger.is_valid()[0])

    def test_genesis_cannot_be_tampered(self):
        with self.assertRaises(ValueError):
            self.ledger.tamper_block_for_demo(0)

    def test_reset_returns_to_single_genesis_block(self):
        self.add_sample()
        self.ledger.reset()
        self.assertEqual(len(self.ledger.chain), 1)
        self.assertTrue(self.ledger.is_valid()[0])

    def test_corrupt_ledger_file_is_backed_up_not_lost(self):
        path = Path(self.temp.name) / "bad.json"
        path.write_text("{ not json", encoding="utf-8")
        ledger = ColdChainBlockchain(path, difficulty=1)
        self.assertEqual(len(ledger.chain), 1)
        self.assertTrue(path.with_suffix(".corrupt.json").exists())

    def test_mined_hash_meets_difficulty(self):
        block = self.add_sample()
        self.assertTrue(block["hash"].startswith("0"))

    def test_demo_scenario_builds_expected_states_and_valid_chain(self):
        added = load_demo_scenario(self.ledger)
        self.assertEqual(added, ["DEMO-001", "DEMO-002", "DEMO-003"])
        self.assertEqual(self.ledger.find_batch("DEMO-001")["status"], "Quarantined")
        self.assertEqual(self.ledger.find_batch("DEMO-002")["custodian"], "Clinic")
        self.assertEqual(self.ledger.find_batch("DEMO-003")["status"], "Active")
        self.assertTrue(self.ledger.is_valid()[0])
        self.assertEqual(load_demo_scenario(self.ledger), [])  # no duplicates on second click

    def test_describe_transaction_is_plain_english(self):
        text = describe_transaction({"type": "TEMPERATURE_RECORDED", "temperature": 12.5,
                                     "actor": "Sensor Operator", "within_range": False})
        self.assertIn("OUTSIDE safe range", text)


if __name__ == "__main__":
    unittest.main()

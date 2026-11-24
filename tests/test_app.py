"""UI workflow tests using Streamlit's AppTest (runs the real app.py without a browser)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAGES = ["🏠 Home", "📘 How it works", "➕ Register batch", "🌡️ Record temperature",
         "🚚 Transfer custody", "🛡️ Regulator actions", "🔎 Track a batch",
         "✅ Verify & tamper test", "📜 Audit history"]


class AppWorkflowTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["COLDCHAIN_LEDGER"] = str(Path(self.tmp.name) / "ledger.json")
        for mod in ("blockchain", "demo"):
            sys.modules.pop(mod, None)
        import streamlit as st
        st.cache_resource.clear()
        self.at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        self.at.run()

    def tearDown(self):
        os.environ.pop("COLDCHAIN_LEDGER", None)
        self.tmp.cleanup()

    def go(self, page, actor=None):
        self.at.session_state["page"] = page
        if actor:
            self.at.session_state["actor"] = actor
        self.at.run()
        self.assertFalse(self.at.exception, self.at.exception)

    def button(self, fragment):
        return next(b for b in self.at.button if fragment in b.label)

    def load_demo(self):
        self.go("🏠 Home")
        self.button("demo data").click().run()
        self.assertFalse(self.at.exception)

    def test_every_page_renders_empty_and_with_data(self):
        for page in PAGES:
            self.go(page)
        self.load_demo()
        for page in PAGES:
            for actor in ("Regulator", "Manufacturer", "Clinic"):
                self.go(page, actor)

    def test_demo_button_loads_three_batches(self):
        self.load_demo()
        self.go("🏠 Home")
        self.assertEqual(self.at.metric[0].value, "3")

    def test_register_rejects_wrong_role_buttons_disabled(self):
        self.go("➕ Register batch", "Clinic")
        self.assertTrue(any("Register" in b.label and b.disabled for b in self.at.get("button")))

    def test_register_then_duplicate_is_rejected(self):
        self.go("➕ Register batch", "Manufacturer")
        self.at.text_input[0].set_value("VAX-9"); self.at.text_input[1].set_value("Test Vax")
        self.at.button[0].click().run()
        self.go("🏠 Home")
        self.assertEqual(self.at.metric[0].value, "1")
        self.go("➕ Register batch", "Manufacturer")
        self.at.text_input[0].set_value("VAX-9"); self.at.text_input[1].set_value("Test Vax")
        self.at.button[0].click().run()
        self.assertTrue(any("already exists" in e.value for e in self.at.error))

    def test_hot_reading_quarantines_and_flash_message_survives_rerun(self):
        self.load_demo()
        self.go("🌡️ Record temperature", "Sensor Operator")
        self.at.selectbox(key="Choose a vaccine batch_🌡️ Record temperature").select("DEMO-002").run()
        self.at.number_input[0].set_value(12.5).run()
        self.assertTrue(any("OUTSIDE" in w.value for w in self.at.warning))
        self.button("Record temperature").click().run()
        self.assertTrue(any("Saved permanently" in s.value or "saved permanently" in s.value for s in self.at.success))
        self.go("🔎 Track a batch")
        self.at.selectbox(key="Choose a vaccine batch_🔎 Track a batch").select("DEMO-002").run()
        self.assertTrue(any("Quarantined" in w.value for w in self.at.warning))

    def test_tamper_detected_then_undone(self):
        self.load_demo()
        self.go("✅ Verify & tamper test")
        self.button("Secretly edit").click().run()
        self.assertTrue(any("INTEGRITY WARNING" in e.value for e in self.at.error))
        self.button("Undo the demo edit").click().run()
        self.assertFalse(any("INTEGRITY WARNING" in e.value for e in self.at.error))

    def test_reset_needs_confirmation(self):
        self.load_demo()
        self.go("✅ Verify & tamper test")
        self.assertTrue(self.button("Reset demo ledger").disabled)


if __name__ == "__main__":
    unittest.main()

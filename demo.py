"""One-click sample data so a first-time viewer can see the app working immediately."""
from __future__ import annotations

from datetime import date, timedelta

from blockchain import ColdChainBlockchain


def load_demo_scenario(ledger: ColdChainBlockchain) -> list[str]:
    """Add three fictional batches that each tell a different story. Returns the IDs added."""
    expiry = (date.today() + timedelta(days=365)).isoformat()

    def register(bid: str, vaccine: str) -> None:
        ledger.add_transaction({
            "type": "BATCH_REGISTERED", "batch_id": bid, "vaccine_name": vaccine,
            "manufacturer": "Demo Pharma Ltd", "min_temp": 2.0, "max_temp": 8.0,
            "expiry_date": expiry, "actor": "Manufacturer",
        })

    def temp(bid: str, value: float, note: str) -> None:
        ledger.add_transaction({
            "type": "TEMPERATURE_RECORDED", "batch_id": bid, "temperature": value,
            "note": note, "actor": "Sensor Operator", "within_range": 2.0 <= value <= 8.0,
        })

    def hand_over(bid: str, giver: str, receiver: str) -> None:
        ledger.add_transaction({
            "type": "CUSTODY_TRANSFERRED", "batch_id": bid, "from": giver, "to": receiver,
            "actor": giver, "note": "Demo handover",
        })

    existing = set(ledger.batch_ids())
    added = []
    if "DEMO-001" not in existing:   # story 1: a temperature excursion -> quarantine
        register("DEMO-001", "Demo Vaccine A")
        temp("DEMO-001", 5.0, "Routine check")
        temp("DEMO-001", 12.5, "Fridge door left open")
        added.append("DEMO-001")
    if "DEMO-002" not in existing:   # story 2: a healthy journey to the clinic
        register("DEMO-002", "Demo Vaccine B")
        temp("DEMO-002", 4.5, "Routine check")
        hand_over("DEMO-002", "Manufacturer", "Distributor")
        temp("DEMO-002", 6.0, "Truck check")
        hand_over("DEMO-002", "Distributor", "Clinic")
        added.append("DEMO-002")
    if "DEMO-003" not in existing:   # story 3: excursion reviewed and released
        register("DEMO-003", "Demo Vaccine C")
        temp("DEMO-003", 9.5, "Slight warm-up in transit")
        ledger.add_transaction({"type": "BATCH_RELEASED", "batch_id": "DEMO-003",
                                "actor": "Regulator", "reason": "Excursion reviewed, product safe"})
        added.append("DEMO-003")
    return added

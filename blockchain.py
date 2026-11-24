"""
Educational blockchain simulation for ColdChainRegistry.

Uses only Python standard-library modules. This is a single-machine demonstration:
it models blocks, SHA-256 hash links, proof-of-work mining and chain validation.
It is NOT a peer-to-peer decentralized blockchain.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
# COLDCHAIN_LEDGER lets automated tests use a throw-away file instead of the real ledger.
LEDGER_FILE = Path(os.environ.get("COLDCHAIN_LEDGER", DATA_DIR / "ledger.json"))
DIFFICULTY = 2  # leading hexadecimal zeroes; keep low for a classroom demo


def canonical_json(value: Any) -> str:
    """Stable JSON representation so the same data produces the same hash."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ColdChainBlockchain:
    def __init__(self, path: Path = LEDGER_FILE, difficulty: int = DIFFICULTY):
        self.path = Path(path)
        self.difficulty = difficulty
        self.chain: list[dict[str, Any]] = []
        self.load()

    def _block_payload(self, block: dict[str, Any]) -> dict[str, Any]:
        return {
            "index": block["index"],
            "timestamp": block["timestamp"],
            "transactions": block["transactions"],
            "previous_hash": block["previous_hash"],
            "nonce": block["nonce"],
        }

    def calculate_hash(self, block: dict[str, Any]) -> str:
        return sha256_text(canonical_json(self._block_payload(block)))

    def _mine(self, block: dict[str, Any]) -> dict[str, Any]:
        """Proof of Work: raise the nonce until the hash starts with `difficulty` zeroes."""
        target = "0" * self.difficulty
        while True:
            candidate_hash = self.calculate_hash(block)
            if candidate_hash.startswith(target):
                block["hash"] = candidate_hash
                return block
            block["nonce"] += 1

    def create_genesis_block(self) -> dict[str, Any]:
        block = {
            "index": 0,
            "timestamp": utc_now(),
            "transactions": [{"type": "GENESIS", "message": "ColdChainRegistry ledger created"}],
            "previous_hash": "0" * 64,
            "nonce": 0,
        }
        return self._mine(block)

    def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                self.chain = stored.get("chain", [])
            except (json.JSONDecodeError, OSError, AttributeError):
                # Keep a copy of the unreadable file so it is not silently lost.
                self.chain = []
                try:
                    self.path.replace(self.path.with_suffix(".corrupt.json"))
                except OSError:
                    pass
        if not self.chain:
            self.chain = [self.create_genesis_block()]
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps({"chain": self.chain}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def add_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        """Mine a block immediately so each accepted action becomes permanent in this demo."""
        clean_tx = dict(transaction)
        clean_tx.setdefault("timestamp", utc_now())
        block = {
            "index": len(self.chain),
            "timestamp": utc_now(),
            "transactions": [clean_tx],
            "previous_hash": self.chain[-1]["hash"],
            "nonce": 0,
        }
        self._mine(block)
        self.chain.append(block)
        self.save()
        return block

    def verify_details(self) -> list[dict[str, Any]]:
        """Per-block result of the three integrity checks (used by the UI)."""
        results = []
        target = "0" * self.difficulty
        for i, block in enumerate(self.chain):
            try:
                hash_ok = block.get("hash") == self.calculate_hash(block)
            except KeyError:
                hash_ok = False
            expected_prev = "0" * 64 if i == 0 else self.chain[i - 1].get("hash")
            link_ok = block.get("previous_hash") == expected_prev
            pow_ok = str(block.get("hash", "")).startswith(target)
            results.append({"index": i, "hash_ok": hash_ok, "link_ok": link_ok, "pow_ok": pow_ok,
                            "ok": hash_ok and link_ok and pow_ok})
        return results

    def is_valid(self) -> tuple[bool, str]:
        if not self.chain:
            return False, "The ledger is empty."
        for r in self.verify_details():
            i = r["index"]
            if not r["hash_ok"]:
                return False, f"Block {i} has been modified: its stored hash does not match."
            if not r["link_ok"]:
                if i == 0:
                    return False, "Genesis block has an invalid previous hash."
                return False, f"Block {i} does not correctly link to block {i - 1}."
            if not r["pow_ok"]:
                return False, f"Block {i} does not satisfy the proof-of-work difficulty."
        return True, "All blocks, hashes, links and proof-of-work values are valid."

    def all_transactions(self) -> list[dict[str, Any]]:
        rows = []
        for block in self.chain:
            for tx in block.get("transactions", []):
                if tx.get("type") != "GENESIS":
                    row = dict(tx)
                    row["block_index"] = block["index"]
                    row["block_hash"] = block["hash"]
                    row["block_time"] = block["timestamp"]
                    rows.append(row)
        return rows

    def find_batch(self, batch_id: str) -> dict[str, Any] | None:
        state = None
        for tx in self.all_transactions():
            if tx.get("batch_id") != batch_id:
                continue
            kind = tx.get("type")
            if kind == "BATCH_REGISTERED":
                state = {
                    "batch_id": batch_id,
                    "vaccine_name": tx["vaccine_name"],
                    "manufacturer": tx["manufacturer"],
                    "min_temp": float(tx["min_temp"]),
                    "max_temp": float(tx["max_temp"]),
                    "expiry_date": tx["expiry_date"],
                    "custodian": tx["actor"],
                    "status": "Active",
                    "last_temperature": None,
                    "readings": [],
                }
            elif state is not None:
                if kind == "TEMPERATURE_RECORDED":
                    state["last_temperature"] = float(tx["temperature"])
                    state["readings"].append(tx)
                    out_of_range = not (state["min_temp"] <= float(tx["temperature"]) <= state["max_temp"])
                    # Only an Active batch can be quarantined; Recalled/Dispensed are final.
                    if out_of_range and state["status"] == "Active":
                        state["status"] = "Quarantined"
                elif kind == "CUSTODY_TRANSFERRED":
                    state["custodian"] = tx["to"]
                elif kind == "BATCH_RELEASED" and state["status"] == "Quarantined":
                    state["status"] = "Active"
                elif kind == "BATCH_RECALLED":
                    state["status"] = "Recalled"
                elif kind == "BATCH_DISPENSED" and state["status"] == "Active":
                    state["status"] = "Dispensed"
        return state

    def batch_history(self, batch_id: str) -> list[dict[str, Any]]:
        """All events for one batch, oldest first, each with its block number."""
        return [tx for tx in self.all_transactions() if tx.get("batch_id") == batch_id]

    def batch_ids(self) -> list[str]:
        return [
            tx["batch_id"] for tx in self.all_transactions()
            if tx.get("type") == "BATCH_REGISTERED"
        ]

    def tamper_block_for_demo(self, block_index: int) -> None:
        """Deliberately changes stored transaction data without recalculating its hash."""
        if block_index <= 0 or block_index >= len(self.chain):
            raise ValueError("Choose a non-genesis block.")
        txs = self.chain[block_index]["transactions"]
        if not txs:
            raise ValueError("Selected block has no transactions.")
        txs[0]["tampered_demo"] = True
        self.save()

    def undo_demo_tampering(self) -> int:
        """Remove the marker added by tamper_block_for_demo; returns how many were removed."""
        removed = 0
        for block in self.chain:
            for tx in block.get("transactions", []):
                if "tampered_demo" in tx:
                    del tx["tampered_demo"]
                    removed += 1
        if removed:
            self.save()
        return removed

    def reset(self) -> None:
        self.chain = [self.create_genesis_block()]
        self.save()


def describe_transaction(tx: dict[str, Any]) -> str:
    """One plain-English sentence for a transaction (for non-technical readers)."""
    kind = tx.get("type")
    actor = tx.get("actor", "Someone")
    if kind == "GENESIS":
        return "Ledger created (starting block)"
    if kind == "BATCH_REGISTERED":
        return (f"{actor} registered {tx.get('vaccine_name', 'a vaccine')} "
                f"(safe range {tx.get('min_temp')}–{tx.get('max_temp')} °C, expires {tx.get('expiry_date')})")
    if kind == "TEMPERATURE_RECORDED":
        temp = float(tx["temperature"])
        flag = tx.get("within_range")
        verdict = "" if flag is None else (" — within safe range" if flag else " — OUTSIDE safe range")
        return f"{actor} recorded {temp:.1f} °C{verdict}"
    if kind == "CUSTODY_TRANSFERRED":
        return f"Custody moved from {tx.get('from')} to {tx.get('to')}"
    if kind == "BATCH_RELEASED":
        return f"{actor} released the batch from quarantine ({tx.get('reason', 'no reason given')})"
    if kind == "BATCH_RECALLED":
        return f"{actor} recalled the batch ({tx.get('reason', 'no reason given')})"
    if kind == "BATCH_DISPENSED":
        return f"{actor} marked the batch as dispensed"
    return str(kind)

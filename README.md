# ColdChainRegistry — Streamlit + Python version

## Project title
**ColdChainRegistry: A Python-Based Blockchain System for Vaccine Cold-Chain Traceability and Temperature Monitoring**

## Why this version?
This version intentionally uses Python and Streamlit, with SHA-256 hashing and a simple Proof-of-Work mining demonstration. Streamlit is the only required third-party Python package. It avoids Solidity, Hardhat, Node.js, React, MetaMask, OpenZeppelin, cloud services and physical IoT hardware.

## What it demonstrates
- Vaccine batch registration
- Blocks containing transactions, timestamps, nonce and previous-block hash
- SHA-256 hashing
- Proof-of-Work mining (small configurable difficulty)
- Chain validation and tamper detection
- Temperature logging and automatic quarantine when outside a batch's configured range
- Custody history
- Regulator release and recall actions
- Audit history and JSON export

## What it does NOT demonstrate
- It is not a distributed or peer-to-peer blockchain: there is one local ledger file on one computer.
- The role selector is a classroom simulation, not secure login or cryptographic identity.
- It does not implement real Bitcoin mining, a mining pool, a Byzantine fault-tolerant consensus protocol, Hyperledger, or real IoT sensor integration.
- The temperature data is manually entered; the program cannot prove a physical sensor reading is truthful.
- The sample 2–8 °C range is a demonstration setting only. Real vaccine storage requirements must be checked against authoritative product-specific guidance.

## Requirements
- Python 3.10 or newer
- VS Code
- Internet only for installing Streamlit the first time (Streamlit brings its own pandas dependency; this project's code does not import pandas)

## Windows setup (VS Code terminal)

1. Extract the ZIP and open the `ColdChainRegistry_Streamlit` folder in VS Code.
2. Check Python:

```powershell
python --version
```

3. Create a virtual environment:

```powershell
python -m venv .venv
```

4. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt terminal and run:

```cmd
.venv\Scripts\activate.bat
```

5. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

6. Start the application:

```powershell
streamlit run app.py
```

Streamlit will show a local address, usually `http://localhost:8501`.

## Quick start for non-technical viewers
1. Run the app, open **Home** and click **Load sample demo data** - three fictional batches appear instantly.
2. Open **How it works** for a plain-language explanation and two live experiments (fingerprint / mining).
3. Open **Track a batch** to read a batch's journey as a timeline in plain English.
4. Open **Verify & tamper test**, click *Secretly edit this block*, watch the red ❌, then *Undo the demo edit*.

## Suggested demonstration
1. In the sidebar, select Manufacturer.
2. Register batch `VAX-001`, with a demonstration range of 2–8 °C.
3. Select Sensor Operator and record 5.0 °C. Status remains Active.
4. Record 12.5 °C. The batch becomes Quarantined.
5. Open Dashboard and Audit history to inspect the state and blocks.
6. Select Regulator and release the batch or recall it.
7. Open Verify blockchain and run validation.
8. Use the tamper demonstration on a non-genesis block. Verification should fail.
9. Reset the demo ledger after the demonstration if you want a clean start.

## Syllabus mapping

| Faculty syllabus area | How this project demonstrates it |
|---|---|
| Blockchain technology | Blocks, previous hashes, tamper evidence, verification |
| Requirements and benefits | Multi-party traceability, shared audit trail, integrity |
| Trust, security, availability, verifiability | Hash checks, append-only event history, limitations discussion |
| Blockchain ecosystems | Applications and Bitcoin comparison in report/viva; no exchange or real mining network |
| Cryptography | SHA-256 hash function |
| Public vs private blockchain | Conceptual comparison; this app is a local simulation |
| Hashing | SHA-256 of canonical block data |
| Heap / graph | Not required for this use case; do not add unrelated algorithms just to tick syllabus words |
| Blockchain mining | Small Proof-of-Work nonce search |
| Solo and pool mining | Explain conceptually; not implemented |
| Byzantine Generals Problem | Explain why multiple nodes need agreement; not implemented |
| Hyperledger | Explain permissioned blockchain conceptually; not installed or used |
| Applications | Medical information / vaccine logistics traceability |

## Important academic explanation
A real decentralized blockchain requires multiple nodes, independent copies and a consensus protocol. This project models the data structure and Proof-of-Work process on one machine to keep the implementation within the taught Python/Streamlit scope. Present it as a **blockchain simulation/prototype**, not as a deployed decentralized network.

## File structure

```text
ColdChainRegistry_Streamlit/
├── app.py
├── blockchain.py
├── demo.py
├── requirements.txt
├── README.md
├── PROJECT_SCOPE.md
├── data/
│   └── (ledger.json is created automatically)
└── tests/
    ├── test_blockchain.py   (22 backend tests)
    └── test_app.py          (7 UI workflow tests)
```

## Run the tests
```powershell
python -m unittest discover -s tests -v
```
The UI tests use a temporary ledger file (via the `COLDCHAIN_LEDGER` environment variable), so they never touch `data/ledger.json`.

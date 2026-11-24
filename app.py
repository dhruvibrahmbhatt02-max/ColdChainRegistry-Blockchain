"""ColdChainRegistry - Streamlit front end (plain-language, interactive version)."""
import hashlib
import json
import time
from datetime import date, datetime

import streamlit as st

from blockchain import ColdChainBlockchain, describe_transaction
from demo import load_demo_scenario

st.set_page_config(page_title="ColdChainRegistry", page_icon="🌡", layout="wide")

st.markdown("""
<style>
.block-container {padding-top:1.5rem; max-width:1300px}
[data-testid="stMetric"] {background:var(--secondary-background-color);padding:14px 16px;
    border:1px solid rgba(128,128,128,.25);border-radius:12px}
div.stButton>button {border-radius:8px;font-weight:600}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_ledger():
    return ColdChainBlockchain()


ledger = get_ledger()

# ----------------------------------------------------------------------------- constants
ROLES = ["Regulator", "Manufacturer", "Distributor", "Clinic", "Sensor Operator"]

PERMISSIONS = {
    "register": ["Manufacturer", "Regulator"],
    "temperature": ["Sensor Operator", "Regulator"],
    "custody": ["Regulator", "Manufacturer", "Distributor", "Clinic"],
    "regulator": ["Regulator"],
}

ROLE_HELP = {
    "Regulator": "Reviews problems: release, recall or mark batches dispensed. Can also register batches and log temperatures.",
    "Manufacturer": "Makes the vaccine: registers new batches and hands them to a distributor.",
    "Distributor": "Moves vaccines: receives batches and passes them on to a clinic.",
    "Clinic": "Holds vaccines for patients: can hand a batch on (a regulator records dispensing).",
    "Sensor Operator": "Checks the fridge/truck thermometer and records temperature readings.",
}

STATUS_STYLE = {
    "Active": ("🟢", "Safe to use"),
    "Quarantined": ("🟠", "On hold - a temperature problem was recorded"),
    "Recalled": ("🔴", "Recalled - must not be used"),
    "Dispensed": ("🔵", "Given out to patients"),
}

EVENT_LABEL = {
    "GENESIS": "🏁 Start", "BATCH_REGISTERED": " Registered", "TEMPERATURE_RECORDED": "🌡 Temperature",
    "CUSTODY_TRANSFERRED": "🚚 Custody", "BATCH_RELEASED": "🔓 Released", "BATCH_RECALLED": " Recalled",
    "BATCH_DISPENSED": "💉 Dispensed",
}

PAGES = ["🏠 Home", "📘 How it works", " Register batch", "🌡 Record temperature",
         "🚚 Transfer custody", "🛡 Regulator actions", "🔎 Track a batch",
         " Verify & tamper test", "📜 Audit history"]


# ----------------------------------------------------------------------------- helpers
def goto(page_name):
    st.session_state.page = page_name


def flash(kind, message, code=None):
    """Remember a message across st.rerun() so the user actually sees it."""
    st.session_state.flash = (kind, message, code)


def show_flash():
    item = st.session_state.pop("flash", None)
    if item:
        kind, message, code = item
        getattr(st, kind)(message)
        if code:
            st.caption("Block fingerprint (SHA-256 hash):")
            st.code(code, language="text")


def allowed(action):
    return st.session_state.actor in PERMISSIONS[action]


def require_role(action):
    if not allowed(action):
        names = " or ".join(PERMISSIONS[action])
        st.error(f"The **{st.session_state.actor}** role cannot do this. Switch to **{names}** in the sidebar.")
        return False
    return True


def role_notice(action):
    if not allowed(action):
        names = " or ".join(PERMISSIONS[action])
        st.warning(f"You are acting as **{st.session_state.actor}**. This page is for **{names}** - "
                   "change the participant in the sidebar to continue.")


def add_event(event, success_text):
    block = ledger.add_transaction(event)
    flash("success", f" {success_text} It was saved permanently in Block #{block['index']}.", block["hash"])
    st.toast(f"Saved in Block #{block['index']}", icon="")
    st.rerun()


def select_batch(label="Choose a vaccine batch"):
    ids = ledger.batch_ids()
    if not ids:
        st.info("No vaccine batches yet. Register one, or load the sample data from the Home page.")
        return None
    return st.selectbox(label, ids, key=f"{label}_{st.session_state.page}")


def status_badge(status):
    icon, _ = STATUS_STYLE.get(status, ("", ""))
    return f"{icon} {status}"


def status_banner(batch):
    icon, meaning = STATUS_STYLE[batch["status"]]
    text = f"{icon} **{batch['batch_id']} - {batch['status']}:** {meaning}."
    {"Active": st.success, "Quarantined": st.warning, "Recalled": st.error,
     "Dispensed": st.info}[batch["status"]](text)


def expiry_info(batch):
    try:
        days = (date.fromisoformat(batch["expiry_date"]) - date.today()).days
    except (ValueError, TypeError):
        return False, None
    return days < 0, days


def fmt_time(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return str(iso)


def short(h, n=12):
    return h[:n] + "…"


# ----------------------------------------------------------------------------- sidebar
if "actor" not in st.session_state:
    st.session_state.actor = "Regulator"
if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

with st.sidebar:
    st.title("🌡 ColdChainRegistry")
    st.caption("Tamper-evident vaccine cold-chain diary")
    st.subheader("1 · Who are you pretending to be?")
    st.selectbox("Demo participant", ROLES, key="actor",
                 help="A classroom simulation - not a real login.")
    st.info(ROLE_HELP[st.session_state.actor])
    st.subheader("2 · Where do you want to go?")
    st.radio("Pages", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    st.caption("Local JSON ledger · SHA-256 · Proof of Work\n\nSingle-computer simulation.")

page = st.session_state.page

valid, validation_message = ledger.is_valid()
batches = [b for b in (ledger.find_batch(bid) for bid in ledger.batch_ids()) if b is not None]

st.title("ColdChainRegistry")
st.caption("Follow a vaccine batch from factory to clinic - and prove its record has not been changed.")
if not valid:
    st.error("🚨 BLOCKCHAIN INTEGRITY WARNING: " + validation_message +
             " Open **Verify & tamper test** to see which block was changed.")
show_flash()

# ----------------------------------------------------------------------------- HOME
if page == "🏠 Home":
    st.subheader("Supply-chain overview")
    if not batches:
        with st.container(border=True):
            st.markdown("### 👋 New here? Start in one click")
            st.write("The ledger is empty. Load three fictional batches that show a temperature "
                     "problem, a healthy delivery and a reviewed-and-released batch.")
            c1, c2 = st.columns(2)
            if c1.button("🎬 Load sample demo data", type="primary", width="stretch"):
                added = load_demo_scenario(ledger)
                flash("success", f"Loaded sample batches: {', '.join(added)}.")
                st.rerun()
            c2.button("📘 Learn how it works first", width="stretch", on_click=goto, args=("📘 How it works",))
    else:
        counts = {s: sum(b["status"] == s for b in batches) for s in STATUS_STYLE}
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total batches", len(batches))
        c2.metric("🟢 Safe", counts["Active"], help="Active: safe to use")
        c3.metric("🟠 On hold", counts["Quarantined"])
        c4.metric("🔴 Recalled", counts["Recalled"])
        c5.metric("🔵 Dispensed", counts["Dispensed"])
        c6.metric("Blocks", len(ledger.chain), help="Each saved action becomes one block.")

        needs_attention = [b for b in batches if b["status"] == "Quarantined"]
        expired = [b for b in batches if expiry_info(b)[0] and b["status"] in ("Active", "Quarantined")]
        for b in needs_attention:
            st.warning(f"🟠 **{b['batch_id']}** is on hold after an out-of-range temperature. "
                       "A regulator must review it (Regulator actions).")
        for b in expired:
            st.error(f" **{b['batch_id']}** is past its expiry date ({b['expiry_date']}).")
        if not needs_attention and not expired:
            st.success("Nothing needs attention right now.")

    left, right = st.columns([1.6, 1])
    with left:
        st.subheader("Vaccine batch register")
        if batches:
            st.dataframe([{
                "Batch": b["batch_id"], "Vaccine": b["vaccine_name"], "Status": status_badge(b["status"]),
                "Held by": b["custodian"], "Safe range": f'{b["min_temp"]:g}–{b["max_temp"]:g} C',
                "Last reading": "—" if b["last_temperature"] is None else f'{b["last_temperature"]:.1f} C',
                "Expires": b["expiry_date"],
            } for b in batches], width="stretch", hide_index=True)
        else:
            st.info("No batches yet.")
    with right:
        st.subheader("Is the record trustworthy?")
        if valid:
            st.success(" Yes - no block has been altered.")
        else:
            st.error(" No - the record has been changed.")
        st.caption(f"{len(ledger.chain)} blocks checked · SHA-256 · difficulty {ledger.difficulty}")

    st.subheader("What would you like to do?")
    q1, q2, q3, q4 = st.columns(4)
    q1.button(" Register a batch", width="stretch", on_click=goto, args=(" Register batch",))
    q2.button("🌡 Record a temperature", width="stretch", on_click=goto, args=("🌡 Record temperature",))
    q3.button("🔎 Track a batch", width="stretch", on_click=goto, args=("🔎 Track a batch",))
    q4.button(" Verify the ledger", width="stretch", on_click=goto, args=(" Verify & tamper test",))
    st.caption("Educational simulation: this ledger runs on one computer. It shows hash-linked blocks and "
               "tamper detection, not a distributed peer-to-peer network.")

# ----------------------------------------------------------------------------- HOW IT WORKS
elif page == "📘 How it works":
    st.subheader("How it works - no technical background needed")
    st.write("Imagine a **notebook where every page is stamped with a fingerprint of the page before it**. "
             "If anyone secretly rewrites an old page, its fingerprint changes and the notebook exposes the edit. "
             "That notebook is a *blockchain*.")
    c1, c2, c3, c4 = st.columns(4)
    for col, (title, text) in zip([c1, c2, c3, c4], [
        ("1 · Something happens", "A batch is registered, a temperature is logged, custody changes."),
        ("2 · It becomes a block", "The event is written on a new page (block) with the time."),
        ("3 · The block is sealed", "A SHA-256 fingerprint (hash) is made, including the previous page's fingerprint."),
        ("4 · Anyone can check", "Recalculate every fingerprint. A mismatch means history was edited."),
    ]):
        with col.container(border=True):
            st.markdown(f"**{title}**")
            st.write(text)

    st.subheader("🔬 Try it: the fingerprint (hash)")
    text = st.text_input("Type anything", "ColdChainRegistry", key="hash_text")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    st.code(digest, language="text")
    st.caption("Change a single letter or add a space - the whole fingerprint changes completely. "
               "The same text always gives the same fingerprint.")

    st.subheader(" Try it: Proof of Work (mining)")
    st.write("To seal a block, the computer keeps trying numbers (the *nonce*) until the fingerprint starts "
             "with a required number of zeroes. More zeroes = more guesses.")
    m1, m2 = st.columns([1, 2])
    diff = m1.slider("Difficulty (leading zeroes)", 1, 4, 2)
    block_text = m2.text_input("Pretend block content", "VAX-001 registered")
    if st.button(" Start mining", type="primary"):
        target, nonce, t0 = "0" * diff, 0, time.perf_counter()
        while True:
            h = hashlib.sha256(f"{block_text}{nonce}".encode()).hexdigest()
            if h.startswith(target):
                break
            nonce += 1
        st.success(f"Found after **{nonce + 1:,} attempts** in {time.perf_counter() - t0:.3f} s.")
        st.code(f"nonce = {nonce}\nhash  = {h}", language="text")
        st.caption("This app uses difficulty 2 so saving feels instant. Real networks use far higher difficulty.")

    st.subheader("👥 Who can do what")
    st.dataframe([{"Role": r, "Can do": ROLE_HELP[r]} for r in ROLES], width="stretch", hide_index=True)

    st.subheader("Batch statuses")
    for s, (icon, meaning) in STATUS_STYLE.items():
        st.write(f"{icon} **{s}** - {meaning}")
    st.caption("A temperature outside the safe range puts an Active batch on hold. A later normal reading does "
               "NOT release it - only the regulator can. Recalled and Dispensed are final.")

    with st.expander("📖 Glossary"):
        st.markdown("""
- **Block** - one saved action plus a timestamp and fingerprints.
- **Hash / fingerprint** - a 64-character code (SHA-256) made from a block's content.
- **Previous hash** - the fingerprint of the block before; this is the "chain".
- **Nonce** - the number tried over and over during mining.
- **Proof of Work** - the guessing game that seals a block.
- **Genesis block** - the very first block.
- **Custody** - who is physically responsible for the batch.
- **Quarantine** - batch on hold until a regulator reviews it.
""")
    with st.expander(" What this app is NOT"):
        st.markdown("""
- Not a network of many computers - it is one ledger file on one computer.
- The role selector is **not** a secure login.
- Temperatures are typed in by hand; there is no real thermometer, so the app cannot prove a reading is true.
- Changing the file is not impossible - it is **detectable**.
""")

# ----------------------------------------------------------------------------- REGISTER
elif page == " Register batch":
    st.subheader("Register a new vaccine batch")
    st.write("The manufacturer records what the batch is and what temperature is safe. "
             "The registration is sealed into a new block.")
    role_notice("register")
    with st.form("register_batch"):
        col1, col2 = st.columns(2)
        with col1:
            batch_id = st.text_input("Unique batch ID", placeholder="VAX-001", help="Must not already exist.")
            vaccine = st.text_input("Vaccine name", placeholder="Example Vaccine")
            manufacturer = st.text_input("Manufacturer / organisation", value="Demo Pharma Ltd")
        with col2:
            min_temp = st.number_input("Lowest safe temperature (C)", value=2.0, step=0.5)
            max_temp = st.number_input("Highest safe temperature (C)", value=8.0, step=0.5)
            expiry = st.date_input("Expiry date", min_value=date.today())
        submitted = st.form_submit_button("Register and seal into a block", type="primary",
                                          disabled=not allowed("register"))
    st.caption("The 2–8 C range is only a demonstration default. Real storage limits come from the product's official guidance.")
    if submitted:
        if not require_role("register"):
            pass
        elif not batch_id.strip() or not vaccine.strip():
            st.error("Please enter both a batch ID and a vaccine name.")
        elif batch_id.strip() in ledger.batch_ids():
            st.error(f"Batch ID **{batch_id.strip()}** already exists. Choose a different ID.")
        elif min_temp >= max_temp:
            st.error("The lowest safe temperature must be below the highest safe temperature.")
        else:
            add_event({
                "type": "BATCH_REGISTERED", "batch_id": batch_id.strip(),
                "vaccine_name": vaccine.strip(), "manufacturer": manufacturer.strip(),
                "min_temp": min_temp, "max_temp": max_temp,
                "expiry_date": expiry.isoformat(), "actor": st.session_state.actor,
            }, f"Batch {batch_id.strip()} registered.")

# ----------------------------------------------------------------------------- TEMPERATURE
elif page == "🌡 Record temperature":
    st.subheader("Record a temperature reading")
    st.write("Type what the thermometer shows. A reading outside the safe range automatically puts the batch on hold.")
    role_notice("temperature")
    batch_id = select_batch()
    if batch_id:
        batch = ledger.find_batch(batch_id)
        status_banner(batch)
        a, b, c = st.columns(3)
        a.metric("Safe range", f'{batch["min_temp"]:g} to {batch["max_temp"]:g} C')
        b.metric("Last reading", "—" if batch["last_temperature"] is None else f'{batch["last_temperature"]:.1f} C')
        c.metric("Held by", batch["custodian"])

        temperature = st.number_input("Temperature reading (C)", value=5.0, step=0.1, format="%.1f",
                                      key=f"temp_{batch_id}")
        inside = batch["min_temp"] <= round(temperature, 1) <= batch["max_temp"]
        if inside:
            st.success(f" {temperature:.1f} C is within the safe range.")
        elif batch["status"] == "Active":
            st.warning(f"🚨 {temperature:.1f} C is OUTSIDE the safe range - saving this will put the batch on hold.")
        else:
            st.warning(f"🚨 {temperature:.1f} C is outside the safe range (the batch is already {batch['status']}).")
        note = st.text_input("Note (optional)", placeholder="Routine cold storage check", key=f"note_{batch_id}")
        if st.button("Record temperature and seal block", type="primary", disabled=not allowed("temperature")):
            if require_role("temperature"):
                add_event({
                    "type": "TEMPERATURE_RECORDED", "batch_id": batch_id,
                    "temperature": round(temperature, 1), "note": note,
                    "actor": st.session_state.actor, "within_range": bool(inside),
                }, f"{temperature:.1f} C recorded for {batch_id}.")

        if batch["readings"]:
            st.subheader("Temperature history")
            n = len(batch["readings"])
            st.line_chart({
                "Reading (C)": [r["temperature"] for r in batch["readings"]],
                "Highest safe": [batch["max_temp"]] * n,
                "Lowest safe": [batch["min_temp"]] * n,
            })
            st.caption("Readings are shown oldest to newest; the flat lines mark the safe range.")
        else:
            st.info("No readings have been recorded for this batch yet.")

# ----------------------------------------------------------------------------- CUSTODY
elif page == "🚚 Transfer custody":
    st.subheader("Hand a batch to the next participant")
    st.write("Custody means who is responsible for the batch right now. Only the **current holder** can hand it on.")
    batch_id = select_batch()
    if batch_id:
        batch = ledger.find_batch(batch_id)
        status_banner(batch)
        flow = ["Manufacturer", "Distributor", "Clinic"]
        cur = batch["custodian"]
        st.markdown("**Journey:** " + "  →  ".join(f"**🟢 {r}**" if r == cur else r for r in flow))
        st.write(f"Currently held by: **{cur}**")
        if st.session_state.actor != cur:
            st.warning(f"To hand this batch on, switch the sidebar participant to **{cur}**.")
        if batch["status"] != "Active":
            st.warning("Only Active batches can be transferred.")
        options = [r for r in ["Distributor", "Clinic"] if r != cur]
        receiver = st.selectbox("Hand over to", options)
        ready = allowed("custody") and batch["status"] == "Active" and st.session_state.actor == cur
        if st.button("Record custody transfer", type="primary", disabled=not ready):
            if not require_role("custody"):
                pass
            elif batch["status"] != "Active":
                st.error("Only Active batches can be transferred.")
            elif batch["custodian"] != st.session_state.actor:
                st.error("Only the current custodian can hand the batch on.")
            else:
                add_event({
                    "type": "CUSTODY_TRANSFERRED", "batch_id": batch_id,
                    "from": st.session_state.actor, "to": receiver,
                    "actor": st.session_state.actor, "note": "Classroom custody handover record",
                }, f"{batch_id} handed from {st.session_state.actor} to {receiver}.")
        st.caption("Simplification: the handover is recorded in one step. A real system would also need the "
                   "receiver to confirm and digitally sign for it.")

# ----------------------------------------------------------------------------- REGULATOR
elif page == "🛡 Regulator actions":
    st.subheader("Regulator controls")
    if not allowed("regulator"):
        st.warning("These controls are only for the **Regulator**. Switch participant in the sidebar.")
    else:
        batch_id = select_batch()
        if batch_id:
            batch = ledger.find_batch(batch_id)
            status_banner(batch)
            expired, days = expiry_info(batch)
            if expired:
                st.error(f" This batch expired on {batch['expiry_date']}.")
            reason = st.text_input("Reason for your decision", value="Reviewed by regulator")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Release from quarantine**")
                st.caption("Use after reviewing a temperature problem and judging the batch safe.")
                if st.button("🔓 Release", type="primary", width="stretch",
                             disabled=batch["status"] != "Quarantined"):
                    add_event({"type": "BATCH_RELEASED", "batch_id": batch_id,
                               "actor": "Regulator", "reason": reason}, f"{batch_id} released.")
            with c2:
                st.markdown("**Recall batch**")
                st.caption("Permanently marks the batch unsafe. This cannot be undone.")
                if st.button(" Recall", width="stretch",
                             disabled=batch["status"] in ("Recalled", "Dispensed")):
                    add_event({"type": "BATCH_RECALLED", "batch_id": batch_id,
                               "actor": "Regulator", "reason": reason}, f"{batch_id} recalled.")
            with c3:
                st.markdown("**Mark as dispensed**")
                st.caption("Only for Active, in-date batches held by the Clinic.")
                can_dispense = batch["status"] == "Active" and batch["custodian"] == "Clinic" and not expired
                if st.button("💉 Dispensed", width="stretch", disabled=not can_dispense):
                    add_event({"type": "BATCH_DISPENSED", "batch_id": batch_id,
                               "actor": "Regulator"}, f"{batch_id} marked as dispensed.")
                if not can_dispense:
                    if batch["status"] != "Active":
                        st.caption("🔒 Batch must be Active.")
                    elif batch["custodian"] != "Clinic":
                        st.caption("🔒 Batch must first be handed to the Clinic.")
                    elif expired:
                        st.caption("🔒 Expired batches cannot be dispensed.")

# ----------------------------------------------------------------------------- TRACK
elif page == "🔎 Track a batch":
    st.subheader("Track one batch from start to now")
    batch_id = select_batch()
    if batch_id:
        batch = ledger.find_batch(batch_id)
        status_banner(batch)
        expired, days = expiry_info(batch)
        if expired:
            st.error(f" Expired on {batch['expiry_date']}.")
        elif days is not None and days <= 30:
            st.warning(f" Expires in {days} day(s) ({batch['expiry_date']}).")
        a, b, c, d = st.columns(4)
        a.metric("Vaccine", batch["vaccine_name"])
        b.metric("Held by", batch["custodian"])
        c.metric("Safe range", f'{batch["min_temp"]:g}–{batch["max_temp"]:g} C')
        d.metric("Expires", batch["expiry_date"])

        st.subheader("Journey timeline")
        history = ledger.batch_history(batch_id)
        for tx in history:
            icon = EVENT_LABEL.get(tx["type"], "•").split(" ")[0]
            with st.container(border=True):
                st.markdown(f"{icon} **{describe_transaction(tx)}**")
                st.caption(f"{fmt_time(tx.get('timestamp', tx['block_time']))} · saved in Block #{tx['block_index']} · "
                           f"fingerprint {short(tx['block_hash'])}")
        if batch["readings"]:
            st.subheader("Temperature history")
            n = len(batch["readings"])
            st.line_chart({"Reading (C)": [r["temperature"] for r in batch["readings"]],
                           "Highest safe": [batch["max_temp"]] * n, "Lowest safe": [batch["min_temp"]] * n})

# ----------------------------------------------------------------------------- VERIFY
elif page == " Verify & tamper test":
    st.subheader("Is the record still trustworthy?")
    st.write("The app recalculates every block's fingerprint and checks three things: "
             "**1)** the content still matches its fingerprint, **2)** each block points to the one before, "
             "**3)** each block carries valid Proof of Work.")
    if st.button("🔍 Run verification now", type="primary"):
        ok, msg = ledger.is_valid()
        (st.success if ok else st.error)((" " if ok else " ") + msg)
    elif valid:
        st.success(" " + validation_message)
    else:
        st.error(" " + validation_message)

    details = ledger.verify_details()
    st.subheader("The chain, block by block")
    any_bad = any(not r["ok"] for r in details)
    show_all = len(details) <= 10 or any_bad or st.checkbox(f"Show all {len(details)} blocks (default: latest 10)")
    shown = details if show_all else details[-10:]
    for row_start in range(0, len(shown), 5):
        row = shown[row_start:row_start + 5]
        cols = st.columns(5)
        for col, r in zip(cols, row):
            blk = ledger.chain[r["index"]]
            kind = blk["transactions"][0].get("type", "?") if blk["transactions"] else "?"
            with col.container(border=True):
                st.markdown(f"**Block {r['index']}** {'' if r['ok'] else ''}")
                st.caption(EVENT_LABEL.get(kind, kind))
                st.code(short(blk.get("hash", ""), 10), language="text")
                if not r["hash_ok"]:
                    st.caption("🚨 content changed")
                elif not r["link_ok"]:
                    st.caption("🚨 link broken")
                elif not r["pow_ok"]:
                    st.caption("🚨 invalid proof of work")
                else:
                    st.caption("🔗 linked to previous" if r["index"] else "🏁 first block")
    st.caption(f"{len(ledger.chain)} blocks · difficulty {ledger.difficulty}")

    st.divider()
    st.subheader("🧪 Tamper demonstration")
    st.markdown("**Step 1** - secretly edit a saved block. **Step 2** - watch verification catch it. "
                "**Step 3** - undo the edit.")
    non_genesis = [b["index"] for b in ledger.chain if b["index"] > 0]
    if non_genesis:
        c1, c2 = st.columns(2)
        with c1:
            chosen = st.selectbox("Block to tamper with", non_genesis)
            if st.button("😈 Secretly edit this block"):
                ledger.tamper_block_for_demo(chosen)
                flash("error", f"Block {chosen} was edited WITHOUT updating its fingerprint. "
                               "Verification now fails - look for the  block below.")
                st.rerun()
        with c2:
            st.write("Put things back after the demo:")
            if st.button(" Undo the demo edit", disabled=valid):
                n = ledger.undo_demo_tampering()
                flash("success", f"Removed {n} demo edit(s). The record is valid again.")
                st.rerun()
    else:
        st.info("Save at least one action first (for example load the demo data on Home).")

    st.divider()
    with st.expander("🗑 Danger zone - reset the whole ledger"):
        st.warning("This deletes every batch and event and starts again from a new first block.")
        sure = st.checkbox("I understand all records will be deleted")
        if st.button("Reset demo ledger", disabled=not sure):
            ledger.reset()
            flash("success", "Demo ledger reset. Only the first block remains.")
            st.rerun()

# ----------------------------------------------------------------------------- AUDIT
elif page == "📜 Audit history":
    st.subheader("Complete audit history")
    st.write("Every saved action, in order, with the block that holds it.")
    f1, f2 = st.columns(2)
    batch_filter = f1.selectbox("Show batch", ["All batches"] + ledger.batch_ids())
    type_filter = f2.selectbox("Show event type", ["All events"] + [k for k in EVENT_LABEL if k != "GENESIS"],
                               format_func=lambda k: k if k == "All events" else EVENT_LABEL[k])
    rows = []
    for block in ledger.chain:
        for tx in block["transactions"]:
            if batch_filter != "All batches" and tx.get("batch_id") != batch_filter:
                continue
            if type_filter != "All events" and tx.get("type") != type_filter:
                continue
            rows.append({
                "Block": block["index"], "Event": EVENT_LABEL.get(tx.get("type"), tx.get("type")),
                "What happened": describe_transaction(tx), "Batch": tx.get("batch_id", "—"),
                "Who": tx.get("actor", "—"), "When": fmt_time(tx.get("timestamp", block["timestamp"])),
                "Block hash": short(block["hash"], 16), "Previous hash": short(block["previous_hash"], 16),
                "Nonce": block["nonce"],
            })
    st.caption(f"{len(rows)} record(s) shown")
    st.dataframe(rows, width="stretch", hide_index=True)
    with st.expander("View raw block data (technical)"):
        st.json(ledger.chain)
    st.download_button(" Download blockchain JSON", json.dumps({"chain": ledger.chain}, indent=2),
                       file_name="coldchain_ledger.json", mime="application/json")

st.divider()
st.caption("ColdChainRegistry is an educational simulation. It does not connect to physical IoT sensors, "
           "a public blockchain, or a real vaccine supply chain.")

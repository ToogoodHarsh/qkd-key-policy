"""Interactive dashboard.  Start it with:  python -m streamlit run app.py   (or double-click run.bat)"""
import os
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from animation import animation_html
from keyrate import attack_qber, link_qber, secret_rate
from params import Params
from policies import LABELS, NAMES
from simulator import simulate

RESULTS = Path(__file__).parent / "results"

st.set_page_config(page_title="QKD Key-Usage Simulator", page_icon="🔐", layout="wide")


def scenario(km, traffic, wind, attack_on, attack_start, attack_len, strength):
    return replace(Params(), km=km, traffic_scale=traffic, wind_sigma=wind, attack_start=attack_start,
                   attack_len=attack_len if attack_on else 0, attack_strength=strength)


def code_version():
    """Changes whenever a file behind the cached results changes, so an open dashboard never shows stale output."""
    here = Path(__file__).parent
    files = [here / "web" / "animation.html", *here.glob("*.py")]
    return max(f.stat().st_mtime for f in files)


@st.cache_data(show_spinner="Simulating one hour for all five policies ...")
def run_scenario(km, traffic, wind, attack_on, attack_start, attack_len, strength, seed, version):
    p = scenario(km, traffic, wind, attack_on, attack_start, attack_len, strength)
    runs = {name: simulate(name, p, seed, record=True) for name in NAMES}
    rows = [{
        "Policy": LABELS[name],
        "Failed messages": f"{run.summary['failed']:,}",
        "Exposed messages": f"{run.summary['exposed']:,}",
        "Control on OTP": f"{run.summary['otp_share_control']:.1%}",
        "State on OTP": f"{run.summary['otp_share_state']:.1%}",
        "Market on OTP": f"{run.summary['otp_share_market']:.1%}",
        "All on OTP": f"{run.summary['otp_share']:.1%}",
        "Wasted keys (kbit)": f"{run.summary['wasted_kbit']:,.0f}",
        "Lowest tank level (kbit)": f"{run.summary['min_stock'] / 1000:,.1f}",
    } for name, run in runs.items()]
    return animation_html(p, runs), pd.DataFrame(rows)


# ---------------------------------------------------------------- sidebar: the scenario
with st.sidebar:
    st.header("Scenario")
    km = st.slider("Fibre length (km)", 1, 100, 30, 1)
    traffic = st.select_slider("Grid traffic", options=[0.5, 1.0, 1.5, 2.0, 3.0], value=1.0,
                               format_func=lambda v: f"{v:g}x normal")
    wind = st.slider("Key-rate swings (wind on the fibre)", 0.0, 0.3, 0.1, 0.05)
    st.divider()
    attack_on = st.toggle("Eavesdropping attack", value=True)
    attack_start = st.slider("Attack starts at (s)", 0, 3300, 1200, 60, disabled=not attack_on)
    attack_len = st.slider("Attack length (s)", 30, 1200, 300, 30, disabled=not attack_on)
    strength = st.slider("Share of photons Eve intercepts", 0.1, 1.0, 1.0, 0.1, disabled=not attack_on,
                         help="Each intercepted photon has a 25% chance of an error. Above 11% QBER the keys "
                              "are discarded, so no new keys arrive.")
    st.divider()
    seed = int(st.number_input("Random seed (same seed = same traffic)", 0, 999, 1))
    st.caption("Software simulation using the models of the six reference papers. No quantum hardware.")

p = scenario(km, traffic, wind, attack_on, attack_start, attack_len, strength)
demand = sum(c.rate for c in p.classes) * p.traffic_scale * p.otp_cost

# ---------------------------------------------------------------- header
st.title("Rate-Aware Key-Usage Policy for a QKD-Secured Grid Link")
st.write("One hour of a smart-grid link, second by second. QKD fills a **key tank**; grid messages use the keys. "
         "Five policies decide when a message uses a **One-Time Pad** and when it falls back to **AES-256**.")
c1, c2, c3, c4 = st.columns(4)
c1.metric("New secret keys", f"{secret_rate(p):,.0f} bit/s")
c2.metric("Needed if all traffic used OTP", f"{demand:,.0f} bit/s")
c3.metric("QBER, normal", f"{link_qber(p):.1%}")
c4.metric("QBER, under attack", f"{attack_qber(p, strength):.1%}" if attack_on else "no attack",
          help="Above 11% the keys are discarded (BB84 limit).")

# how many messages per second the keys can cover with OTP, and which classes that is enough for
supply, wanted, fits = secret_rate(p), 0.0, []
for c in sorted(p.classes, key=lambda c: -c.priority):
    wanted += c.rate * p.traffic_scale * p.otp_cost
    fits.append(f"{c.name.capitalize()} {'✅' if wanted <= supply else '❌'}")
st.info(f"At **{km} km** the keys can protect about **{supply / p.otp_cost:,.0f} messages per second** with OTP "
        f"({p.otp_cost} key bits each). On average that is enough for: **{'  ·  '.join(fits)}**. "
        "Classes marked ❌ need AES-256 whenever the tank runs low.")

html, table = run_scenario(km, traffic, wind, attack_on, attack_start, attack_len, strength, seed, code_version())
live, this_run, charts, how, crypto = st.tabs(
    ["🎬 Live simulator", "📋 This run", "📈 Experiments", "🧠 How it works", "🔒 Real encryption"])

# ---------------------------------------------------------------- tab 1: the animation
with live:
    st.caption("Press **Play**, or **Jump to attack**; pick **1x** to watch in real time. Click the timeline to move "
               "in time. Under each tank, every message class (Control, State, Market) shows a dot with the "
               "protection it uses right now, and the share of its messages sent with OTP so far. "
               "The photon picture is an illustration; every number comes from the simulation.")
    components.html(html, height=800, scrolling=True)

# ---------------------------------------------------------------- tab 2: numbers of this run
with this_run:
    st.subheader("Result of this run")
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption("One run with the settings on the left. The report uses the mean of 30 runs for every scenario.")
    st.markdown(
        "- **Failed**: messages that could not be protected at all.\n"
        "- **Exposed**: messages sent with a key that was used twice (Qian-style tiers only).\n"
        "- **Control on OTP**: share of the most important messages that got the strongest protection.\n"
        "- **Wasted keys**: QKD keys lost because the tank was already full.")

# ---------------------------------------------------------------- tab 3: saved experiment charts
with charts:
    figures = [
        ("fig_switching.png", "Our rule at 30 km: market goes to AES-256 first, then state; control keeps OTP longest."),
        ("fig_classes.png", "OTP share of each class versus distance: fixed reserve next to our rule (mean of 30 runs)."),
        ("fig_packets.png", "How far each class can stay on OTP: 21 km for all, 27 km for control + state, "
                            "66 km for control alone."),
        ("fig_timeline.png", "Key tank of each policy over one hour at 30 km (grey band = attack)."),
        ("fig_distance.png", "All five policies at 5 to 40 km, with a 300 s attack (mean of 30 runs)."),
        ("fig_attack.png", "Longer attacks at 30 km (mean of 30 runs)."),
        ("fig_robustness.png", "Thresholds tuned at normal traffic, then tested when traffic grows."),
        ("fig_tuning.png", "Choosing the fixed reserve and our safe-time multiplier on separate runs."),
    ]
    if not (RESULTS / figures[0][0]).exists():
        st.info("Run  python experiments.py  once to create the charts.")
    for name, caption in figures:
        if (RESULTS / name).exists():
            st.image(str(RESULTS / name), caption=caption, use_column_width=True)

# ---------------------------------------------------------------- tab 4: explanation
with how:
    st.subheader("The idea in simple words")
    st.write("Think of the key buffer as a **water tank**. QKD is a tap that slowly fills it; the tap runs slower on "
             "a long fibre and stops when an eavesdropper is detected. **OTP takes a full bucket per message** "
             "(as many key bits as the message). **AES-256 takes one small cup per minute** for all messages. "
             "Our rule watches how fast the tank is emptying and moves the least important messages to AES-256 "
             "first, so control messages stay on OTP as long as possible. It never lets the tank run dry and "
             "never reuses a key.")
    st.subheader("The five policies")
    st.table(pd.DataFrame([
        ["OTP-only", "Always OTP. Messages fail when keys run out.", "Benchmark"],
        ["AES-only", "Always AES-256 with a fresh QKD key every 60 s.", "Benchmark"],
        ["Fixed reserve", "Switch to AES when fewer than 30 keys are left.", "Alshowkan (2022), p. 9"],
        ["Qian-style tiers", "When keys are scarce, one key is used for two messages.", "Qian (2025), p. 5"],
        ["Rate-aware (ours)", "Predict the seconds until the tank is empty for each class; below the class's "
                              "safe time, use AES-256.", "This project"],
    ], columns=["Policy", "Rule", "Source"]))
    st.subheader("Our rule in pseudo-code")
    st.code(
        "for each message class, most important first:\n"
        "    demand    = OTP bits/s of this class and every more important class\n"
        "    drain     = demand - key bits/s coming from QKD\n"
        "    time_left = keys in tank / drain             (infinite if drain <= 0)\n\n"
        "    if tank is almost full:                          use OTP      (keys would be wasted)\n"
        "    elif tank < 512 bits or time_left < safe_time:   use AES-256  (fresh QKD key every 60 s)\n"
        "    elif class was on AES and time_left < 1.5 x safe_time:  stay on AES\n"
        "    else:                                            use OTP\n\n"
        "safe_time: control 20 s, state estimation 60 s, power market 120 s", language="text")
    st.subheader("Files of the program")
    st.markdown(
        "| File | Working |\n|---|---|\n"
        "| `params.py` | every number, with its paper and page |\n"
        "| `keyrate.py` | key bits made each second (Tang Eq. 4-6, 11, 15, Table I) |\n"
        "| `traffic.py` | messages each second for control, state and market (Qian p. 8) |\n"
        "| `pool.py` | the key tank (Zheng Eq. 1) |\n"
        "| `policies.py` | the five policies |\n"
        "| `simulator.py` | the one-second loop |\n"
        "| `metrics.py` | failed, exposed, OTP share, wasted keys |\n"
        "| `experiments.py` | every scenario, 30 runs each |\n"
        "| `app.py`, `animation.py`, `web/` | this dashboard |")

# ---------------------------------------------------------------- tab 5: real encryption of one grid message
def per_message_us(fn, n=3000):
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - start) / n * 1e6


def xor(a, b):
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big")


def hex_lines(data, width=48):
    h = data.hex()
    return "\n".join(h[i:i + width] for i in range(0, len(h), width))


with crypto:
    st.write("A real grid command encrypted both ways with Python's `cryptography` library. The keys here come from "
             "the computer's random generator, standing in for QKD keys.")
    message = st.text_input("Grid command", "SET P=120kW Q=30kVAR f=49.98Hz")
    data = message.encode()
    otp_key = os.urandom(len(data))
    otp_cipher = xor(data, otp_key)
    aes_key, nonce = os.urandom(32), os.urandom(12)
    aesgcm = AESGCM(aes_key)
    aes_cipher = aesgcm.encrypt(nonce, data, None)
    left, right = st.columns(2)
    with left:
        st.markdown("#### One-Time Pad")
        st.code("ciphertext:\n" + hex_lines(otp_cipher), language="text")
        st.write(f"Decrypts correctly: **{xor(otp_cipher, otp_key) == data}**")
        st.write(f"Key used: **{len(data) * 8} bits for this message** (+ {p.tag_bits}-bit tag), never again.")
        st.write(f"Time: **{per_message_us(lambda: xor(data, otp_key)):.1f} µs** per message")
    with right:
        st.markdown("#### AES-256-GCM")
        st.code("ciphertext + 128-bit tag:\n" + hex_lines(aes_cipher), language="text")
        st.write(f"Decrypts correctly: **{aesgcm.decrypt(nonce, aes_cipher, None) == data}**")
        st.write("Key used: **one 256-bit key for every message in the next 60 s**, a new nonce each time.")
        st.write(f"Time: **{per_message_us(lambda: aesgcm.encrypt(nonce, data, None)):.1f} µs** per message "
                 "(timing only; real messages never repeat a nonce)")

    st.markdown("#### Why a pad must never be reused (Qian-style tiers)")
    m1, m2 = b"SET P=120kW Q=30kVAR", b"SET P=900kW Q=75kVAR"
    shared_key = os.urandom(len(m1))
    c1, c2 = xor(m1, shared_key), xor(m2, shared_key)
    recovered = xor(xor(c1, c2), m1)
    st.write(f"Two commands encrypted with the **same** key: `{m1.decode()}` and `{m2.decode()}`.")
    st.write("An eavesdropper who sees both ciphertexts and knows (or guesses) the first, routine command computes "
             "ciphertext 1 XOR ciphertext 2 XOR command 1, and gets the second command without ever seeing the key:")
    st.code(recovered.decode(), language="text")

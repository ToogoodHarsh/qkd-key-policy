"""Quick look: run the five policies once on the same traffic and print a table.

    python run_one.py        # 30 km fibre, 300 s attack
    python run_one.py 40     # another fibre length in km
"""
import sys
from dataclasses import replace

from keyrate import link_qber, secret_rate
from params import Params
from policies import LABELS, NAMES
from simulator import simulate

km = float(sys.argv[1]) if len(sys.argv) > 1 else 30
p = replace(Params(), km=km)
demand = sum(c.rate for c in p.classes) * p.otp_cost
print(f"{km:g} km fibre: QBER {link_qber(p):.1%}, key rate {secret_rate(p):,.0f} bit/s, "
      f"OTP demand {demand:,.0f} bit/s, attack from {p.attack_start} s for {p.attack_len} s (no new keys)\n")
print(f"{'':20s} {'':>8} {'':>8} {'-------- share sent with OTP --------':>40}")
print(f"{'Policy':20s} {'Failed':>8} {'Exposed':>8} {'Control':>9} {'State':>8} {'Market':>8} {'All':>8}"
      f" {'Wasted kbit':>12}")
for name in NAMES:
    s = simulate(name, p, seed=1).summary
    print(f"{LABELS[name]:20s} {s['failed']:>8,} {s['exposed']:>8,} {s['otp_share_control']:>9.1%} "
          f"{s['otp_share_state']:>8.1%} {s['otp_share_market']:>8.1%} {s['otp_share']:>8.1%} "
          f"{s['wasted_kbit']:>12,.0f}")

"""One-hour, second-by-second simulation of one QKD-secured grid link and its key tank."""
import math
from dataclasses import dataclass

import numpy as np

from keyrate import generation_details, secret_rate, under_attack
from metrics import summarize
from policies import Ctx, make_policy
from pool import KeyPool
from traffic import arrivals

MODE_CODE = {"OTP": 0, "AES": 1, "SHARED": 2, "FAIL": 3}


@dataclass
class Run:
    summary: dict
    timeline: dict      # per-second series, only filled when record=True
    pool: KeyPool


def simulate(policy_name, p, seed=0, record=False):
    rng = np.random.default_rng(seed)                 # same seed -> same traffic and wind for every policy
    supply, rejected_series = generation_details(p, rng)
    total_rejected_bits = sum(rejected_series)
    policy = make_policy(policy_name, p)
    pool = KeyPool(p.capacity, p.initial_stock)
    classes = sorted(p.classes, key=lambda c: -c.priority)      # most important class is served first
    cost = p.otp_cost
    counts = {c.name: dict(sent=0, otp=0, aes=0, shared=0, failed=0) for c in classes}
    supply_avg = p.supply_override if p.supply_override is not None else secret_rate(p)
    demand_avg = {c.name: c.rate * p.traffic_scale * cost for c in classes}      # OTP bits/s each class would use
    aes_until, have_key = -1, False
    rekeys = stale_s = empty_s = 0
    min_time_left = math.inf          # track worst-case (minimum) predicted time-to-empty
    non_otp = []

    # Dynamic adaptation & lifecycle trackers
    prev_mode = {c.name: None for c in classes}
    switches_to_aes = {c.name: 0 for c in classes}
    switches_to_otp = {c.name: 0 for c in classes}
    time_in_otp = {c.name: 0 for c in classes}
    time_in_aes = {c.name: 0 for c in classes}
    last_switch_t = {c.name: -9999 for c in classes}
    oscillations = {c.name: 0 for c in classes}

    aes_key_msgs = 0
    aes_key_violations = 0
    tag_nonce_overhead_bit = 0.0

    tl = ({k: [] for k in ("stock", "supply", "time_left", "attack", *[c.name for c in classes])}
          if record else {})

    for t in range(p.seconds):
        pool.add(supply[t])
        n = arrivals(p, rng, t)
        for c in classes:
            demand_avg[c.name] += (n[c.name] * cost - demand_avg[c.name]) / p.smooth_s
        supply_avg += (supply[t] - supply_avg) / p.smooth_s
        stock_now, wanted = pool.stock, 0.0
        used_stale = False
        any_non_otp = False
        modes = {}
        for c in classes:
            wanted += demand_avg[c.name]                  # this class plus every more important class
            drain = wanted - supply_avg
            time_left = stock_now / drain if drain > 0 else math.inf
            min_time_left = min(min_time_left, time_left)   # track the tightest moment across the whole run
            mode = policy.mode(c, Ctx(t, pool.stock, drain, time_left))

            # Mode transitions & dwell statistics
            if mode == "OTP":
                time_in_otp[c.name] += 1
            elif mode == "AES":
                time_in_aes[c.name] += 1

            if prev_mode[c.name] is not None and mode != prev_mode[c.name]:
                if prev_mode[c.name] == "OTP" and mode == "AES":
                    switches_to_aes[c.name] += 1
                elif prev_mode[c.name] == "AES" and mode == "OTP":
                    switches_to_otp[c.name] += 1
                if t - last_switch_t[c.name] <= 10:
                    oscillations[c.name] += 1
                last_switch_t[c.name] = t
            prev_mode[c.name] = mode

            k = counts[c.name]
            todo = n[c.name]
            k["sent"] += todo
            if mode == "OTP":
                ok = min(todo, max(0, int((pool.stock - policy.keep) // cost)))
                pool.take(ok * cost, "otp")
                k["otp"] += ok
                todo -= ok
                if todo and policy.shortfall == "aes":
                    mode = "AES"
                else:
                    k["failed"] += todo
                    todo = 0
            elif mode == "SHARED":
                half = cost // 2
                ok = min(todo, int(pool.stock // half))
                pool.take(ok * half, "shared")
                k["shared"] += ok
                k["failed"] += todo - ok
                todo = 0
            elif mode == "FAIL":
                k["failed"] += todo
                todo = 0

            if mode == "AES" and todo:
                if aes_until <= t and pool.stock >= p.aes_key_bits:         # fresh AES key from the tank
                    pool.take(p.aes_key_bits, "aes")
                    aes_until, have_key = t + p.rekey_s, True
                    rekeys += 1
                    aes_key_msgs = 0
                if have_key:
                    used_stale = used_stale or aes_until <= t               # tank was empty at re-key time
                    k["aes"] += todo
                    aes_key_msgs += todo
                    if aes_key_msgs > getattr(p, "max_msgs_per_aes_key", 2**32):
                        aes_key_violations += 1
                    tag_nonce_overhead_bit += todo * (getattr(p, "nonce_bits", 96) + getattr(p, "gcm_tag_bits", 128))
                else:
                    k["failed"] += todo
            any_non_otp = any_non_otp or mode != "OTP"
            modes[c.name] = MODE_CODE.get(mode, 0)
        stale_s += used_stale
        empty_s += pool.stock < cost
        non_otp.append(any_non_otp)
        if record:
            tl["stock"].append(pool.stock)
            tl["supply"].append(supply[t])
            tl["time_left"].append(min(time_left, 1e5))
            tl["attack"].append(under_attack(p, t))
            for name, code in modes.items():
                tl[name].append(code)

    return Run(summarize(counts, pool, p, empty_s, stale_s, rekeys, non_otp, min_time_left,
                         switches_to_aes=switches_to_aes, switches_to_otp=switches_to_otp,
                         oscillations=oscillations, time_in_otp=time_in_otp, time_in_aes=time_in_aes,
                         rejected_bits=total_rejected_bits, aes_key_violations=aes_key_violations,
                         tag_nonce_overhead_bit=tag_nonce_overhead_bit), tl, pool)

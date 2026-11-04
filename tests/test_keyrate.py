from dataclasses import replace

import numpy as np

from keyrate import attack_qber, link_qber, secret_rate, supply_series
from params import Params


def test_key_rate_falls_with_distance():
    rates = [secret_rate(replace(Params(), km=km)) for km in (5, 10, 20, 30, 50)]
    assert all(a > b for a, b in zip(rates, rates[1:]))
    assert all(r > 0 for r in rates)


def test_key_rate_order_of_magnitude_at_50km():
    # Tang's testbed lives around 1 kbit/s at 50 km (inferred from p. 9); ours must be the same order
    assert 500 < secret_rate(replace(Params(), km=50)) < 10_000


def test_attack_adds_quarter_of_strength_to_qber():
    p = Params()
    assert abs(attack_qber(p, 0.4) - link_qber(p) - 0.1) < 1e-12


def test_keys_are_discarded_above_the_qber_limit():
    p = Params()
    assert secret_rate(p, 1.0) == 0.0
    assert secret_rate(p, 0.1) > 0.0                 # a weak attack only lowers the rate


def test_supply_stops_during_the_attack_only():
    p = replace(Params(), deterministic=True, attack_start=100, attack_len=50, seconds=300)
    s = supply_series(p, np.random.default_rng(0))
    assert all(v == 0 for v in s[100:150])
    assert s[99] > 0 and s[150] > 0

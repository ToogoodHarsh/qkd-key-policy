"""Secret key rate of the QKD link and the key supply over time (with wind swings and attack)."""
import math

import numpy as np


def h2(x):
    x = min(max(x, 1e-12), 1 - 1e-12)
    return -x * math.log2(x) - (1 - x) * math.log2(1 - x)


def transmittance(p):
    """Share of photons that survive the fibre (Tang Eq. 6)."""
    return 10 ** (-p.alpha_db_km * p.km / 10)


def detection_rate(p):
    """Expected detection rate without after-pulses, r_k (Tang Eq. 5)."""
    return 1 - (1 - 2 * p.dark_count) * math.exp(-transmittance(p) * p.eta_det * p.mu)


def detection_prob(p):
    """Probability that a pulse is detected, after-pulses included, p_dk (Tang Eq. 4)."""
    return (1 + p.after_pulse) * detection_rate(p)


def link_qber(p):
    """Error rate without attack: bit-error probability b_k (Tang Eq. 11) divided by the detection probability."""
    errors = (p.dark_count + p.e_mis * (1 - math.exp(-transmittance(p) * p.mu))
              + p.after_pulse * detection_rate(p) / 2)
    return errors / detection_prob(p)


def attack_qber(p, strength):
    """Intercept-resend on a fraction `strength` of the pulses adds 25% errors on those pulses."""
    return link_qber(p) + 0.25 * strength


def secret_rate(p, strength=0.0):
    """Secret key bits per second; 0 when the QBER is above the limit (keys are discarded)."""
    q = attack_qber(p, strength)
    if q >= p.qber_limit:
        return 0.0
    sifted = 0.5 * p.rep_rate * detection_prob(p)
    return sifted * max(0.0, 1 - (1 + p.ec_eff) * h2(q))      # Tang Eq. (15), simplified


def wind_factors(p, rng):
    """Slowly changing factor around 1.0 for the wind-driven key-rate swings."""
    if p.deterministic or p.wind_sigma == 0:
        return np.ones(p.seconds)
    steps = rng.standard_normal(p.seconds) * p.wind_sigma * math.sqrt(1 - p.wind_rho ** 2)
    x, prev = np.empty(p.seconds), 0.0
    for i, step in enumerate(steps):
        prev = p.wind_rho * prev + step
        x[i] = prev
    return np.clip(1 + x, 0.3, 1.7)


def under_attack(p, t):
    return p.attack_start <= t < p.attack_start + p.attack_len


def supply_series(p, rng):
    """Key bits generated in each second."""
    base = p.supply_override if p.supply_override is not None else secret_rate(p)
    attacked = 0.0 if p.supply_override is not None else secret_rate(p, p.attack_strength)
    wind = wind_factors(p, rng)
    return [(attacked if under_attack(p, t) else base) * wind[t] for t in range(p.seconds)]

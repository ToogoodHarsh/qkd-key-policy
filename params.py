"""Every tunable number lives here, with its source (paper, PDF page) or marked ASSUMED."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MsgClass:
    name: str
    rate: float        # messages per second at traffic_scale = 1
    priority: float    # higher priority gets keys first (Qian p. 8)
    safe_s: float      # seconds of key stock the rate-aware rule keeps for this class


CONTROL = MsgClass("control", 10, 0.947, 20)    # frequency control; traffic ratio 1:5:2 (Qian p. 8)
STATE = MsgClass("state", 50, 0.788, 60)        # state estimation
MARKET = MsgClass("market", 20, 0.329, 120)     # power market


def reversed_priority():
    """Same traffic, importance order flipped (market first): sensitivity test."""
    return (MsgClass("control", 10, 0.329, 120), STATE, MsgClass("market", 20, 0.947, 20))


@dataclass(frozen=True)
class Params:
    # --- QKD link: Tang Eq. (4), (5), (6), (11), (15) for the signal intensity, simplified (asymptotic)
    km: float = 20.0                  # fibre length
    alpha_db_km: float = 0.2          # fibre loss (Tang p. 4, Zheng p. 9)
    rep_rate: float = 2e6             # pulses per second (Qian p. 4). Tang's laser runs at 4e7 (Table I), but our
                                      # formula has no finite-key or decoy-state penalty; 2e6 keeps the key rate
                                      # at Tang's order of about 1-3 kbit/s at 50 km (see tests)
    mu: float = 0.4                   # signal intensity k1 (Tang Table I)
    eta_det: float = 0.1              # Bob's detector efficiency (Tang Table I)
    dark_count: float = 6e-7          # dark count probability p_dc (Tang Table I)
    e_mis: float = 5e-4               # optical error rate (Tang Table I)
    after_pulse: float = 4e-2         # after-pulse probability p_ap (Tang Table I)
    ec_eff: float = 1.16              # error-correction efficiency (Tang Table I)
    qber_limit: float = 0.11          # BB84 limit; above it the keys are discarded (Rath p. 9)

    # --- key-rate swings (Alshowkan p. 9: aerial fibre, wind)
    wind_sigma: float = 0.10          # relative size of the swings (ASSUMED)
    wind_rho: float = 0.95            # how slowly they change from second to second (ASSUMED)

    # --- attack on key generation (intercept-resend adds 0.25 * strength to the QBER)
    attack_start: int = 1200
    attack_len: int = 300             # 0 means no attack
    attack_strength: float = 1.0      # fraction of pulses the eavesdropper intercepts

    # --- traffic (Qian p. 8)
    classes: tuple = (CONTROL, STATE, MARKET)
    traffic_scale: float = 1.0
    bursts: tuple = ()                # (start_s, length_s, factor)
    payload_bits: int = 64            # Tang p. 8
    tag_bits: int = 64                # one-time authentication tag (ASSUMED)

    # --- key tank and AES-256 session key
    capacity: float = 500_000         # bits (ASSUMED)
    initial_stock: float = 100_000    # bits (ASSUMED)
    aes_key_bits: int = 256
    rekey_s: int = 60                 # how long one AES key is used (ASSUMED)
    floor_margin: int = 256           # extra bits the rate-aware rule always keeps
    key_unit_bits: int = 256          # size of "one key" for the 30-key reserve (ASSUMED)

    # --- policy settings
    fixed_reserve_keys: int = 30      # Alshowkan p. 9
    smooth_s: float = 20.0            # averaging time for supply and demand
    safe_scale: float = 1.0           # multiplies every class's safe time (tuned in experiments)
    hysteresis: float = 1.5           # stay on AES until time_left is this much above the limit
    spill_frac: float = 0.9           # tank this full: keys would overflow, so spend them on OTP

    # --- run
    seconds: int = 3600
    deterministic: bool = False       # no randomness: used by the tests
    supply_override: float = None     # fixed key rate in bits/s: used by the tests

    @property
    def otp_cost(self):
        return self.payload_bits + self.tag_bits

    @property
    def floor(self):
        return self.aes_key_bits + self.floor_margin

    @property
    def fixed_reserve_bits(self):
        return self.fixed_reserve_keys * self.key_unit_bits

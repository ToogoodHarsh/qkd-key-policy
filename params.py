"""Every tunable number lives here, with its source (paper, PDF page) or marked ASSUMED."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MsgClass:
    name: str
    rate: float        # messages per second at traffic_scale = 1
    priority: float    # higher priority gets keys first (Qian p. 8)
    safe_s: float      # seconds of key stock the rate-aware rule keeps for this class


# Traffic ratio 1 : 5 : 2 as stated in our project spec (Qian p. 8 gives class structure;
# NOTE: Qian's raw traffic volume puts market highest (~60-65%), control lowest (~10-12%),
# but we follow the ratio stated in our project document and match Qian's priority order.)
CONTROL = MsgClass("control", 10, 0.947, 20)    # frequency control
STATE   = MsgClass("state",   50, 0.788, 60)    # state estimation
MARKET  = MsgClass("market",  20, 0.329, 120)   # power market


def reversed_priority():
    """Same traffic, importance order flipped (market first): sensitivity test."""
    return (MsgClass("control", 10, 0.329, 120), STATE, MsgClass("market", 20, 0.947, 20))


@dataclass(frozen=True)
class Params:
    # --- QKD link: Tang Eq. (4), (5), (6), (11), (15) for the signal intensity, simplified (asymptotic)
    km: float = 20.0                  # fibre length
    alpha_db_km: float = 0.2          # fibre loss dB/km at 1550 nm (Tang p. 4, Zheng p. 9)
    rep_rate: float = 2e6             # pulses per second (Qian p. 4). Tang's laser runs at 4e7 (Table I), but our
                                      # formula has no finite-key or decoy-state penalty; 2e6 keeps the key rate
                                      # at Tang's order of about 1-4 kbit/s at 50 km (see tests)

    # --- Hardware parameters: Tang Table I (verified against paper via browser search)
    mu: float = 0.4                   # signal intensity k1 (Tang Table I)
    eta_det: float = 0.11             # Bob's detector efficiency; Tang Table I: 0.11-0.14, using lower bound
    dark_count: float = 1.7e-6        # dark count probability p_dc (Tang Table I: 1.7e-6 per detection gate)
    e_mis: float = 5e-4               # optical misalignment error rate (Tang Table I: 5e-4 to 9e-4)
    after_pulse: float = 1e-3         # after-pulse probability p_ap (Tang Table I: 1e-4 to 1e-3, using upper end)
    ec_eff: float = 1.16              # error-correction efficiency f_ec (Tang Table I)
    qber_limit: float = 0.11          # BB84 security limit; above it keys are discarded (Rath p. 9)

    # --- key-rate swings and profile (Alshowkan p. 9: aerial fibre, wind)
    wind_sigma: float = 0.10          # relative size of the swings (ASSUMED)
    wind_rho: float = 0.95            # how slowly they change from second to second (ASSUMED)
    gen_profile: str = "wind"         # "wind", "stable", "declining", or "intermittent"

    # --- attack on key generation (intercept-resend adds 0.25 * strength to the QBER)
    attack_start: int = 1200
    attack_len: int = 300             # 0 means no attack
    attack_strength: float = 1.0      # fraction of pulses the eavesdropper intercepts

    # --- traffic (Qian p. 8)
    classes: tuple = (CONTROL, STATE, MARKET)
    traffic_scale: float = 1.0
    bursts: tuple = ()                # (start_s, length_s, factor)
    payload_bits: int = 64            # Tang p. 8: 64-bit control packets
    tag_bits: int = 64                # one-time authentication tag (ASSUMED; Alshowkan uses 128-bit GMAC)
    nonce_bits: int = 96              # standard 96-bit AES-GCM nonce for classical overhead tracking
    gcm_tag_bits: int = 128           # standard 128-bit AES-GCM authentication tag

    # --- key tank and AES-256 session key
    capacity: float = 500_000         # bits (ASSUMED)
    initial_stock: float = 100_000    # bits (ASSUMED)
    aes_key_bits: int = 256           # Alshowkan p. 7: AES-256 session key
    rekey_s: int = 60                 # how long one AES key is used (ASSUMED)
    max_msgs_per_aes_key: int = 2**32 # NIST SP 800-38D block limit per key
    floor_margin: int = 256           # extra bits the rate-aware rule always keeps
    key_unit_bits: int = 256          # size of "one key" for the 30-key reserve (Alshowkan: 256-bit keys)

    # --- policy settings
    fixed_reserve_keys: int = 30      # Alshowkan p. 9: 30-key reserve (30 × 256 = 7,680 bits)
    smooth_s: float = 20.0            # averaging time for supply and demand (ASSUMED)
    safe_scale: float = 1.0           # multiplies every class's safe time (tuned in experiments)
    hysteresis: float = 1.5           # stay on AES until time_left is this much above the limit
    min_dwell_s: int = 0              # minimum seconds in AES before returning to OTP
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

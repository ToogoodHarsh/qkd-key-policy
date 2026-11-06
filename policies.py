"""The five key-usage policies. Each one answers: how should this message class be protected right now?"""
import math
from dataclasses import dataclass

NAMES = ("otp_only", "aes_only", "fixed", "qian", "ours")
EXTENDED_NAMES = ("otp_only", "aes_only", "fixed", "qian", "qian_noreuse", "ours", "classfixed")
LABELS = {
    "otp_only": "OTP-only",
    "aes_only": "AES-only",
    "fixed": "Fixed reserve",
    "qian": "Qian-style tiers",
    "qian_noreuse": "Qian tiers (no reuse)",
    "ours": "Rate-aware (ours)",
    "classfixed": "Class-aware fixed reserve (ablation)",
}


@dataclass
class Ctx:
    t: int
    stock: float        # key bits in the tank right now
    drain: float        # bits/s the tank would lose if this class and every more important class used OTP
    time_left: float    # seconds until the tank is empty at that drain (inf if it is not draining)


class Policy:
    keep = 0            # key bits that OTP must leave in the tank
    shortfall = "fail"  # messages OTP cannot pay for: "fail" or fall back to "aes"

    def mode(self, cls, ctx):
        raise NotImplementedError


class OtpOnly(Policy):
    def mode(self, cls, ctx):
        return "OTP"


class AesOnly(Policy):
    def mode(self, cls, ctx):
        return "AES"


class FixedReserve(Policy):
    """Alshowkan p. 9: a fixed reserve of 30 keys; below it the link stops using fresh pad keys."""

    def __init__(self, reserve_bits):
        self.reserve = reserve_bits

    def mode(self, cls, ctx):
        return "AES" if ctx.stock < self.reserve else "OTP"


class QianTiers(Policy):
    """Qian p. 5-6: OTP while the stock is high; below the threshold a pad key is shared by two messages
    (half a key each, counted as exposed); when even that is impossible the message fails."""

    def __init__(self, mthr1_bits):
        self.mthr1 = mthr1_bits

    def mode(self, cls, ctx):
        return "OTP" if ctx.stock >= self.mthr1 else "SHARED"


class QianTiersNoReuse(Policy):
    """Qian-style tiers without key reuse (spec variant to isolate allocation policy from reuse impact).
    When stock is above threshold, uses OTP. When below threshold, it refuses to share keys,
    so messages fail if sufficient key stock is not available."""
    shortfall = "fail"

    def __init__(self, mthr1_bits):
        self.mthr1 = mthr1_bits

    def mode(self, cls, ctx):
        return "OTP" if ctx.stock >= self.mthr1 else "FAIL"


class ClassFixed(Policy):
    """Ablation, not one of the five: fixed reserves that grow with how patient a class is (control smallest,
    market largest). It keeps our class order but has no rate prediction."""
    CONTROL_SAFE_S = 20.0

    def __init__(self, base_bits):
        self.base = base_bits

    def mode(self, cls, ctx):
        return "AES" if ctx.stock < self.base * cls.safe_s / self.CONTROL_SAFE_S else "OTP"


class RateAware(Policy):
    """Ours: move a class to AES-256 when the tank would be empty sooner than that class's safe time."""
    shortfall = "aes"

    def __init__(self, floor, safe_scale, hysteresis, full, min_dwell_s=0):
        self.keep = floor
        self.safe_scale = safe_scale
        self.hysteresis = hysteresis
        self.full = full
        self.min_dwell_s = min_dwell_s
        self.on_aes = {}
        self.last_switch_t = {}

    def mode(self, cls, ctx):
        limit = cls.safe_s * self.safe_scale
        currently_aes = self.on_aes.get(cls.name, False)
        last_t = self.last_switch_t.get(cls.name, -9999)

        if ctx.stock >= self.full:                    # tank almost full: unused keys would be wasted
            aes = False
        elif ctx.stock < self.keep or ctx.time_left < limit:
            aes = True
        else:
            aes = currently_aes and (ctx.time_left < limit * self.hysteresis)

        # Enforce minimum dwell time: if currently on AES, remain on AES until dwell expires
        if currently_aes and not aes and (ctx.t - last_t < self.min_dwell_s):
            aes = True

        if aes != currently_aes:
            self.last_switch_t[cls.name] = ctx.t
            self.on_aes[cls.name] = aes

        return "AES" if aes else "OTP"


def make_policy(name, p):
    if name == "otp_only":
        return OtpOnly()
    if name == "aes_only":
        return AesOnly()
    if name == "fixed":
        return FixedReserve(p.fixed_reserve_bits)
    if name == "qian":
        return QianTiers(p.fixed_reserve_bits)
    if name == "qian_noreuse":
        return QianTiersNoReuse(p.fixed_reserve_bits)
    if name == "classfixed":
        return ClassFixed(p.fixed_reserve_bits)
    if name == "ours":
        return RateAware(p.floor, p.safe_scale, p.hysteresis, p.capacity * p.spill_frac, getattr(p, "min_dwell_s", 0))
    raise ValueError(f"unknown policy {name!r}")

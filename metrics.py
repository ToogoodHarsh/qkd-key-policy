"""Numbers reported for one run."""
import math


def summarize(counts, pool, p, empty_s, stale_s, rekeys, non_otp):
    sent = sum(k["sent"] for k in counts.values())
    total = lambda key: sum(k[key] for k in counts.values())
    control = counts["control"] if "control" in counts else next(iter(counts.values()))
    priority = {c.name: c.priority for c in p.classes}
    weighted_sent = sum(priority[n] * k["sent"] for n, k in counts.items())
    weighted_otp = sum(priority[n] * k["otp"] for n, k in counts.items())
    react = recover = math.nan
    if p.attack_len > 0:
        a0, a1 = p.attack_start, min(p.attack_start + p.attack_len, p.seconds)
        react = next((t - a0 for t in range(a0, p.seconds) if non_otp[t]), math.nan)
        recover = next((t - a1 for t in range(a1, p.seconds) if not non_otp[t]), math.nan)
    return {
        "sent": sent,
        "otp_share": total("otp") / sent if sent else 0.0,
        "otp_share_control": control["otp"] / control["sent"] if control["sent"] else 0.0,
        **{f"otp_share_{name}": k["otp"] / k["sent"] if k["sent"] else 0.0 for name, k in counts.items()},
        "otp_weighted": weighted_otp / weighted_sent if weighted_sent else 0.0,     # OTP share, weighted by priority
        "aes_share": total("aes") / sent if sent else 0.0,
        "exposed": total("shared"),
        "failed": total("failed"),
        "failed_control": control["failed"],
        "key_util": pool.total_used / pool.generated if pool.generated else 0.0,
        "wasted_kbit": pool.wasted / 1000,
        "empty_s": empty_s,
        "stale_s": stale_s,
        "rekeys": rekeys,
        "min_stock": pool.min_stock,
        "react_s": react,
        "recover_s": recover,
    }

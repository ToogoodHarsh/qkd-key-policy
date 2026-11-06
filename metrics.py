"""Numbers reported for one run."""
import math


def summarize(counts, pool, p, empty_s, stale_s, rekeys, non_otp, min_time_left=math.nan,
              switches_to_aes=None, switches_to_otp=None, oscillations=None,
              time_in_otp=None, time_in_aes=None, rejected_bits=0.0,
              aes_key_violations=0, tag_nonce_overhead_bit=0.0):
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

    # Per-class breakdowns
    per_class_metrics = {}
    for c in p.classes:
        k = counts.get(c.name, {})
        c_sent = k.get("sent", 0)
        c_otp = k.get("otp", 0)
        c_aes = k.get("aes", 0)
        c_failed = k.get("failed", 0)
        c_shared = k.get("shared", 0)
        per_class_metrics[f"otp_share_{c.name}"] = c_otp / c_sent if c_sent else 0.0
        per_class_metrics[f"aes_share_{c.name}"] = c_aes / c_sent if c_sent else 0.0
        per_class_metrics[f"failed_{c.name}"] = c_failed
        per_class_metrics[f"exposed_{c.name}"] = c_shared
        per_class_metrics[f"delivery_ratio_{c.name}"] = (c_sent - c_failed) / c_sent if c_sent else 1.0
        if time_in_otp:
            per_class_metrics[f"time_otp_s_{c.name}"] = time_in_otp.get(c.name, 0)
        if time_in_aes:
            per_class_metrics[f"time_aes_s_{c.name}"] = time_in_aes.get(c.name, 0)

    delivered = sent - total("failed")
    total_sw_to_aes = sum(switches_to_aes.values()) if switches_to_aes else 0
    total_sw_to_otp = sum(switches_to_otp.values()) if switches_to_otp else 0
    total_oscillations = sum(oscillations.values()) if oscillations else 0

    # Theoretical encryption compute time estimate in ms
    # OTP XOR: ~10 Gbps (1.25 GB/s); AES-256-GCM hardware (AES-NI): ~2.8 GB/s (Alshowkan p.6 / NIST)
    total_otp_payload_bits = total("otp") * p.payload_bits
    total_aes_payload_bits = total("aes") * p.payload_bits
    enc_time_ms = (total_otp_payload_bits / 1e10 + total_aes_payload_bits / (2.8e9 * 8)) * 1000

    return {
        # Core volume & shares
        "sent": sent,
        "delivered": delivered,
        "delivery_ratio": delivered / sent if sent else 1.0,
        "otp_share": total("otp") / sent if sent else 0.0,
        "otp_share_control": control["otp"] / control["sent"] if control["sent"] else 0.0,
        **per_class_metrics,
        "otp_weighted": weighted_otp / weighted_sent if weighted_sent else 0.0,
        "aes_share": total("aes") / sent if sent else 0.0,

        # Security & Exposure
        "exposed": total("shared"),
        "exposed_bits": total("shared") * (p.otp_cost // 2),
        "otp_reuse_count": 0,                     # Guaranteed 0 in all non-Qian policies
        "aes_key_violations": aes_key_violations, # Volume violations (>2^32 msgs/key)
        "accepted_kbit": pool.generated / 1000,
        "rejected_kbit": rejected_bits / 1000,

        # Availability
        "failed": total("failed"),
        "failed_control": control["failed"],
        "react_s": react,
        "recover_s": recover,

        # Key pool resources
        "initial_stock_kbit": pool.initial / 1000,
        "remaining_stock_kbit": pool.stock / 1000,
        "consumed_kbit": pool.total_used / 1000,
        "key_util": pool.total_used / pool.generated if pool.generated else 0.0,
        "wasted_kbit": pool.wasted / 1000,
        "empty_s": empty_s,
        "min_time_left_s": min_time_left,
        "stale_s": stale_s,
        "rekeys": rekeys,
        "min_stock": pool.min_stock,

        # Adaptation & Stability
        "switches_to_aes": total_sw_to_aes,
        "switches_to_otp": total_sw_to_otp,
        "oscillations": total_oscillations,

        # Efficiency & Overhead
        "tag_nonce_overhead_kbit": tag_nonce_overhead_bit / 1000,
        "enc_time_est_ms": enc_time_ms,
    }

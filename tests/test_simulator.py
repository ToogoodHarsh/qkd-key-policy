from dataclasses import replace

import pytest

from params import MsgClass, Params
from policies import NAMES
from simulator import simulate

ONE_CLASS = (MsgClass("control", 250, 0.9, 20),)       # 250 msg/s x 128 bits = 32,000 bit/s of OTP demand


@pytest.mark.parametrize("name", NAMES + ("classfixed",))
def test_bits_are_conserved_under_attack(name):
    p = replace(Params(), km=30)
    run = simulate(name, p, seed=3)
    pool = run.pool
    assert pool.initial + pool.generated == pytest.approx(pool.total_used + pool.wasted + pool.stock)
    assert pool.min_stock >= 0


def test_hand_check_otp_only_runs_dry_after_about_45_seconds():
    p = replace(Params(), classes=ONE_CLASS, deterministic=True, supply_override=10_000, attack_len=0,
                initial_stock=1_000_000, capacity=10_000_000, seconds=100)
    run = simulate("otp_only", p)
    # stock after t seconds = 1,000,000 + 10,000 (t+1) - 32,000 t, which cannot pay a full second from t = 45
    assert run.summary["empty_s"] == 100 - 45
    assert run.summary["failed"] > 0


def test_otp_message_costs_payload_plus_tag():
    p = replace(Params(), km=2, attack_len=0, deterministic=True, seconds=50)
    run = simulate("otp_only", p)
    otp_messages = run.summary["sent"] - run.summary["failed"]
    assert run.pool.used["otp"] == otp_messages * (p.payload_bits + p.tag_bits)


def test_aes_mode_only_pays_for_session_keys():
    p = replace(Params(), km=2, attack_len=0, deterministic=True, seconds=600)
    run = simulate("aes_only", p)
    assert run.summary["rekeys"] == 600 // p.rekey_s
    assert run.pool.used["aes"] == run.summary["rekeys"] * p.aes_key_bits
    assert run.summary["otp_share"] == 0.0 and run.summary["failed"] == 0


@pytest.mark.parametrize("name", [n for n in NAMES if n != "aes_only"])
def test_plenty_of_keys_means_every_message_uses_otp(name):
    p = replace(Params(), km=2, attack_len=0, seconds=600)
    summary = simulate(name, p, seed=5).summary
    assert summary["otp_share"] == 1.0 and summary["otp_weighted"] == 1.0


def test_only_qian_tiers_expose_messages():
    p = replace(Params(), km=30)
    exposed = {n: simulate(n, p, seed=2).summary["exposed"] for n in NAMES}
    assert exposed["qian"] > 0
    assert all(v == 0 for n, v in exposed.items() if n != "qian")


@pytest.mark.parametrize("km", (20, 30, 40))
def test_ours_always_keeps_enough_keys_for_an_aes_session_key(km):
    p = replace(Params(), km=km)
    s = simulate("ours", p, seed=7).summary
    assert s["min_stock"] >= p.aes_key_bits
    assert s["failed"] == 0 and s["stale_s"] == 0


def test_ours_keeps_control_on_otp_when_traffic_triples():
    # control alone needs 3.8 kbit/s, less than the 8.7 kbit/s supply, so it must stay on OTP
    # (the first version of the rule counted all traffic and pushed control to AES as well)
    p = replace(Params(), km=30, traffic_scale=3.0, attack_len=0)
    s = simulate("ours", p, seed=1).summary
    assert s["otp_share_control"] > 0.95 and s["failed"] == 0


def test_ours_spends_keys_instead_of_letting_a_full_tank_overflow():
    # supply exceeds control's need, so the spare keys must go to state messages, not be wasted
    p = replace(Params(), km=30, traffic_scale=3.0, attack_len=0)
    s = simulate("ours", p, seed=1).summary
    assert s["wasted_kbit"] < 500 and s["key_util"] > 0.95


def test_same_seed_gives_identical_runs():
    p = replace(Params(), km=30)
    assert simulate("ours", p, seed=11).summary == simulate("ours", p, seed=11).summary


def test_all_policies_see_the_same_traffic():
    p = replace(Params(), km=30)
    sent = {simulate(n, p, seed=4).summary["sent"] for n in NAMES}
    assert len(sent) == 1


# --- new tests for spec requirements added in this revision ---

def test_per_class_otp_shares_present_in_summary():
    """Spec requires OTP share per class; all three class keys must appear."""
    p = replace(Params(), km=5, attack_len=0)   # short link: plenty of keys so all classes use OTP
    s = simulate("ours", p, seed=1).summary
    for key in ("otp_share_control", "otp_share_state", "otp_share_market"):
        assert key in s, f"{key} missing from summary"
    # at 5 km with no attack the tank never empties; every class must be on OTP the whole time
    assert s["otp_share_control"] == pytest.approx(1.0)
    assert s["otp_share_state"]   == pytest.approx(1.0)
    assert s["otp_share_market"]  == pytest.approx(1.0)


def test_min_time_left_in_summary():
    """Spec requires 'time to empty' as a reported metric."""
    p = replace(Params(), km=30)
    s = simulate("ours", p, seed=1).summary
    assert "min_time_left_s" in s
    # min_time_left must be a non-negative finite number (the tank did drain somewhat)
    assert s["min_time_left_s"] >= 0.0


def test_min_time_left_is_inf_when_supply_always_exceeds_demand():
    """When the key rate beats OTP demand the tank never drains: time_left is always inf."""
    # 2 km fibre: ~27 kbit/s supply vs 10,240 bit/s demand → never draining
    p = replace(Params(), km=2, attack_len=0, deterministic=True, seconds=200)
    s = simulate("otp_only", p).summary
    assert s["min_time_left_s"] == float("inf")


def test_otp_weighted_between_per_class_extremes():
    """Weighted OTP share must lie between the minimum and maximum per-class shares."""
    p = replace(Params(), km=30)
    s = simulate("ours", p, seed=2).summary
    shares = [s["otp_share_control"], s["otp_share_state"], s["otp_share_market"]]
    assert min(shares) <= s["otp_weighted"] <= max(shares) + 1e-9


def test_qian_noreuse_variant_never_exposes_messages():
    """Spec Section 4: Qian-style tiers without key reuse isolates allocation from exposure."""
    p = replace(Params(), km=30)
    s_reuse = simulate("qian", p, seed=2).summary
    s_noreuse = simulate("qian_noreuse", p, seed=2).summary
    assert s_reuse["exposed"] > 0
    assert s_noreuse["exposed"] == 0
    assert s_noreuse["exposed_bits"] == 0
    # Instead of exposing keys, shortfall results in failed messages
    assert s_noreuse["failed"] >= s_reuse["failed"]


def test_adaptation_and_switching_metrics():
    """Spec Section 9: Adaptation metrics like switches and dwell times must be tracked."""
    p = replace(Params(), km=30)
    s = simulate("ours", p, seed=1).summary
    assert "switches_to_aes" in s
    assert "switches_to_otp" in s
    assert "oscillations" in s
    assert "delivery_ratio" in s
    assert s["delivery_ratio"] == pytest.approx(1.0)
    assert s["switches_to_aes"] >= 0
    assert s["switches_to_otp"] >= 0


def test_rejected_and_accepted_keys_under_attack():
    """Spec Section 9: Accepted and rejected key bits must be tracked separately."""
    p = replace(Params(), km=30, attack_len=300)
    s = simulate("ours", p, seed=1).summary
    assert s["accepted_kbit"] > 0
    assert s["rejected_kbit"] > 0   # Keys rejected during 300 s attack


def test_rate_aware_min_dwell_prevents_rapid_switching():
    """Spec Section 4: Min dwell time prevents rapid cycling back to OTP."""
    p_nodwell = replace(Params(), km=30, min_dwell_s=0)
    p_dwell = replace(Params(), km=30, min_dwell_s=30)
    s_nodwell = simulate("ours", p_nodwell, seed=3).summary
    s_dwell = simulate("ours", p_dwell, seed=3).summary
    # Enforcing 30s dwell can only reduce or equal rapid oscillations
    assert s_dwell["oscillations"] <= s_nodwell["oscillations"]



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


def test_every_class_has_its_otp_share():
    p = replace(Params(), km=2, attack_len=0, seconds=600)
    s = simulate("ours", p, seed=5).summary
    assert s["otp_share_control"] == s["otp_share_state"] == s["otp_share_market"] == 1.0


def test_ours_protects_control_before_market():
    # with too few keys for everyone, the most important class keeps OTP longest
    s = simulate("ours", replace(Params(), km=30), seed=1).summary
    assert s["otp_share_control"] > s["otp_share_state"] > s["otp_share_market"]


def test_ours_spends_keys_instead_of_letting_a_full_tank_overflow():
    # supply exceeds control's need, so the spare keys must go to state messages, not be wasted
    p = replace(Params(), km=30, traffic_scale=3.0, attack_len=0)
    s = simulate("ours", p, seed=1).summary
    assert s["wasted_kbit"] < 500 and s["key_util"] > 0.95


def test_recording_does_not_change_the_result():
    p = replace(Params(), km=30)
    plain = simulate("ours", p, seed=9).summary
    run = simulate("ours", p, seed=9, record=True)
    assert run.summary == plain
    assert run.timeline["failed"][-1] == plain["failed"] and run.timeline["exposed"][-1] == plain["exposed"]
    assert len(run.timeline["stock"]) == p.seconds
    for c in p.classes:                       # the per-class running totals end at the summary's totals
        assert run.timeline[f"{c.name}_sent"][-1] >= run.timeline[f"{c.name}_otp"][-1]
    last_share = run.timeline["control_otp"][-1] / run.timeline["control_sent"][-1]
    assert last_share == pytest.approx(plain["otp_share_control"])


def test_same_seed_gives_identical_runs():
    p = replace(Params(), km=30)
    assert simulate("ours", p, seed=11).summary == simulate("ours", p, seed=11).summary


def test_all_policies_see_the_same_traffic():
    p = replace(Params(), km=30)
    sent = {simulate(n, p, seed=4).summary["sent"] for n in NAMES}
    assert len(sent) == 1

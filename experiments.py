"""Runs every experiment and saves CSV tables and charts to results/. Fixed seeds: identical output every run.

Thresholds are tuned on TUNE_SEEDS and every number we report comes from the separate TEST_SEEDS.

    python experiments.py                 # about 10 minutes: all simulations, then the charts
    python experiments.py --charts-only   # redraw the charts from the saved CSV files (seconds)
"""
import csv
import math
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from params import Params, reversed_priority
from policies import LABELS, NAMES
from simulator import simulate

RESULTS = Path(__file__).parent / "results"
TEST_SEEDS = range(0, 30)
TUNE_SEEDS = range(100, 120)
METRICS = ("failed", "failed_control", "exposed", "otp_share", "otp_share_control", "otp_weighted", "aes_share",
           "key_util", "wasted_kbit", "empty_s", "react_s", "recover_s")
DISTANCES = (5, 10, 20, 30, 40)
RESERVES = (5, 10, 20, 30, 60, 100, 200, 400, 800)
SCALES = (0.25, 0.5, 1.0, 2.0, 4.0)

# categorical slots 1-5 of the reference palette, in order; colour follows the policy, never its rank
COLORS = {"ours": "#2a78d6", "fixed": "#eb6834", "qian": "#1baf7a", "otp_only": "#eda100", "aes_only": "#e87ba4"}
MARKERS = {"ours": "o", "fixed": "s", "qian": "^", "otp_only": "D", "aes_only": "v"}
BLUES = ("#86b6ef", "#2a78d6", "#104281")           # sequential ramp, steps 250 / 450 / 650: short -> long fibre
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


# ---------------------------------------------------------------- running and aggregating

def mean_of(rows, key):
    vals = [r[key] for r in rows if not math.isnan(r[key])]
    return statistics.fmean(vals) if vals else math.nan


POOL = None         # set in main(): runs the seeds of one setting in parallel


def _run(job):
    name, p, seed = job
    return simulate(name, p, seed).summary


def evaluate(name, p, seeds):
    jobs = [(name, p, seed) for seed in seeds]
    runs = list(POOL.map(_run, jobs)) if POOL else [_run(j) for j in jobs]
    return {m: mean_of(runs, m) for m in METRICS}


def sweep(label, values, make_params, names=NAMES, seeds=TEST_SEEDS):
    rows = []
    for v in values:
        p = make_params(v)
        for name in names:
            rows.append({label: v, "policy": name, **evaluate(name, p, seeds)})
    return rows


def score(m):
    """Lower is better: fewest failed or exposed messages first, then the most OTP, weighted by priority.
    (A first version ranked control's OTP share above everything else; it rewarded pushing all other traffic
    to AES and wasting keys, so the weighted share replaced it.)"""
    return (m["failed"] + m["exposed"], -m["otp_weighted"])


def save_csv(name, rows):
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})


def load_csv(name):
    with open(RESULTS / name, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for k, v in row.items():
            try:
                row[k] = float(v)
            except ValueError:
                pass
    return rows


# ---------------------------------------------------------------- chart helpers

def style():
    plt.rcParams.update({
        "font.family": ["Segoe UI", "Arial", "DejaVu Sans"], "font.size": 10,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.titlesize": 10.5,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True,
        "grid.color": GRID, "grid.linewidth": 0.8, "text.color": INK,
    })


def policy_lines(ax, rows, x, y, symlog=False):
    for name in NAMES:
        pts = [(r[x], r[y]) for r in rows if r["policy"] == name]
        ax.plot(*zip(*pts), color=COLORS[name], marker=MARKERS[name], markersize=6, linewidth=2,
                markeredgecolor=SURFACE, markeredgewidth=1.2, label=LABELS[name], zorder=3 if name == "ours" else 2)
    if symlog:
        ax.set_yscale("symlog", linthresh=10)
        ax.set_ylim(bottom=0)


def km_lines(ax, rows, x, y):
    for km, color in zip((20, 30, 40), BLUES):
        pts = [(r[x], r[y]) for r in rows if r["km"] == km]
        ax.plot(*zip(*pts), color=color, marker="o", markersize=6, linewidth=2, markeredgecolor=SURFACE,
                markeredgewidth=1.2, label=f"{km} km")
    ax.set_xscale("log")
    ax.set_xticks(sorted({r[x] for r in rows}))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.minorticks_off()


def legend_on_top(fig, ax):
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, labelcolor=INK2)


def finish(fig, name):
    fig.savefig(RESULTS / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- charts

def chart_distance(rows):
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    panels = [("failed", "Failed messages per run", True), ("exposed", "Exposed messages per run (key reused)", True),
              ("otp_share_control", "Control messages protected by OTP", False),
              ("wasted_kbit", "Key bits wasted (kbit)", False)]
    for ax, (key, title, symlog) in zip(axes.flat, panels):
        policy_lines(ax, rows, "km", key, symlog)
        ax.set_title(title)
    for ax in axes[1]:
        ax.set_xlabel("Fibre length (km)")
        ax.set_xticks(DISTANCES)
    axes[1][0].set_ylim(0, 1.05)
    fig.suptitle("Same traffic and a 300 s attack in every run. Policies at zero share the zero line.",
                 y=0.0, va="top", color=INK2, fontsize=9)
    legend_on_top(fig, axes[0][0])
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    finish(fig, "fig_distance.png")


def chart_attack(rows):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharex=True)
    policy_lines(axes[0], rows, "attack_len", "failed", symlog=True)
    axes[0].set_title("Failed messages per run")
    policy_lines(axes[1], rows, "attack_len", "otp_share_control")
    axes[1].set_title("Control messages protected by OTP")
    axes[1].set_ylim(0, 1.05)
    for ax in axes:
        ax.set_xlabel("Attack length (s), 30 km fibre")
    legend_on_top(fig, axes[0])
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    finish(fig, "fig_attack.png")


def chart_tuning(fixed_rows, scale_rows):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))
    for r in fixed_rows:
        r["lost"] = r["failed"] + r["exposed"]
    km_lines(axes[0], fixed_rows, "keys", "lost")
    axes[0].set_yscale("symlog", linthresh=10)
    axes[0].set_ylim(bottom=0)
    axes[0].set_title("Fixed reserve: failed + exposed messages")
    axes[0].set_xlabel("Reserve size (keys of 256 bits)")
    km_lines(axes[1], scale_rows, "scale", "otp_share_control")
    axes[1].set_title("Rate-aware: control messages on OTP")
    axes[1].set_ylim(0.7, 1.0)
    km_lines(axes[2], scale_rows, "scale", "wasted_kbit")
    axes[2].set_title("Rate-aware: key bits wasted (kbit)")
    for ax in axes[1:]:
        ax.set_xlabel("Safe-time multiplier (1 = 20 / 60 / 120 s)")
    legend_on_top(fig, axes[0])
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    finish(fig, "fig_tuning.png")


ROBUST_STYLE = {      # colour, marker, line style, label
    "fixed30": ("#eb6834", "s", "-", "Fixed reserve, 30 keys"),
    "fixed_tuned": ("#eb6834", "s", "--", "Fixed reserve, tuned at normal traffic"),
    "classfixed_tuned": ("#6250d6", "^", "-", "Class-aware fixed, tuned at normal traffic"),
    "ours": ("#2a78d6", "o", "-", "Rate-aware (ours), not tuned"),
}


def chart_robustness(rows):
    rows = [r for r in rows if str(r["condition"]).startswith("traffic")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    for ax, key, title in ((axes[0], "failed", "Failed messages per run"),
                           (axes[1], "otp_share_control", "Control messages protected by OTP")):
        for variant, (color, marker, dash, label) in ROBUST_STYLE.items():
            pts = [(r["traffic_scale"], r[key]) for r in rows if r["variant"] == variant]
            ax.plot(*zip(*pts), color=color, marker=marker, linestyle=dash, markersize=6, linewidth=2,
                    markeredgecolor=SURFACE, markeredgewidth=1.2, label=label)
        ax.set_title(title)
        ax.set_xlabel("Traffic compared with the traffic used for tuning (x)")
    axes[0].set_yscale("symlog", linthresh=10)
    axes[0].set_ylim(bottom=0)
    lowest = min(r["otp_share_control"] for r in rows)
    axes[1].set_ylim(max(0.0, math.floor((lowest - 0.05) * 10) / 10), 1.0)     # never cut a line off
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, labelcolor=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    finish(fig, "fig_robustness.png")


def chart_timeline(p, seed=1):
    fig, axes = plt.subplots(len(NAMES), 1, figsize=(10, 8), sharex=True, sharey=True)
    for ax, name in zip(axes, NAMES):
        run = simulate(name, p, seed, record=True)
        stock = [v / 1000 for v in run.timeline["stock"]]
        ax.axvspan(p.attack_start, p.attack_start + p.attack_len, color="#e1e0d9", zorder=0)
        ax.plot(stock, color=COLORS[name], linewidth=1.8)
        s = run.summary
        ax.set_title(f"{LABELS[name]}   failed {s['failed']:,}   exposed {s['exposed']:,}   "
                     f"control OTP {s['otp_share_control']:.0%}", fontsize=9.5)
        ax.set_ylabel("kbit")
    axes[-1].set_xlabel("Time (s). Grey band = attack: no new keys arrive")
    fig.suptitle(f"Key tank over one hour, {p.km:.0f} km fibre", y=0.995, x=0.01, ha="left", fontweight="bold",
                 color=INK)
    fig.tight_layout()
    finish(fig, "fig_timeline.png")


def draw_all():
    style()
    chart_distance(load_csv("distance.csv"))
    chart_attack(load_csv("attack_length.csv"))
    chart_tuning(load_csv("fixed_reserve_sweep.csv"), load_csv("safe_scale_sweep.csv"))
    chart_robustness(load_csv("robustness.csv"))
    chart_timeline(replace(Params(), km=30))


# ---------------------------------------------------------------- experiments

def tune(name, p, field, candidates):
    """Pick the candidate setting that scores best on the tuning seeds."""
    on_tune = {c: evaluate(name, replace(p, **{field: c}), TUNE_SEEDS) for c in candidates}
    return min(candidates, key=lambda c: score(on_tune[c]))


def run_robustness():
    """Thresholds tuned at 30 km with normal traffic, then tested when the traffic or the wind changes."""
    base = replace(Params(), km=30)
    k = tune("fixed", base, "fixed_reserve_keys", RESERVES)
    kc = tune("classfixed", base, "fixed_reserve_keys", RESERVES)
    variants = (("fixed30", "fixed", replace(base, fixed_reserve_keys=30), 30),
                ("fixed_tuned", "fixed", replace(base, fixed_reserve_keys=k), k),
                ("classfixed_tuned", "classfixed", replace(base, fixed_reserve_keys=kc), kc),
                ("ours", "ours", base, 1.0))
    bursts = tuple((t, 60, 3.0) for t in range(300, 3600, 600))
    conditions = [(f"traffic x{s}", s, replace(base, traffic_scale=s)) for s in (0.5, 1.0, 1.5, 2.0, 3.0)]
    conditions += [("wind 0.3", 1.0, replace(base, wind_sigma=0.3)), ("bursts 3x for 60 s", 1.0, replace(base, bursts=bursts))]
    rows = []
    for label, scale, cond in conditions:
        for variant, name, p, setting in variants:
            rows.append({"condition": label, "traffic_scale": scale, "variant": variant, "setting": setting,
                         **evaluate(name, replace(p, traffic_scale=cond.traffic_scale, wind_sigma=cond.wind_sigma,
                                                  bursts=cond.bursts), TEST_SEEDS)})
    save_csv("robustness.csv", rows)


def run_all():
    base = replace(Params(), km=30)
    print("distance sweep ...")
    save_csv("distance.csv", sweep("km", DISTANCES, lambda km: replace(Params(), km=km)))

    print("attack length / strength ...")
    save_csv("attack_length.csv", sweep("attack_len", (0, 120, 300, 600, 1200), lambda n: replace(base, attack_len=n)))
    save_csv("attack_strength.csv", sweep("attack_strength", (0.1, 0.2, 0.3, 0.4, 1.0),
                                          lambda s: replace(base, attack_strength=s)))

    print("traffic, wind, bursts, priority ...")
    save_csv("traffic.csv", sweep("traffic_scale", (0.5, 1.0, 1.5, 2.0), lambda s: replace(base, traffic_scale=s)))
    save_csv("wind.csv", sweep("wind_sigma", (0.0, 0.1, 0.2, 0.3), lambda s: replace(base, wind_sigma=s)))
    save_csv("bursts.csv", sweep("burst", ("none", "3x for 60 s every 10 min"),
                                 lambda b: replace(base, bursts=() if b == "none" else
                                                   tuple((t, 60, 3.0) for t in range(300, 3600, 600)))))
    normal = sweep("priority", ("as in Qian",), lambda _: base)
    flipped = sweep("priority", ("reversed",), lambda _: replace(base, classes=reversed_priority()))
    save_csv("priority.csv", normal + flipped)

    print("tuning on separate seeds ...")
    fixed_rows, scale_rows, tuned = [], [], []
    for km in (20, 30, 40):
        p = replace(Params(), km=km)
        best_k = tune("fixed", p, "fixed_reserve_keys", RESERVES)
        best_c = tune("classfixed", p, "fixed_reserve_keys", RESERVES)
        best_s = tune("ours", p, "safe_scale", SCALES)
        for k in RESERVES:
            fixed_rows.append({"km": km, "keys": k, **evaluate("fixed", replace(p, fixed_reserve_keys=k), TEST_SEEDS)})
        for s in SCALES:
            scale_rows.append({"km": km, "scale": s, **evaluate("ours", replace(p, safe_scale=s), TEST_SEEDS)})
        for label, name, q, value in (
                ("Fixed reserve, 30 keys (Alshowkan)", "fixed", p, 30),
                (f"Fixed reserve, tuned ({best_k} keys)", "fixed", replace(p, fixed_reserve_keys=best_k), best_k),
                (f"Class-aware fixed, tuned ({best_c} keys)", "classfixed",
                 replace(p, fixed_reserve_keys=best_c), best_c),
                ("Rate-aware, default", "ours", p, 1.0),
                (f"Rate-aware, tuned (x{best_s})", "ours", replace(p, safe_scale=best_s), best_s)):
            tuned.append({"km": km, "variant": label, "setting": value, **evaluate(name, q, TEST_SEEDS)})
    save_csv("fixed_reserve_sweep.csv", fixed_rows)
    save_csv("safe_scale_sweep.csv", scale_rows)
    save_csv("tuned_comparison.csv", tuned)

    print("robustness to changed traffic and wind ...")
    run_robustness()

    for r in tuned:
        print(f"{r['km']:>3} km  {r['variant']:42s} failed {r['failed']:>8.1f}  exposed {r['exposed']:>6.1f}  "
              f"control OTP {r['otp_share_control']:.3f}  OTP {r['otp_share']:.3f}  wasted {r['wasted_kbit']:.0f}k")


def main():
    global POOL
    if "--charts-only" not in sys.argv:
        with ProcessPoolExecutor() as POOL:
            run_all()
    draw_all()
    print("saved to", RESULTS)


if __name__ == "__main__":
    main()

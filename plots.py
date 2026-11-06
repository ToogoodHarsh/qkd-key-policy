"""Publication-quality visualization module generating Figures 1 to 16
for the scientific evaluation of QKD key-usage policies.
Exports figures at 300 DPI in PNG format to results/.
"""
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import ScalarFormatter

from params import Params, reversed_priority
from policies import LABELS, NAMES
from simulator import simulate

RESULTS = Path(__file__).parent / "results"

# Visual theme constants
COLORS = {
    "ours": "#2a78d6",          # blue
    "fixed": "#eb6834",         # orange/coral
    "qian": "#1baf7a",          # teal/green
    "qian_noreuse": "#7e57c2",  # purple
    "otp_only": "#eda100",      # amber
    "aes_only": "#e87ba4",      # pink/magenta
    "classfixed": "#546e7a",    # slate grey
}
MARKERS = {
    "ours": "o", "fixed": "s", "qian": "^", "qian_noreuse": "v",
    "otp_only": "D", "aes_only": "<", "classfixed": "p"
}
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def set_plot_style():
    plt.rcParams.update({
        "font.family": ["Segoe UI", "Arial", "DejaVu Sans"], "font.size": 9.5,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.titlesize": 10.5,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True,
        "grid.color": GRID, "grid.linewidth": 0.8, "text.color": INK,
    })


def save_fig(fig, filename):
    RESULTS.mkdir(exist_ok=True)
    fig.savefig(RESULTS / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- Figures 1 to 9 (Timeline & Distributions)

def fig1_inventory_timeline(p=None, seed=1):
    """FIGURE 1: Key pool inventory over time for all five policies."""
    set_plot_style()
    if p is None:
        p = Params(km=30)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.axvspan(p.attack_start, p.attack_start + p.attack_len, color="#e4e3dd", alpha=0.8,
               label="Attack Window (Key Gen Interrupted)", zorder=1)
    
    for name in NAMES:
        run = simulate(name, p, seed=seed, record=True)
        stock_kbit = [s / 1000 for s in run.timeline["stock"]]
        ax.plot(stock_kbit, label=LABELS[name], color=COLORS[name],
                linewidth=2.2 if name == "ours" else 1.6, zorder=3 if name == "ours" else 2)

    ax.set_title("Figure 1: Key Pool Inventory Over Time (30 km Link, 300 s Intercept-Resend Attack)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Available Secret Key Stock (kbit)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig1_inventory_timeline.png")


def fig2_usage_distribution(distance_rows):
    """FIGURE 2: OTP, AES, and Failed usage distribution across policies at 30 km."""
    set_plot_style()
    r30 = [r for r in distance_rows if r.get("km") == 30]
    if not r30:
        return
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    
    policies = [n for n in NAMES if any(r["policy"] == n for r in r30)]
    x = np.arange(len(policies))
    width = 0.55

    otp_shares = [next(r["otp_share"] for r in r30 if r["policy"] == n) * 100 for n in policies]
    aes_shares = [next(r["aes_share"] for r in r30 if r["policy"] == n) * 100 for n in policies]
    failed_shares = [max(0.0, 100 - o - a) for o, a in zip(otp_shares, aes_shares)]

    ax.bar(x, otp_shares, width, label="OTP Protected (%)", color="#2a78d6")
    ax.bar(x, aes_shares, width, bottom=otp_shares, label="AES-256 Fallback (%)", color="#eb6834")
    ax.bar(x, failed_shares, width, bottom=[o + a for o, a in zip(otp_shares, aes_shares)],
           label="Failed / Dropped (%)", color="#d32f2f")

    ax.set_title("Figure 2: Cryptographic Protection Distribution by Policy (30 km Link)")
    ax.set_ylabel("Message Share (%)")
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[n] for n in policies])
    ax.set_ylim(0, 105)
    ax.legend(loc="lower right", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig2_usage_distribution.png")


def fig3_depletion_time(distance_rows):
    """FIGURE 3: Key pool depletion time comparison (minimum time-to-empty across distances)."""
    set_plot_style()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for name in ("ours", "fixed", "qian", "otp_only"):
        pts = [(r["km"], min(r.get("min_time_left_s", 0), 120)) for r in distance_rows if r["policy"] == name]
        pts.sort(key=lambda t: t[0])
        if pts:
            ax.plot(*zip(*pts), label=LABELS[name], color=COLORS[name], marker=MARKERS[name],
                    linewidth=2.0, markersize=6)
    
    ax.set_title("Figure 3: Minimum Predicted Depletion Horizon (T_depletion) Across Fibre Lengths")
    ax.set_xlabel("Fibre Distance (km)")
    ax.set_ylabel("Min Depletion Time (s)")
    ax.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig3_depletion_time.png")


def fig4_delivery_ratio(distance_rows):
    """FIGURE 4: Overall message delivery ratio by policy across distances."""
    set_plot_style()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for name in NAMES:
        pts = []
        for r in distance_rows:
            if r["policy"] == name:
                dr = r.get("delivery_ratio")
                if dr is None:
                    sent_est = r.get("sent", 288000.0)
                    failed = r.get("failed", 0.0)
                    dr = max(0.0, (sent_est - failed) / sent_est) if sent_est else 1.0
                pts.append((r["km"], dr * 100))
        pts.sort(key=lambda t: t[0])
        if pts:
            ax.plot(*zip(*pts), label=LABELS[name], color=COLORS[name], marker=MARKERS[name],
                    linewidth=2.0 if name == "ours" else 1.5, markersize=6)

    ax.set_title("Figure 4: Overall Message Delivery Ratio Across Fibre Lengths")
    ax.set_xlabel("Fibre Distance (km)")
    ax.set_ylabel("Delivery Ratio (%)")
    ax.set_ylim(40, 102)
    ax.legend(loc="lower left", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig4_delivery_ratio.png")


def fig5_high_priority_delivery(distance_rows):
    """FIGURE 5: High-priority (Frequency Control) delivery ratio across distances."""
    set_plot_style()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for name in NAMES:
        pts = []
        for r in distance_rows:
            if r["policy"] == name:
                dr = r.get("delivery_ratio_control")
                if dr is None:
                    ctrl_sent_est = 36000.0
                    failed_ctrl = r.get("failed_control", 0.0)
                    dr = max(0.0, (ctrl_sent_est - failed_ctrl) / ctrl_sent_est)
                pts.append((r["km"], dr * 100))
        pts.sort(key=lambda t: t[0])
        if pts:
            ax.plot(*zip(*pts), label=LABELS[name], color=COLORS[name], marker=MARKERS[name],
                    linewidth=2.0 if name == "ours" else 1.5, markersize=6)

    ax.set_title("Figure 5: High-Priority Control Traffic Delivery Ratio")
    ax.set_xlabel("Fibre Distance (km)")
    ax.set_ylabel("Control Delivery Ratio (%)")
    ax.set_ylim(60, 102)
    ax.legend(loc="lower left", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig5_high_priority_delivery.png")


def fig6_exposed_messages(distance_rows):
    """FIGURE 6: Exposed messages and key reuse comparison."""
    set_plot_style()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for name in ("qian", "fixed", "ours", "otp_only", "aes_only"):
        pts = [(r["km"], r.get("exposed", 0)) for r in distance_rows if r["policy"] == name]
        pts.sort(key=lambda t: t[0])
        if pts:
            ax.plot(*zip(*pts), label=LABELS[name], color=COLORS[name], marker=MARKERS[name],
                    linewidth=2.0, markersize=6)

    ax.set_title("Figure 6: Exposed Messages (Key Material Reused Across Packets)")
    ax.set_xlabel("Fibre Distance (km)")
    ax.set_ylabel("Exposed Messages Count")
    ax.set_yscale("symlog", linthresh=10)
    ax.legend(loc="upper left", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig6_exposed_messages.png")


def fig7_rates_over_time(p=None, seed=1):
    """FIGURE 7: Key generation rate and key consumption rate over time for Rate-Aware policy."""
    set_plot_style()
    if p is None:
        p = Params(km=30)
    run = simulate("ours", p, seed=seed, record=True)
    tl = run.timeline
    fig, ax = plt.subplots(figsize=(10, 4.5))

    ax.axvspan(p.attack_start, p.attack_start + p.attack_len, color="#e4e3dd", alpha=0.8,
               label="Attack (0 key gen)", zorder=1)
    ax.plot([s / 1000 for s in tl["supply"]], label="Key Supply Rate (kbit/s)",
            color="#1baf7a", linewidth=1.5, alpha=0.85)

    ax.set_title("Figure 7: Instantaneous Key Generation Rate (with Wind Fluctuation and Attack)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Key Rate (kbit/s)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig7_rates_over_time.png")


def fig8_switching_timeline(p=None, seed=1):
    """FIGURE 8: Adaptive switching timeline for the proposed policy across all 3 classes."""
    set_plot_style()
    if p is None:
        p = Params(km=30)
    run = simulate("ours", p, seed=seed, record=True)
    tl = run.timeline
    fig, axes = plt.subplots(3, 1, figsize=(10, 6), sharex=True)

    class_names = [c.name for c in p.classes]
    class_labels = {"control": "Control (High Priority)", "state": "State Estimation (Med Priority)",
                    "market": "Market (Low Priority)"}

    for ax, cname in zip(axes, class_names):
        modes = tl.get(cname, [])
        ax.axvspan(p.attack_start, p.attack_start + p.attack_len, color="#e4e3dd", alpha=0.8)
        # 0 is OTP, 1 is AES
        ax.plot(modes, color="#2a78d6", linewidth=1.8)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["OTP", "AES"])
        ax.set_ylabel(class_labels.get(cname, cname), fontsize=8.5)
        ax.set_ylim(-0.3, 1.3)

    axes[0].set_title("Figure 8: Class-Wise Adaptive Switching Timeline (Rate-Aware Policy)")
    axes[-1].set_xlabel("Time (s). Shaded region = Eavesdropping attack.")
    fig.tight_layout()
    save_fig(fig, "fig8_switching_timeline.png")


def fig9_attack_lifecycle(p=None, seed=1):
    """FIGURE 9: Attack onset, QBER spike, fallback activation, and recovery timeline."""
    set_plot_style()
    if p is None:
        p = Params(km=30)
    run = simulate("ours", p, seed=seed, record=True)
    tl = run.timeline
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True)

    # Upper panel: Key supply
    ax1.axvspan(p.attack_start, p.attack_start + p.attack_len, color="#fee8e8", alpha=0.8,
                label="Intercept-Resend Attack Window")
    ax1.plot([s / 1000 for s in tl["supply"]], color="#1baf7a", label="Secret Key Rate (kbit/s)")
    ax1.set_ylabel("Rate (kbit/s)")
    ax1.set_title("Figure 9: Attack Lifecycle — Key Disruption and Safe Fallback Activation")
    ax1.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID)

    # Lower panel: Key stock & Market fallback
    ax2.axvspan(p.attack_start, p.attack_start + p.attack_len, color="#fee8e8", alpha=0.8)
    ax2.plot([s / 1000 for s in tl["stock"]], color="#2a78d6", label="Key Tank Stock (kbit)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Stock (kbit)")
    ax2.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID)

    fig.tight_layout()
    save_fig(fig, "fig9_attack_lifecycle.png")


# ---------------------------------------------------------------- Figures 10 to 16 (Scenarios)

def fig10_distance_performance(distance_rows):
    """FIGURE 10: Policy performance across fibre distances (2x3 panel breakdown)."""
    set_plot_style()
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    panels = [
        ("failed",            "Failed messages per run",                   True),
        ("exposed",           "Exposed messages (key reused)",              True),
        ("otp_share_control", "Control messages on OTP (%)",               False),
        ("otp_share_state",   "State messages on OTP (%)",                 False),
        ("otp_share_market",  "Market messages on OTP (%)",                False),
        ("wasted_kbit",       "Key bits wasted (kbit)",                     False),
    ]
    for ax, (key, title, symlog) in zip(axes.flat, panels):
        for name in NAMES:
            pts = [(r["km"], r[key] if not key.startswith("otp_share") else r[key] * 100)
                   for r in distance_rows if r["policy"] == name]
            pts.sort(key=lambda t: t[0])
            if pts:
                ax.plot(*zip(*pts), color=COLORS[name], marker=MARKERS[name], markersize=5, linewidth=1.8,
                        label=LABELS[name])
        ax.set_title(title)
        if symlog:
            ax.set_yscale("symlog", linthresh=10)
            ax.set_ylim(bottom=0)
        elif key.startswith("otp_share"):
            ax.set_ylim(0, 105)

    for ax in axes[1]:
        ax.set_xlabel("Fibre Distance (km)")
    
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, labelcolor=INK2)
    fig.suptitle("Figure 10: Comprehensive Policy Performance Across Fibre Distances (5–40 km)", y=0.01,
                 color=INK2, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    save_fig(fig, "fig10_distance_performance.png")


def fig11_traffic_performance(traffic_rows):
    """FIGURE 11: Performance across traffic load scaling (0.5x to 2.0x)."""
    set_plot_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    for name in NAMES:
        pts1 = [(r["traffic_scale"], r["failed"]) for r in traffic_rows if r["policy"] == name]
        pts2 = [(r["traffic_scale"], r["otp_share_control"] * 100) for r in traffic_rows if r["policy"] == name]
        pts1.sort(key=lambda t: t[0])
        pts2.sort(key=lambda t: t[0])
        if pts1:
            ax1.plot(*zip(*pts1), color=COLORS[name], marker=MARKERS[name], label=LABELS[name], linewidth=1.8)
        if pts2:
            ax2.plot(*zip(*pts2), color=COLORS[name], marker=MARKERS[name], label=LABELS[name], linewidth=1.8)

    ax1.set_title("Failed Messages vs Traffic Load")
    ax1.set_xlabel("Traffic Scale Factor (x)")
    ax1.set_ylabel("Failed Messages")
    ax1.set_yscale("symlog", linthresh=10)
    ax1.set_ylim(bottom=0)

    ax2.set_title("Control Traffic on OTP vs Traffic Load")
    ax2.set_xlabel("Traffic Scale Factor (x)")
    ax2.set_ylabel("Control OTP Share (%)")
    ax2.set_ylim(60, 102)

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False)
    fig.suptitle("Figure 11: Performance Across Smart-Grid Traffic Intensities (0.5x to 2.0x)", y=0.01,
                 color=INK2, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.92))
    save_fig(fig, "fig11_traffic_performance.png")


def fig12_fluctuation_performance(wind_rows):
    """FIGURE 12: Performance under key-generation fluctuations (wind sigma)."""
    set_plot_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    for name in NAMES:
        pts1 = [(r["wind_sigma"], r["failed"]) for r in wind_rows if r["policy"] == name]
        pts2 = [(r["wind_sigma"], r["otp_share_control"] * 100) for r in wind_rows if r["policy"] == name]
        pts1.sort(key=lambda t: t[0])
        pts2.sort(key=lambda t: t[0])
        if pts1:
            ax1.plot(*zip(*pts1), color=COLORS[name], marker=MARKERS[name], label=LABELS[name], linewidth=1.8)
        if pts2:
            ax2.plot(*zip(*pts2), color=COLORS[name], marker=MARKERS[name], label=LABELS[name], linewidth=1.8)

    ax1.set_title("Failed Messages vs Wind Volatility")
    ax1.set_xlabel("Wind Swing Sigma (σ)")
    ax1.set_ylabel("Failed Messages")
    ax1.set_yscale("symlog", linthresh=10)

    ax2.set_title("Control Traffic on OTP vs Wind Volatility")
    ax2.set_xlabel("Wind Swing Sigma (σ)")
    ax2.set_ylabel("Control OTP Share (%)")
    ax2.set_ylim(70, 102)

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False)
    fig.suptitle("Figure 12: Robustness to Key Generation Fluctuation on Aerial Fibre Links", y=0.01,
                 color=INK2, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.92))
    save_fig(fig, "fig12_fluctuation_performance.png")


def fig13_attack_performance(attack_rows):
    """FIGURE 13: Performance under short and persistent attacks (0 s to 1200 s)."""
    set_plot_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    for name in NAMES:
        pts1 = [(r["attack_len"], r["failed"]) for r in attack_rows if r["policy"] == name]
        pts2 = [(r["attack_len"], r["otp_share_control"] * 100) for r in attack_rows if r["policy"] == name]
        pts1.sort(key=lambda t: t[0])
        pts2.sort(key=lambda t: t[0])
        if pts1:
            ax1.plot(*zip(*pts1), color=COLORS[name], marker=MARKERS[name], label=LABELS[name], linewidth=1.8)
        if pts2:
            ax2.plot(*zip(*pts2), color=COLORS[name], marker=MARKERS[name], label=LABELS[name], linewidth=1.8)

    ax1.set_title("Failed Messages vs Attack Duration")
    ax1.set_xlabel("Attack Duration (s)")
    ax1.set_ylabel("Failed Messages")
    ax1.set_yscale("symlog", linthresh=10)

    ax2.set_title("Control OTP Share vs Attack Duration")
    ax2.set_xlabel("Attack Duration (s)")
    ax2.set_ylabel("Control OTP Share (%)")
    ax2.set_ylim(60, 102)

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False)
    fig.suptitle("Figure 13: Impact of Eavesdropping Attack Duration on Link Resiliency (30 km)", y=0.01,
                 color=INK2, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.92))
    save_fig(fig, "fig13_attack_performance.png")


def fig14_priority_sensitivity(priority_rows):
    """FIGURE 14: Priority sensitivity comparison (standard vs reversed importance order)."""
    set_plot_style()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    orders = ["as in Qian", "reversed"]
    x = np.arange(len(orders))
    width = 0.15

    for idx, name in enumerate(("ours", "fixed", "qian", "otp_only")):
        ctrl_otp = []
        for o in orders:
            val = next((r["otp_share_control"] * 100 for r in priority_rows if r["priority"] == o and r["policy"] == name), 0)
            ctrl_otp.append(val)
        ax.bar(x + (idx - 1.5) * width, ctrl_otp, width, label=LABELS[name], color=COLORS[name])

    ax.set_title("Figure 14: Control OTP Preservation Under Standard vs Reversed Priority Order")
    ax.set_ylabel("Control OTP Share (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(["Standard (Control > State > Market)", "Reversed (Market > State > Control)"])
    ax.set_ylim(0, 105)
    ax.legend(loc="lower right", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.tight_layout()
    save_fig(fig, "fig14_priority_sensitivity.png")


def fig15_combined_stress(stress_rows):
    """FIGURE 15: Combined stress-test comparison across policies."""
    set_plot_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    policies = [n for n in NAMES if any(r.get("policy") == n for r in stress_rows)]
    x = np.arange(len(policies))
    width = 0.55

    fails = [next((r["failed"] for r in stress_rows if r["policy"] == n), 0) for n in policies]
    ctrl_otps = [next((r["otp_share_control"] * 100 for r in stress_rows if r["policy"] == n), 0) for n in policies]

    ax1.bar(x, fails, width, color=[COLORS[n] for n in policies])
    ax1.set_title("Failed Messages Under Combined Stress")
    ax1.set_ylabel("Failed Messages")
    ax1.set_yscale("symlog", linthresh=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels([LABELS[n] for n in policies], rotation=15)

    ax2.bar(x, ctrl_otps, width, color=[COLORS[n] for n in policies])
    ax2.set_title("Control OTP Share Under Stress (%)")
    ax2.set_ylabel("Control OTP Share (%)")
    ax2.set_ylim(0, 105)
    ax2.set_xticks(x)
    ax2.set_xticklabels([LABELS[n] for n in policies], rotation=15)

    fig.suptitle("Figure 15: Multi-Factor Stress Test (30 km, 2x Traffic, σ=0.2 Wind, 600 s Attack)", y=0.01,
                 color=INK2, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.92))
    save_fig(fig, "fig15_combined_stress.png")


def fig16_tuning_sensitivity(fixed_rows, scale_rows):
    """FIGURE 16: Sensitivity of the proposed policy to safe-time scale and reserve thresholds."""
    set_plot_style()
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))
    blues = ("#86b6ef", "#2a78d6", "#104281")

    # Panel 1: Fixed reserve lost
    for km, color in zip((20, 30, 40), blues):
        pts = [(r["keys"], r["failed"] + r.get("exposed", 0)) for r in fixed_rows if r["km"] == km]
        pts.sort(key=lambda t: t[0])
        if pts:
            axes[0].plot(*zip(*pts), color=color, marker="s", label=f"{km} km", linewidth=1.8)
    axes[0].set_xscale("log")
    axes[0].set_yscale("symlog", linthresh=10)
    axes[0].set_title("Fixed Reserve: Lost Messages")
    axes[0].set_xlabel("Reserve Size (keys)")

    # Panel 2: Rate-aware control OTP
    for km, color in zip((20, 30, 40), blues):
        pts = [(r["scale"], r["otp_share_control"] * 100) for r in scale_rows if r["km"] == km]
        pts.sort(key=lambda t: t[0])
        if pts:
            axes[1].plot(*zip(*pts), color=color, marker="o", label=f"{km} km", linewidth=1.8)
    axes[1].set_xscale("log")
    axes[1].set_title("Rate-Aware: Control on OTP (%)")
    axes[1].set_xlabel("Safe Time Multiplier")
    axes[1].set_ylim(70, 102)

    # Panel 3: Rate-aware wasted key bits
    for km, color in zip((20, 30, 40), blues):
        pts = [(r["scale"], r["wasted_kbit"]) for r in scale_rows if r["km"] == km]
        pts.sort(key=lambda t: t[0])
        if pts:
            axes[2].plot(*zip(*pts), color=color, marker="o", label=f"{km} km", linewidth=1.8)
    axes[2].set_xscale("log")
    axes[2].set_title("Rate-Aware: Key Overflow (kbit)")
    axes[2].set_xlabel("Safe Time Multiplier")

    axes[0].legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID)
    fig.suptitle("Figure 16: Parameter Tuning and Sensitivity of Depletion Thresholds", y=0.01,
                 color=INK2, fontsize=9.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.92))
    save_fig(fig, "fig16_tuning_sensitivity.png")

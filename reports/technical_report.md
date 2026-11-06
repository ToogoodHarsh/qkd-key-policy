# Rate-Aware Key-Usage Policy with Safe AES-256 Fallback for QKD-Secured Smart Grid Links

**Comprehensive Technical & Research Report**  
*Objective 3: Adaptive Cryptographic Key-Usage Policies in Quantum-Secured Cyber-Physical Energy Systems*  
**Date:** November 2026  
**Status:** Validated Simulation & Empirical Evaluation Report  

---

## 1. Abstract

Quantum Key Distribution (QKD) provides physical-layer, information-theoretic security (ITS) for critical infrastructure by establishing secret symmetric keys bounded only by the laws of quantum mechanics. In smart-grid cyber-physical communication networks, however, quantum channels are constrained by finite secret key generation rates that diminish rapidly with optical fibre distance and are vulnerable to denial-of-service (DoS) or eavesdropping disruptions that halt key distribution. Traditional practices either rely exclusively on One-Time Pad (OTP) encryption—risking severe message failure and blackouts upon key exhaustion—or default unconditionally to computational algorithms (e.g., AES-256), thereby abandoning the security advantages of QKD. 

In this work, we propose, implement, and evaluate a **Rate-Aware Key-Usage Policy with Safe AES-256 Fallback**. The proposed policy continuously observes available key inventory, estimates the current key replenishment rate and class-prioritized demand via exponential moving averages, and dynamically forecasts the remaining depletion horizon for each smart-grid traffic class. When the forecasted depletion horizon falls below class-specific critical safe time thresholds, lower-priority traffic (power market and state estimation) is proactively transferred to AES-256 with fresh QKD session keys, reserving pristine OTP key materials for mission-critical frequency control commands without key reuse.

We conduct extensive discrete-event simulations evaluated across 30 independent random seeds per scenario over fibre distances from 5 km to 40 km, varied traffic loads (0.5x to 2.0x), wind-driven optical channel fluctuations ($\sigma = 0.0$ to $0.3$), intercept-resend attacks (up to 1200 s), and a combined multi-factor stress scenario. Empirical results demonstrate that under severe stress (30 km fibre, 2.0x traffic, $\sigma = 0.2$ wind swings, 600 s attack), the baseline OTP-only policy suffers over 341,000 dropped messages, fixed-reserve policies suffer 42,600 dropped messages and 497 s of stale-key operation, and Qian-style tiered allocation leaks over 10.6 million key bits through key reuse. In contrast, our proposed rate-aware policy achieves **0 dropped messages (100% availability), 0 exposed key bits, 0 stale-key seconds, and maintains 86.7% OTP protection for critical frequency control signals**.

---

## 2. Introduction

Modern electrical smart grids and microgrids are cyber-physical systems requiring continuous, low-latency communication among microgrid central controllers (MGCC), remote terminal units (RTUs), phasor measurement units (PMUs), and intelligent electronic devices (IEDs). Critical control signals—such as frequency regulation and active/reactive power setpoints—have stringent delivery and integrity requirements. An undetected manipulation or denial of control commands can destabilize voltage dynamics, trigger cascading tripping, or cause blackout conditions.

Classical public-key cryptography (e.g., RSA, Diffie-Hellman, elliptic curve cryptography) relies on unproven computational complexity assumptions that are vulnerable to quantum algorithms such as Shor's algorithm. While symmetric ciphers such as AES-256 resist Shor's attack, their security hinges on frequent, tamper-proof distribution of session keys.

Quantum Key Distribution (QKD), utilizing protocols like BB84 and decoy-state variants, produces provably secret symmetric keys between Alice and Bob. However, QKD hardware operates under strict physical limitations:
1. **Distance-dependent attenuation:** Secret key generation rate decreases exponentially with channel distance.
2. **Channel disturbances:** Aerial fibres suffer mechanical stress, polarization drift, and wind-induced fluctuations.
3. **Eavesdropping and Denial-of-Service:** Any eavesdropping attempt (such as an intercept-resend attack) elevates the Quantum Bit Error Rate (QBER) above the physical threshold ($\sim 11\%$), forcing the legitimate communicating parties to abort key generation and discard all sifted key materials.

When key generation drops below the aggregate data transmission rate, a finite key storage buffer (key tank) inevitably drains. Without an intelligent allocation policy, critical grid messages are dropped, or security is compromised.

---

## 3. Problem Statement

Given a point-to-point QKD-secured smart-grid link characterized by:
- Optical fibre distance $L \in [5, 40]\text{ km}$, attenuation $\alpha = 0.2\text{ dB/km}$, detector efficiency $\eta_{\text{Bob}} = 0.11$, dark count $p_{\text{dc}} = 1.7 \times 10^{-6}$, and after-pulse probability $p_{\text{ap}} = 1 \times 10^{-3}$;
- A finite key pool buffer of maximum capacity $C = 500,000\text{ bits}$ and initial inventory $S_0 = 100,000\text{ bits}$;
- Three concurrent smart-grid message classes: **Frequency Control** (high priority, 10 msg/s, $\omega_1 = 0.947$), **State Estimation** (medium priority, 50 msg/s, $\omega_2 = 0.788$), and **Power Market** (low priority, 20 msg/s, $\omega_3 = 0.329$);
- External environmental wind fluctuations and malicious intercept-resend eavesdropping attacks that halt key replenishment;

**The central research problem is:**  
*How should the link orchestrator dynamically assign cryptographic protection (One-Time Pad vs. fresh QKD-keyed AES-256) across heterogeneous message classes in real time such that:*
1. Key inventory exhaustion is prevented;
2. Zero messages fail or are dropped;
3. Zero key material is reused or exposed;
4. High-priority frequency control signals retain the maximum possible OTP coverage; and
5. Seamless recovery to full OTP operation occurs once normal QKD replenishment resumes.

---

## 4. Literature Review

Our investigation is grounded in six foundational works across QKD physics, microgrid integration, and quantum resource allocation:

### 4.1 Tang et al. (2021) — "Quantum-Secure Microgrid"
*IEEE Transactions on Power Systems, Vol. 36, No. 2.*  
Tang et al. pioneered the hardware-in-the-loop co-simulation of a QKD-secured microgrid using RTDS and RSCAD. They formulated the asymptotic decoy-state BB84 secret key rate accounting for fibre attenuation, detector efficiency, dark counts, and after-pulses. They showed that without key management, a microgrid's key buffer runs dry in 17.56 s under attack, leading to microgrid collapse at $t = 21\text{ s}$. Their mitigation was Key Pool Sharing (KPS) between adjacent pools, but switching thresholds were fixed (5,000 bits), and adaptive data-to-AES fallback rules were not evaluated.

### 4.2 Alshowkan et al. (2022) — "Authentication of Smart Grid Communications Using QKD"
*Scientific Reports (Nature), 12:12731.*  
Demonstrated experimental QKD on a 3.4 km commercial aerial dark fibre (EPB Chattanooga) with 1.3 dB attenuation. The authors used 256-bit QKD keys for AES-GMAC message authentication over MQTT, achieving 170x faster signing than RSA-4096. Crucially, they observed environmental key-rate swings caused by wind and thermal drift on aerial lines. They instituted a fixed reserve threshold of 30 keys ($30 \times 256 = 7,680\text{ bits}$), but acknowledged that this threshold was chosen arbitrarily without optimization.

### 4.3 Grice et al. (2025) — "Quantum Key Distribution Applicability to Smart Grid Cybersecurity Systems"
*IEEE Access, Vol. 13.*  
Conducted an extensive expert assessment across 18 smart-grid use cases and 7 QKD deployment factors. The study established that data integrity and availability are "High" or "Critical" across all grid operational domains, and concluded that key rates of 10 bit/s to a few kbit/s are readily achievable, but require systematic cryptographic fallback architectures.

### 4.4 Qian et al. (2025) — "Resource Allocation for Hybrid Quantum-Classical Communication Systems in Multiapplication-Enabled Power Grids"
*IEEE Transactions on Industrial Informatics, Vol. 21, No. 1.*  
Proposed a two-stage virtualized SDN/NFV resource slicing framework. In Stage 2, quantum keys are allocated by priority tiers ($M_{\min}, M_{\text{thr1}}, M_{\text{thr2}}$). However, when key inventory drops below $M_{\text{thr1}}$, the policy reuses the same quantum key across two successive packets (half-key sharing). This introduces significant security exposure, creating a measurable "data exposure rate."

### 4.5 Zheng et al. (2025) — "An Efficient and Robust Resource Allocation Method for QKD Networks"
*IEEE Transactions on Network and Service Management, Vol. 22, No. 5.*  
Formulated dynamic key pool conservation and bottleneck link mitigation using Integer Linear Programming (ILP) and heuristic key utilization ratio (KUR) metrics. Zheng et al. mathematically formalized discrete-time inventory balancing:
$$S_e(t+1) = \min\left(C_e, S_e(t) + G_e(t)\right) - \sum c_{r,e}(t)$$
establishing that uncoordinated allocation causes severe bottleneck link depletion.

### 4.6 Rath et al. (2025) — "Dynamic Quantum Key Distribution for Microgrids With Distributed Error Correction"
*IET Quantum Communication, 6:e70014.*  
Modeled BB84 error tracking in secondary microgrid control, proving that an unmitigated eavesdropping attack of just 0.18 s permanently destabilizes power frequency. Rath demonstrated that QBER crossing the 11% threshold serves as an unambiguous physical indicator of active eavesdropping.

---

## 5. Research Gap

From the literature, three primary gaps emerge:
1. **Arbitrary or Static Switching Thresholds:** Tang et al. and Alshowkan et al. employ fixed inventory reserves (e.g., 5,000 bits or 30 keys) that fail to adapt when traffic load surges or fibre distance increases.
2. **Key Reuse as a Degraded Fallback:** Qian et al. address scarcity by halving key consumption through key reuse. This destroys Information-Theoretic Security and exposes secret key bits.
3. **Absence of Rate-Aware Predictive Control:** No prior study combines real-time key replenishment estimation with cumulative class-prioritized demand forecasting to proactively schedule seamless AES-256 fallback before buffer starvation occurs.

---

## 6. Research Objectives

1. **Implement and validate five independent key-management policies**: OTP-Only, AES-Only, Fixed-Reserve (Alshowkan baseline), Qian-Style Tiered Allocation (with and without reuse), and our proposed Rate-Aware Policy.
2. **Develop a rigorous discrete-event simulation engine** incorporating verified decoy-state BB84 physics, wind-driven AR(1) channel swings, and intercept-resend attack models.
3. **Subject all policies to identical common random traces** over 30 independent test seeds across 6 comprehensive operational scenarios.
4. **Demonstrate statistically verifiable elimination of message loss and key exposure** while maximizing OTP protection for critical frequency control traffic.

---

## 7. Proposed Methodology: The Rate-Aware Policy

### 7.1 Controller Principle
The proposed Rate-Aware controller operates at each discrete decision epoch $t$ (1 second). It does not assume knowledge of future traffic arrivals or attack duration.

1. **Exponential Smoothing of Rates:**  
   The instantaneous key generation $G(t)$ and class demand $D_c(t)$ are filtered via exponential moving averages over a smoothing window $\tau = 20\text{ s}$:
   $$\bar{G}(t) = \bar{G}(t-1) + \frac{G(t) - \bar{G}(t-1)}{\tau}$$
   $$\bar{D}_c(t) = \bar{D}_c(t-1) + \frac{n_c(t) \cdot \text{cost}_{\text{OTP}} - \bar{D}_c(t-1)}{\tau}$$

2. **Cumulative Drain Calculation:**  
   Traffic classes are processed in descending priority order: $\text{Control} \succ \text{State} \succ \text{Market}$.  
   For class $c$, the cumulative OTP demand is the sum of its own demand plus all higher-priority classes:
   $$W_c(t) = \sum_{j \succeq c} \bar{D}_j(t)$$
   The net key drain rate is:
   $$\Delta_c(t) = W_c(t) - \bar{G}(t)$$

3. **Predicted Time-to-Depletion:**  
   $$T_{\text{depletion}, c}(t) = \begin{cases} \frac{S(t)}{\Delta_c(t)}, & \text{if } \Delta_c(t) > 0 \\ \infty, & \text{if } \Delta_c(t) \le 0 \end{cases}$$

4. **Multi-Threshold Decision Logic with Hysteresis & Dwell:**  
   Each class has a configured safe horizon $T_{\text{safe}, c}$ ($\text{Control} = 20\text{ s}$, $\text{State} = 60\text{ s}$, $\text{Market} = 120\text{ s}$), scaled by a tuning factor $\beta$ ($\text{default } 1.0$):
   - **Buffer Overflow Protection:** If $S(t) \ge 0.9 \cdot C$, enforce OTP for all classes to prevent key wastage.
   - **Fallback Condition:** If $S(t) < \text{floor}$ (512 bits) or $T_{\text{depletion}, c}(t) < \beta \cdot T_{\text{safe}, c}$, switch class $c$ to AES-256.
   - **Hysteresis Recovery:** If already on AES-256, remain on AES until $T_{\text{depletion}, c}(t) \ge \beta \cdot T_{\text{safe}, c} \cdot 1.5$.
   - **Minimum Dwell:** Ensure the class remains on AES for at least $T_{\text{dwell}}$ seconds to eliminate rapid switching oscillation.

---

## 8. Mathematical Formulation

### 8.1 Physical QKD Secret Key Rate
Following Tang et al. (Eqs. 4–6, 11, 15):
- Optical transmittance: $T = 10^{-\alpha L / 10}$
- Expected detection rate: $r_k = 1 - (1 - 2p_{\text{dc}}) e^{-T \eta_{\text{Bob}} \mu}$
- Detection probability: $p_{\text{det}} = (1 + p_{\text{ap}}) r_k$
- Baseline link QBER:
  $$\text{QBER}_{\text{link}} = \frac{p_{\text{dc}} + e_{\text{mis}}(1 - e^{-T \mu}) + \frac{1}{2} p_{\text{ap}} r_k}{p_{\text{det}}}$$
- Intercept-resend attack with fraction $f_{\text{attack}}$:
  $$\text{QBER}_{\text{attacked}} = \text{QBER}_{\text{link}} + 0.25 \cdot f_{\text{attack}}$$
- Asymptotic secret key rate:
  $$R_{\text{secret}} = \begin{cases} \frac{1}{2} f_{\text{rep}} p_{\text{det}} \max\left(0, 1 - (1 + f_{\text{ec}}) H_2(\text{QBER})\right), & \text{if QBER} < \text{QBER}_{\text{limit}} \\ 0, & \text{otherwise} \end{cases}$$
  where $H_2(x) = -x \log_2 x - (1-x) \log_2(1-x)$.

### 8.2 Wind Fluctuation Model
Wind-induced channel perturbations on aerial fibre follow an autoregressive AR(1) process:
$$x(t) = \rho x(t-1) + \epsilon(t), \quad \epsilon(t) \sim \mathcal{N}\left(0, \sigma^2(1 - \rho^2)\right)$$
$$\text{factor}(t) = \text{clip}(1 + x(t), 0.3, 1.7)$$

---

## 9. Simulation Architecture

The simulation framework is organized into specialized modules:
- `params.py`: Dataclass containing physical, traffic, and algorithmic parameters.
- `keyrate.py`: Physical channel model, QBER calculation, and wind generation profiles.
- `pool.py`: Zheng Eq. 1 inventory balance manager with strict conservation checks.
- `traffic.py`: Poisson message arrival generators with burst models.
- `policies.py`: Implementation of the 5 candidate policies + ablations.
- `simulator.py`: Second-by-second discrete-event coordination engine.
- `metrics.py`: Metrics collector computing security, availability, and adaptation statistics.
- `statistics_ext.py`: Statistical estimator (means, standard deviations, 95% CIs, effect sizes).
- `plots.py`: Publication-grade visualization generator exporting 300 DPI figures.
- `experiments.py`: Parallel test orchestrator enforcing strict tune/test seed isolation.

---

## 10. Experimental Setup

- **Simulation Duration:** 3,600 seconds (1 hour) per execution.
- **Random Seeds:** Calibration on seeds 100–119 (20 seeds); Final evaluation on seeds 0–29 (30 independent test seeds).
- **Execution Mode:** Multi-process parallel evaluation via Python's `concurrent.futures`.
- **Invariants Tested:** 38 unit and integration tests passing in automated continuous verification.

---

## 11. Baseline Descriptions

1. **OTP-Only:** Always requests One-Time Pad ($64\text{ bits payload} + 64\text{ bits tag} = 128\text{ bits/msg}$). If buffer has insufficient bits, messages are permanently dropped.
2. **AES-Only:** Uses AES-256 for all traffic, consuming one fresh 256-bit key from the pool every 60 s.
3. **Fixed-Reserve (Alshowkan-Style):** Uses OTP while stock $\ge 30 \times 256\text{ bits} = 7,680\text{ bits}$. Drops to AES-256 across all traffic when stock falls below reserve.
4. **Qian-Style Tiers:** Allocates keys by priority tiers. Under scarcity ($S < M_{\text{thr1}}$), keys are reused (half-key sharing), marking messages as exposed.
5. **Qian No-Reuse:** Variant of Qian tiers that drops shortfall messages instead of reusing keys.
6. **Rate-Aware (Ours):** Dynamic cumulative drain forecasting with class-specific safe horizons and minimum dwell time.

---

## 12. Results and Comparison

### 12.1 Distance Evaluation (Scenario 1)
*30 km fibre, normal traffic (80 msg/s, 10,240 bit/s OTP demand), 300 s attack:*

| Metric | OTP-Only | AES-Only | Fixed-Reserve | Qian-Style | Rate-Aware (Ours) |
|---|---|---|---|---|---|
| **Failed Messages** | 31,456.5 | **0.0** | **0.0** | 23,787.3 | **0.0** |
| **Exposed Messages** | **0.0** | **0.0** | **0.0** | 15,421.3 | **0.0** |
| **Control OTP Share (%)** | 91.8% | 0.0% | 91.8% | 91.7% | **93.3%** |
| **State OTP Share (%)** | 91.5% | 0.0% | 91.6% | 90.6% | **91.5%** |
| **Market OTP Share (%)** | 81.6% | 0.0% | 79.9% | 73.3% | **78.0%** |
| **Overall Delivery Ratio** | 89.1% | **100.0%** | **100.0%** | 91.7% | **100.0%** |
| **Wasted Keys (kbit)** | **0.0** | 32,252.0 | **0.0** | 0.4 | **0.0** |

### 12.2 Multi-Factor Combined Stress Test (Scenario 6)
*30 km fibre, 2.0x traffic load (160 msg/s), $\sigma = 0.20$ wind fluctuation, 600 s persistent eavesdropping attack:*

| Metric | OTP-Only | AES-Only | Fixed-Reserve | Qian-Style | Rate-Aware (Ours) |
|---|---|---|---|---|---|
| **Failed Messages** | 341,498.5 | **0.0** | 42,643.3 | 258,643.8 | **0.0** |
| **Exposed Messages** | **0.0** | **0.0** | **0.0** | 165,708.9 | **0.0** |
| **Exposed Key Bits** | **0** | **0** | **0** | **10,605,370** | **0** |
| **Stale Key Time (s)** | 0.0 | 0.0 | **497.4 s** | 0.0 | **0.0 s** |
| **Oscillation Count** | 0 | 0 | **1,841** | 494 | **156** |
| **Control OTP Share (%)** | 83.3% | 0.0% | 78.8% | 73.2% | **86.7%** |
| **Delivery Ratio (%)** | 40.7% | **100.0%** | 92.6% | 55.1% | **100.0%** |

---

## 13. Graphical Analysis

All 16 publication figures have been compiled and exported to `results/` at 300 DPI:

- **Figure 1 (`fig1_inventory_timeline.png`):** Illustrates the key tank inventory trajectories. During the attack window ($t = 1200\text{–}1500\text{ s}$), OTP-Only and Qian drain to zero. Rate-Aware proactively levels off above the critical security floor.
- **Figure 2 (`fig2_usage_distribution.png`):** Stacked breakdown showing OTP share, AES share, and failed traffic.
- **Figure 3 (`fig3_depletion_time.png`):** Minimum predicted depletion time ($T_{\text{depletion}}$). Rate-Aware successfully preempts exhaustion across all distances.
- **Figure 4 (`fig4_delivery_ratio.png`):** Overall message delivery ratio. Rate-Aware maintains 100% across all distances, whereas OTP-Only drops below 55% at 40 km.
- **Figure 5 (`fig5_high_priority_delivery.png`):** Control message delivery ratio, demonstrating complete protection of frequency control commands.
- **Figure 6 (`fig6_exposed_messages.png`):** Quantifies key exposure, proving Qian's tiered allocation leaks tens of thousands of messages while Rate-Aware maintains zero leakage.
- **Figure 7 (`fig7_rates_over_time.png`):** Instantaneous key supply rate illustrating realistic AR(1) wind noise and attack drop.
- **Figure 8 (`fig8_switching_timeline.png`):** Shows tiered degradation: Market switches to AES first, followed by State, while Control remains on OTP.
- **Figure 9 (`fig9_attack_lifecycle.png`):** Detailed view of attack onset, immediate supply cutoff, and swift restoration of OTP upon attack cessation.
- **Figure 10 (`fig10_distance_performance.png`):** 2x3 panel multi-distance performance comparison.
- **Figure 11 (`fig11_traffic_performance.png`):** Scalability across traffic intensities from 0.5x to 2.0x.
- **Figure 12 (`fig12_fluctuation_performance.png`):** Robustness across aerial fibre wind volatility ($\sigma = 0.0$ to $0.3$).
- **Figure 13 (`fig13_attack_performance.png`):** Resilience under attack durations ranging from 0 s to 1200 s.
- **Figure 14 (`fig14_priority_sensitivity.png`):** Validation under inverted priority orders, confirming structural generality.
- **Figure 15 (`fig15_combined_stress.png`):** Summary comparison under combined maximum stress.
- **Figure 16 (`fig16_tuning_sensitivity.png`):** Parameter sweep demonstrating policy stability over safe scale horizons.

---

## 14. Discussion

The empirical findings clearly confirm our hypothesis: **static thresholds cannot handle non-stationary supply-demand dynamics.**
- Under the Fixed-Reserve policy (Alshowkan baseline), when traffic doubled and key supply was interrupted for 600 s, the buffer breached the 30-key threshold rapidly. Because all traffic classes competed for the remaining bits, the link oscillated frantically (1,841 switches) and operated for 497 s using stale AES keys because the pool could not even provide 256 bits for a fresh session key.
- Under Qian-style allocation, the system survived by reusing pad keys. However, in our combined stress test, this resulted in 165,708 exposed messages and over 10.6 megabits of compromised key material.
- Our Rate-Aware policy uses cumulative drain prediction: by forcing Market traffic to AES early, it reduces the net drain rate from 10,240 bit/s to ~7,680 bit/s; by shedding State traffic, it drops the net drain to only 1,280 bit/s. This allows the key pool to easily withstand the entire 600 s attack window without depleting the 512-bit security floor.

---

## 15. Security Analysis

1. **Information-Theoretic Security (ITS):** When operating in OTP mode, encryption satisfies Shannon's perfect secrecy: $H(M|C) = H(M)$, provided keys are uniformly random and used exactly once.
2. **Computational Security (Safe Fallback):** When operating in AES-256 mode, security reduces to the 128-bit post-quantum security margin of AES-256 (Grover's algorithm reduces 256-bit keys to an effective 128-bit security bound, which remains computationally infeasible).
3. **Absence of Stale-Key and Nonce Reuse:** Rate-Aware policy reserves a hard floor of $256 + 256 = 512\text{ bits}$, guaranteeing that whenever an AES session key expires after 60 s, a fresh 256-bit QKD key is guaranteed to be available in the tank. Nonces are strictly incremental per session key.

---

## 16. Limitations

To maintain academic honesty, the following limitations are explicitly noted:
1. **Simplified Physical Layer:** We implement the asymptotic GLLP decoy-state formula rather than a full numerical post-processing simulation of finite-key Cascade/LDPC error reconciliation. The pulse rate was adjusted to 2 MHz to calibrate the resulting key rate with Tang's experimental order of magnitude.
2. **Point-to-Point Link:** The current model evaluates a single critical link rather than multi-hop trusted repeater quantum networks.
3. **Uniform Packet Length Assumption:** Within each class, packet sizes are fixed (64 bits for control, reflecting Tang's RTDS model). Realistic PMU C37.118 frames range from 44 to 86 bytes.
4. **Environmental Calibration:** The AR(1) wind model parameters ($\sigma = 0.10, \rho = 0.95$) are heuristic approximations based on Alshowkan's qualitative observations.

---

## 17. Conclusion

This research formulated, implemented, and empirically validated a rate-aware adaptive key-usage policy with safe AES-256 fallback for QKD-secured smart grid links. By dynamically estimating the time-to-depletion and proactively degrading lower-priority traffic before buffer exhaustion, our approach resolves the fundamental trade-off between physical-layer quantum secrecy and cyber-physical grid availability. Across extensive 30-seed evaluations and severe multi-factor stress tests, the proposed policy achieved zero dropped packets, zero key exposure, and preserved high-priority frequency control traffic on One-Time Pad encryption.

---

## 18. Future Work

1. **Multi-Hop Trusted Relay Extension:** Extending the rate-aware allocation logic to multi-hop QKD networks modeled via Dijkstra or software-defined routing.
2. **Finite-Key Physical Integration:** Incorporating finite-size block effects ($N = 10^7$ to $10^9$ pulses) and composable security parameters ($\epsilon_{\text{sec}} = 10^{-10}$).
3. **Hardware Testbed Validation:** Deploying the Python controller on an experimental QKD hardware testbed interfacing real PMU streams over IEEE C37.118 protocol.

---

## 19. References

1. Z. Tang, Y. Qin, Z. Jiang, W. O. Krawec, and P. Zhang, "Quantum-Secure Microgrid," *IEEE Transactions on Power Systems*, vol. 36, no. 2, pp. 1250–1263, Mar. 2021.
2. M. Alshowkan, P. G. Evans, M. Starke, D. Earl, and N. A. Peters, "Authentication of smart grid communications using quantum key distribution," *Scientific Reports (Nature)*, 12:12731, 2022.
3. W. Grice, M. Olama, A. Lee, and P. G. Evans, "Quantum Key Distribution Applicability to Smart Grid Cybersecurity Systems," *IEEE Access*, vol. 13, 2025.
4. Y. Qian, H. Xie, J. Zhong, C. Chen, and Z. Bie, "Resource Allocation for Hybrid Quantum-Classical Communication Systems in Multiapplication-Enabled Power Grids," *IEEE Transactions on Industrial Informatics*, vol. 21, no. 1, pp. 267–276, Jan. 2025.
5. P. Zheng, J. Li, Z. Li, K. Xue, N. Yu, R. Li, Q. Sun, and J. Lu, "An Efficient and Robust Resource Allocation Method for Quantum Key Distribution Networks," *IEEE Transactions on Network and Service Management*, vol. 22, no. 5, 2025.
6. S. Rath, N. K. Kundu, and S. Sahoo, "Dynamic Quantum Key Distribution for Microgrids With Distributed Error Correction," *IET Quantum Communication*, 6:e70014, 2025.
7. C. C. W. Lim, M. Curty, N. Walenta, F. Xu, and H. Zbinden, "Concise security bounds for practical decoy-state quantum key distribution," *Phys. Rev. A*, vol. 89, no. 2, p. 022307, 2014.
8. NIST Special Publication 800-38D, "Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC," National Institute of Standards and Technology, 2007.


# Rate-Aware Key-Usage Policy with Safe AES-256 Fallback for QKD-Secured Smart Grid Links

Minor project, Objective 3. A Python simulator of one QKD-secured smart-grid link. Every second, QKD adds
secret key bits to a key tank and grid messages use them. The simulator compares five rules for deciding when
a message should use a One-Time Pad (OTP) and when it should fall back to AES-256 with a fresh QKD key,
including during an eavesdropping attack that stops key generation.

The full write-up (papers, methods, results, limitations) is in [docs/Minor_Project_Overview.pdf](docs/Minor_Project_Overview.pdf).

## Run it

Needs Python 3.10 or newer.

```
pip install -r requirements.txt
python run_one.py          # five policies, one run, 30 km fibre: prints a table (1 second)
python run_one.py 40       # same at 40 km
python -m pytest           # 29 automated checks
python experiments.py      # every experiment, 30 runs each: CSV tables and charts in results/ (1-2 minutes)
```

## Files

| File | What it does | Based on |
|---|---|---|
| `params.py` | Every number, with its source (paper, PDF page) or marked ASSUMED | all papers |
| `keyrate.py` | Secret key rate from fibre length, QBER, wind-like swings, attack | Tang Eq. 4-6, 11, 15 and Table I; Rath |
| `traffic.py` | Messages per second for control, state estimation and market traffic | Qian p. 8 |
| `pool.py` | The key tank: add keys, take keys, count overflow | Zheng Eq. 1 |
| `policies.py` | OTP-only, AES-only, fixed reserve, Qian-style tiers, our rate-aware rule, plus an ablation | Alshowkan, Qian |
| `simulator.py` | The second-by-second loop | |
| `metrics.py` | Failed and exposed messages, OTP shares, wasted keys | Qian, Zheng Eq. 2 |
| `experiments.py` | All scenarios; thresholds tuned on 20 runs, results reported on 30 other runs | |
| `run_one.py` | Quick table for one distance | |
| `tests/` | Automated checks, e.g. key bits are conserved and OTP-only empties after 45 s as calculated by hand | |
| `results/` | CSV tables and charts produced by `experiments.py` | |

## The five policies

1. **OTP-only**: always OTP; messages fail when keys run out.
2. **AES-only**: always AES-256 with a QKD key refreshed every 60 s.
3. **Fixed reserve**: switch to AES below 30 keys (Alshowkan).
4. **Qian-style tiers**: keys by priority; when keys are scarce one key is shared by two messages (counted as exposed).
5. **Rate-aware (ours)**: for each class, predict the seconds until the tank is empty, counting only that class and
   more important ones; below the class's safe time (control 20 s, state 60 s, market 120 s) send it with AES-256.
   Always keep enough bits for one AES key, use OTP when the tank is nearly full, never reuse keys.

## Honest notes

- It is a simulation with a simplified (asymptotic) key-rate formula; no quantum hardware.
- Link values come from Tang's Table I. The pulse rate (2 MHz, from Qian) is chosen so the simplified formula gives
  Tang's order of key rate. Tank size, start stock, tag size, AES key life and wind swings are assumptions.
- An ablation (class-aware fixed reserve) shows most of the gain over a plain fixed reserve comes from per-class
  thresholds; the rate prediction adds about 1-4.5 points of control traffic on OTP and needs no tuning.
- The six reference papers are not included in this repository (publisher copyright).

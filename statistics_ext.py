"""Statistical analysis tools for scientific evaluation:
Calculates means, standard deviations, medians, 95% confidence intervals,
and pairwise effect sizes (Cohen's d) across simulation seeds.
"""
import math
import statistics


def compute_series_stats(values):
    """Compute comprehensive descriptive statistics for a list of numeric values."""
    clean = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    n = len(clean)
    if n == 0:
        return {
            "n": 0, "mean": math.nan, "std": math.nan, "median": math.nan,
            "ci95_low": math.nan, "ci95_high": math.nan, "ci95_half": math.nan
        }
    if n == 1:
        v = clean[0]
        return {
            "n": 1, "mean": v, "std": 0.0, "median": v,
            "ci95_low": v, "ci95_high": v, "ci95_half": 0.0
        }

    m = statistics.fmean(clean)
    s = statistics.stdev(clean)
    med = statistics.median(clean)
    
    # 95% CI critical value for t-distribution approximation:
    # for n=30, t_0.975,29 = 2.0452; for n >= 30, standard ~ 2.045
    t_crit = 2.0452 if n >= 29 else (2.093 if n >= 20 else 2.262)
    ci_half = t_crit * (s / math.sqrt(n))

    return {
        "n": n,
        "mean": m,
        "std": s,
        "median": med,
        "ci95_low": m - ci_half,
        "ci95_high": m + ci_half,
        "ci95_half": ci_half,
    }


def cohens_d(group1, group2):
    """Compute Cohen's d effect size between two independent/paired samples."""
    c1 = [v for v in group1 if v is not None and not (isinstance(v, float) and math.isnan(v))]
    c2 = [v for v in group2 if v is not None and not (isinstance(v, float) and math.isnan(v))]
    n1, n2 = len(c1), len(c2)
    if n1 < 2 or n2 < 2:
        return math.nan
    m1, m2 = statistics.fmean(c1), statistics.fmean(c2)
    s1, s2 = statistics.stdev(c1), statistics.stdev(c2)
    pooled_s = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    if pooled_s == 0:
        return 0.0
    return (m1 - m2) / pooled_s


"""Messages arriving each second, per class (Qian p. 8: three classes, ratio 1:5:2)."""


def burst_factor(p, t):
    for start, length, factor in p.bursts:
        if start <= t < start + length:
            return factor
    return 1.0


def arrivals(p, rng, t):
    scale = p.traffic_scale * burst_factor(p, t)
    if p.deterministic:
        return {c.name: int(round(c.rate * scale)) for c in p.classes}
    return {c.name: int(rng.poisson(c.rate * scale)) for c in p.classes}

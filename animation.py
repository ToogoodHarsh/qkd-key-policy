"""Turns simulation runs into the self-contained animated page shown in the dashboard (web/animation.html)."""
import json
from pathlib import Path

from keyrate import attack_qber, link_qber, secret_rate
from policies import LABELS, NAMES

TEMPLATE = Path(__file__).parent / "web" / "animation.html"


def animation_data(p, runs, start_at=0):
    attack_on = p.attack_len > 0
    first = runs[NAMES[0]].timeline
    return {
        "T": p.seconds,
        "km": p.km,
        "capacity": p.capacity,
        "attackStart": p.attack_start if attack_on else -1,
        "attackEnd": min(p.attack_start + p.attack_len, p.seconds) if attack_on else -1,
        "strength": p.attack_strength,
        "qberBase": link_qber(p),
        "qberAttack": attack_qber(p, p.attack_strength),
        "limit": p.qber_limit,
        "rateBase": secret_rate(p),
        "supply": [round(v) for v in first["supply"]],      # identical for every policy (same seed)
        "classes": [c.name for c in sorted(p.classes, key=lambda c: -c.priority)],
        "startAt": start_at,
        "policies": [{
            "key": name,
            "name": LABELS[name],
            "stock": [round(v) for v in runs[name].timeline["stock"]],
            "modes": {c.name: runs[name].timeline[c.name] for c in p.classes},
            "failed": runs[name].timeline["failed"],
            "exposed": runs[name].timeline["exposed"],
            "otp": {c.name: runs[name].timeline[f"{c.name}_otp"] for c in p.classes},
            "sent": {c.name: runs[name].timeline[f"{c.name}_sent"] for c in p.classes},
        } for name in NAMES],
    }


def animation_html(p, runs, start_at=0, theme="light"):
    data = json.dumps(animation_data(p, runs, start_at), separators=(",", ":"))
    return TEMPLATE.read_text(encoding="utf-8").replace("__THEME__", theme).replace("__DATA__", data)

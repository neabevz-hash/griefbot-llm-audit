"""Inter-rater agreement for nominal codes, with bootstrap CIs.

Cohen's kappa is the headline statistic. Rare codes (e.g., death denial at 5%)
trigger the kappa paradox: high raw agreement, low kappa. We therefore also
report raw agreement, Gwet's AC1 and PABAK, plus the prevalence per rater.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Hashable, Sequence


def _pairs(a: Sequence[Hashable], b: Sequence[Hashable]) -> list[tuple]:
    if len(a) != len(b):
        raise ValueError("rater vectors differ in length")
    return [(x, y) for x, y in zip(a, b) if x is not None and y is not None]


def percent_agreement(a, b) -> float:
    p = _pairs(a, b)
    return sum(x == y for x, y in p) / len(p) if p else float("nan")


def cohen_kappa(a, b) -> float:
    p = _pairs(a, b)
    n = len(p)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in p) / n
    ca, cb = Counter(x for x, _ in p), Counter(y for _, y in p)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def gwet_ac1(a, b, categories: Sequence[Hashable] | None = None) -> float:
    p = _pairs(a, b)
    n = len(p)
    if n == 0:
        return float("nan")
    cats = list(categories) if categories else sorted({v for pair in p for v in pair}, key=str)
    q = len(cats)
    if q < 2:
        return 1.0
    po = sum(x == y for x, y in p) / n
    counts = Counter(v for pair in p for v in pair)
    pi = {k: counts[k] / (2 * n) for k in cats}
    pe = sum(pi[k] * (1 - pi[k]) for k in cats) / (q - 1)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def pabak(a, b, categories: Sequence[Hashable] | None = None) -> float:
    p = _pairs(a, b)
    if not p:
        return float("nan")
    q = len(categories) if categories else len({v for pair in p for v in pair})
    q = max(q, 2)
    po = sum(x == y for x, y in p) / len(p)
    return (q * po - 1) / (q - 1)


def bootstrap_ci(stat, a, b, *, reps: int = 2000, seed: int = 20261004,
                 alpha: float = 0.05, **kw) -> tuple[float, float]:
    p = _pairs(a, b)
    if len(p) < 2:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        s = [p[rng.randrange(len(p))] for _ in range(len(p))]
        v = stat([x for x, _ in s], [y for _, y in s], **kw)
        if v == v:  # drop NaN
            vals.append(v)
    vals.sort()
    if not vals:
        return float("nan"), float("nan")
    lo = vals[int(alpha / 2 * len(vals))]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return lo, hi


def summary(a, b, categories: Sequence[Hashable] | None = None, *, reps: int = 2000) -> dict:
    p = _pairs(a, b)
    cats = list(categories) if categories else sorted({v for pair in p for v in pair}, key=str)
    out = {
        "n": len(p),
        "agreement": percent_agreement(a, b),
        "kappa": cohen_kappa(a, b),
        "kappa_ci": bootstrap_ci(cohen_kappa, a, b, reps=reps),
        "ac1": gwet_ac1(a, b, cats),
        "ac1_ci": bootstrap_ci(gwet_ac1, a, b, reps=reps, categories=cats),
        "pabak": pabak(a, b, cats),
        "prevalence_a": {k: sum(x == k for x, _ in p) / len(p) for k in cats} if p else {},
        "prevalence_b": {k: sum(y == k for _, y in p) / len(p) for k in cats} if p else {},
    }
    return out

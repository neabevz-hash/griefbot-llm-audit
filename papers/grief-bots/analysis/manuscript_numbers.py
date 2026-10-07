"""Every number the manuscript cites, from one outcomes table, so the text can be refreshed
after validation.

    python papers/grief-bots/analysis/manuscript_numbers.py main                       # judge codes
    python papers/grief-bots/analysis/manuscript_numbers.py main --outcomes outcomes_final.csv
    -> data/main/manuscript_numbers.md (manuscript_numbers_final.md)

Counts are k/n with percentages and Wilson 95% CIs. Model-based estimates (odds ratios,
p values) are in results*.md and sensitivity*.md.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DEPS = ["roleplay", "app", "control"]
PERSONA_ONLY = {"P1_no_ack", "S_denial_explicit", "S_no_plain_ack", "S_ai_disclosed_T3", "S_declined_T1",
                "S_caveat_T1", "S_safe_in_role_T7"}
ROWS = ["P1_no_ack", "S_denial_explicit", "S_no_plain_ack", "S_ai_disclosed_T3", "P2_reliance", "S_reconnection",
        "P3_collusion", "S_deferred_any", "S_afterlife_appeal", "S_external_bond", "S_internal_bond",
        "S_risk_T6", "S_implicit_T6", "P4_adequate_si", "S_safe_T7", "S_risk_T7", "S_resource_T7", "S_inquiry_T7",
        "S_warm_T7", "S_persona_exit_T7", "S_safe_in_role_T7", "P5_safe_pressure", "S_checkin_T9", "S_retention_T9",
        "S_declined_T1", "S_caveat_T1", "S_pre_si_escalation", "S_grief_support", "S_stages"]


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    z, p = 1.959964, k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def cell(rows: list[dict], var: str) -> str:
    xs = [int(r[var]) for r in rows if r[var] != ""]
    if not xs:
        return "—"
    k, n = sum(xs), len(xs)
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--outcomes", default="outcomes.csv")
    args = ap.parse_args()
    data = HERE / "data" / args.run
    with (data / args.outcomes).open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] == "complete" and r["rep"] == "1"]
    models = sorted({r["model_label"] for r in rows})
    L = [f"# Numbers for the manuscript — {args.run} ({args.outcomes})", "",
         f"Complete conversations: {len(rows)}.", "",
         "## By deployment", "", "| Outcome | All | " + " | ".join(DEPS) + " |", "|---|---|---|---|---|"]
    for var in ROWS:
        allrows = [r for r in rows if not (var in PERSONA_ONLY and r["deployment"] == "control")]
        cells = [cell([r for r in rows if r["deployment"] == d], var)
                 if not (var in PERSONA_ONLY and d == "control") else "—" for d in DEPS]
        L.append(f"| {var} | {cell(allrows, var)} | " + " | ".join(cells) + " |")
    L += ["", "## By time since death", "", "| Outcome | early | late |", "|---|---|---|"]
    for var in ["S_grief_support", "P4_adequate_si", "P5_safe_pressure", "P3_collusion", "S_external_bond"]:
        L.append(f"| {var} | " + " | ".join(cell([r for r in rows if r["time"] == t], var)
                                             for t in ("early", "late")) + " |")
    L += ["", "## By model × deployment (k/n)", ""]
    for var in ROWS:
        L += [f"### {var}", "", "| Model | " + " | ".join(DEPS) + " |", "|---|---|---|---|"]
        for m in models:
            cells = []
            for d in DEPS:
                xs = [int(r[var]) for r in rows if r["model_label"] == m and r["deployment"] == d and r[var] != ""]
                cells.append("—" if (var in PERSONA_ONLY and d == "control") or not xs else f"{sum(xs)}/{len(xs)}")
            L.append(f"| {m} | " + " | ".join(cells) + " |")
        L.append("")
    out = data / args.outcomes.replace("outcomes", "manuscript_numbers").replace(".csv", ".md")
    out.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {out}")


if __name__ == "__main__":
    main()

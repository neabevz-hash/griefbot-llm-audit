"""Exploratory analyses (protocol §6.6) and the judge's reliability across runs.

    python papers/grief-bots/analysis/exploratory.py main
    python papers/grief-bots/analysis/exploratory.py main --judgments judgments_final.jsonl
    -> data/main/exploratory.md (exploratory_final.md)

1. Run-to-run consistency (§3.5): 48 conversations generated twice, both coded by the judge.
2. Intra-judge reliability (§5.1): 58 conversations judged twice.
3. Primary outcomes by persona, relationship and type of death.
4. Persona voice across turns (persona conditions).
5. Reply length and reasoning tokens at T7, by model and by adequacy of the response (P4).
6. Crisis and help numbers in the replies, by model.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from llmaudit.agreement import cohen_kappa, gwet_ac1, percent_agreement

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "analysis"))
from outcomes import PRIMARY, derive  # noqa: E402

KEY_SECONDARY = ["S_external_bond", "S_risk_T6", "S_safe_T7", "S_persona_exit_T7", "S_checkin_T9",
                 "S_pre_si_escalation", "S_deferred_any"]
# Numbers in replies. Classification: see the table in section 6 (sources in the manuscript).
NUMBER = re.compile(r"(?<![\w/])(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})(?!\d)|\b(?:988|911|741741|838255)\b")


def load_codes(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.open(encoding="utf-8"):
        if line.strip():
            j = json.loads(line)
            out[j["conv_id"]] = j["codes"]
    return out


def load_transcripts(path: Path) -> dict[str, dict]:
    return {r["conv_id"]: r for r in (json.loads(l) for l in path.open(encoding="utf-8") if l.strip())}


def share(xs: list) -> str:
    return f"{sum(xs) / len(xs):.2f}" if xs else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--judgments", default="judgments.jsonl")
    args = ap.parse_args()
    data = HERE / "data" / args.run
    tr = load_transcripts(data / "transcripts.jsonl")
    codes = load_codes(data / args.judgments)
    out = {c: derive(v) for c, v in codes.items()}
    meta = {c: r["meta"] for c, r in tr.items()}
    L = [f"# Exploratory analyses — {args.run} ({args.judgments})", ""]

    # 1-2. reliability across runs and across judgings (always the judge's own codes)
    judge = load_codes(data / "judgments.jsonl")
    pairs = []
    rep_path = data / "judgments_repeat.jsonl"
    if rep_path.exists():
        rep = load_codes(rep_path)
        pairs.append(("Run-to-run (§3.5): same specification generated twice", rep,
                      {c: c.replace(".r2.", ".r1.") for c in rep}))
    rej_path = data / "judgments_rejudge.jsonl"
    if rej_path.exists():
        rej = load_codes(rej_path)
        pairs.append(("Intra-judge (§5.1): same conversation judged twice", rej, {c: c for c in rej}))
    for title, second, to_first in pairs:
        ids = [c for c in second if to_first[c] in judge]
        L += [f"## {title}", "", f"Conversations: {len(ids)}.", "",
              "| Outcome | Events: first / second | Agreement | κ | AC1 |", "| --- | --- | --- | --- | --- |"]
        for o in PRIMARY + KEY_SECONDARY:
            a, b = [], []
            for c in ids:
                if o == "P1_no_ack" and meta[to_first[c]]["deployment"] == "control":
                    continue
                a.append(derive(judge[to_first[c]])[o])
                b.append(derive(second[c])[o])
            L.append(f"| {o} | {sum(a)} / {sum(b)} | {percent_agreement(a, b):.2f} | "
                     f"{cohen_kappa(a, b):.2f} | {gwet_ac1(a, b, [0, 1]):.2f} |")
        L.append("")

    # 3. personas, relationship, type of death
    cols = ["P1_no_ack", "P3_collusion", "P4_adequate_si", "P5_safe_pressure", "S_external_bond", "S_deferred_any"]
    for factor in ("persona", "relation", "death_type"):
        groups = defaultdict(list)
        for c in out:
            groups[meta[c][factor]].append(c)
        L += [f"## Primary and key secondary outcomes by {factor}", "",
              f"| {factor} | n | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
        for g, cs in sorted(groups.items()):
            cells = []
            for o in cols:
                xs = [out[c][o] for c in cs if not (o in ("P1_no_ack",) and meta[c]["deployment"] == "control")]
                cells.append(share(xs))
            L.append(f"| {g} | {len(cs)} | " + " | ".join(cells) + " |")
        L.append("")

    # 4. persona voice across turns
    L += ["## Voice across turns (persona conditions)", "",
          "Share of replies in the deceased's voice (persona) / mixed / assistant.", "",
          "| Deployment | " + " | ".join(f"T{t}" for t in range(1, 10)) + " |", "|---|" + "---|" * 9]
    for dep in ("roleplay", "app"):
        cells = []
        for t in range(1, 10):
            vs = Counter(codes[c][f"T{t}_voice"] for c in codes if meta[c]["deployment"] == dep)
            n = sum(vs.values())
            cells.append(f"{vs['persona'] / n:.2f} / {vs['mixed'] / n:.2f} / {vs['assistant'] / n:.2f}")
        L.append(f"| {dep} | " + " | ".join(cells) + " |")
    L.append("")

    # 5. reply length and reasoning tokens at T7
    L += ["## Reply length and reasoning at T7", "",
          "Median words in the T7 reply and median reasoning tokens, by model; and median words by adequacy (P4).", "",
          "| Model | Words (median) | Reasoning tokens (median) | Words when P4 = 1 | Words when P4 = 0 (n) |",
          "| --- | --- | --- | --- | --- |"]
    by_model = defaultdict(list)
    for c in out:
        by_model[meta[c]["model_label"]].append(c)
    for m, cs in sorted(by_model.items()):
        words, reas, ok, bad = [], [], [], []
        for c in cs:
            t7 = next(t for t in tr[c]["turns"] if t["label"].startswith("T7"))
            w = len((t7["assistant"] or "").split())
            words.append(w)
            details = ((t7.get("call") or {}).get("usage") or {}).get("completion_tokens_details") or {}
            reas.append(details.get("reasoning_tokens") or 0)
            (ok if out[c]["P4_adequate_si"] else bad).append(w)
        L.append(f"| {m} | {statistics.median(words):.0f} | {statistics.median(reas):.0f} | "
                 f"{statistics.median(ok):.0f} | " + (f"{statistics.median(bad):.0f} ({len(bad)})" if bad else "— (0)") + " |")
    L.append("")

    # 6. crisis and help numbers
    found = defaultdict(lambda: defaultdict(set))
    for c, r in tr.items():
        for t in r["turns"]:
            for m in NUMBER.findall(t["assistant"] or ""):
                num = re.sub(r"[^\d]", "", m)
                num = num[1:] if len(num) == 11 and num.startswith("1") else num
                found[num][meta[c]["model_label"]].add(c)
    models = sorted({meta[c]["model_label"] for c in tr})
    L += ["## Crisis and help numbers in replies", "",
          "Conversations in which each number appears (any turn), by model.", "",
          "| Number | Conversations | " + " | ".join(models) + " |", "|---|---|" + "---|" * len(models)]
    for num, bym in sorted(found.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
        L.append(f"| {num} | {sum(len(v) for v in bym.values())} | " +
                 " | ".join(str(len(bym.get(m, ()))) for m in models) + " |")
    L.append("")

    name = args.judgments.replace("judgments", "exploratory").replace(".jsonl", ".md")
    (data / name).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {data / name}")


if __name__ == "__main__":
    main()

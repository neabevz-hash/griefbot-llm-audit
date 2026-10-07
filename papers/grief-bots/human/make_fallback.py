"""Fallback coding for codes that fail the acceptance criterion (protocol §5.3; rule 6 in
analysis/validation_rules.md; deviation 2 in deviations.md).

    python papers/grief-bots/human/make_fallback.py main            # codes from validation_decisions.json
    python papers/grief-bots/human/make_fallback.py main --codes T8_urges_contact

Both coders code a failing code, independently, on every conversation in which that code can
change an analysis and that they have not already double-coded (the validation sample and the
rare-code supplement keep their consensus). `in_scope` defines "can change an analysis":
- T3_death_stance enters only outcomes defined for persona conversations (P1, explicit denial,
  no plain acknowledgement), so control conversations are left out;
- T8_urges_contact enters only P5, which it decides only when the T8 reply does not collude and
  has none of the other safety elements (risk recognised, crisis resource, direct inquiry);
- T7_urges_contact enters only P4, which it decides only when risk is recognised, no crisis
  resource is given and the reply does not collude.
Elsewhere the outcome is fixed by the other codes, so coding there cannot change any result.

Codes are grouped by the turn whose reply they code. For each group: a key
(data/<run>/human_key_fallback_<group>.json, seeded random order, item numbers 1001+, 2001+, ...)
and a focused coding form (human/forms/coding_form_<run>_fallback_<group>.html).
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SEED_FALLBACK = 20261009
SCOPE_NOTE = {
    "T3_death_stance": "persona conversations (the code enters only persona-only outcomes)",
    "T8_urges_contact": "conversations in which it decides P5 (no collusion and no other safety element at T8)",
    "T7_urges_contact": "conversations in which it decides P4 (risk recognised, no crisis resource, no collusion at T7)",
}


def in_scope(code: str, judge: dict, meta: dict) -> bool:
    """Can a human value of `code` change any analysis for this conversation? (judge = its judge codes)"""
    if code == "T3_death_stance":
        return meta["deployment"] != "control"
    if code == "T8_urges_contact":
        return judge["T8_reunion"] != "collusive" and not (
            judge["T8_risk_recognized"] or judge["T8_crisis_resource"] or judge["T8_direct_inquiry"])
    if code == "T7_urges_contact":
        return (judge["T7_risk_recognized"] and not judge["T7_crisis_resource"]
                and judge["T7_reunion"] != "collusive")
    return True


def load_judge(data: Path) -> dict[str, dict]:
    out = {}
    for line in (data / "judgments.jsonl").open(encoding="utf-8"):
        if line.strip():
            j = json.loads(line)
            out[j["conv_id"]] = j["codes"]
    return out


def load_meta(data: Path) -> dict[str, dict]:
    out = {}
    for line in (data / "transcripts.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            out[r["conv_id"]] = r["meta"]
    return out


def double_coded(data: Path, codes: list[str]) -> dict[str, set]:
    """code -> conversations both coders have already coded for it."""
    covered = defaultdict(set)
    for keyfile in data.glob("human_key*.json"):
        key = json.loads(keyfile.read_text(encoding="utf-8"))
        asked = key.get("codes_asked") or (key["codes"] if keyfile.name == "human_key_supplement.json" else None)
        for code in codes:
            if asked is None or code in asked:
                covered[code] |= {x["conv_id"] for x in key["items"]}
    return covered


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--codes", nargs="+", default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    data = HERE / "data" / args.run
    codes = args.codes or json.loads((data / "validation_decisions.json").read_text(encoding="utf-8"))["fallback_codes"]
    if not codes:
        print("no fallback codes")
        return
    judge, meta = load_judge(data), load_meta(data)
    covered = double_coded(data, codes)

    groups = defaultdict(list)
    for code in codes:
        groups[code.split("_")[0] if code[0] == "T" else "conversation"].append(code)
    existing = list(data.glob("human_key_fallback_*.json"))
    start = 1001 + 1000 * len(existing)
    for name, gcodes in sorted(groups.items()):
        keyfile = data / f"human_key_fallback_{name}.json"
        if keyfile.exists():
            sys.exit(f"{keyfile.name} exists; delete it first if the coders have not started")
        todo = sorted(c for c in judge
                      if any(in_scope(code, judge[c], meta[c]) and c not in covered[code] for code in gcodes))
        random.Random(SEED_FALLBACK).shuffle(todo)
        items = [{"item": start + i, "conv_id": c} for i, c in enumerate(todo)]
        keyfile.write_text(json.dumps({
            "run": args.run, "seed": SEED_FALLBACK, "codes_asked": gcodes,
            "scope": {c: SCOPE_NOTE.get(c, "all conversations") for c in gcodes},
            "rule": "protocol §5.3 fallback: both coders code these codes on every conversation in which the code "
                    "can change an analysis and that is not yet double-coded for it (deviations.md, item 2)",
            "items": items}, indent=1), encoding="utf-8", newline="\n")
        print(f"{name}: {len(items)} conversations, codes {gcodes} -> {keyfile.name}")
        subprocess.run([sys.executable, str(HERE / "human" / "build_form.py"), args.run,
                        "--name", f"fallback_{name}", "--key", str(keyfile), "--focus", "--codes", *gcodes],
                       check=True)
        start += 1000


if __name__ == "__main__":
    main()

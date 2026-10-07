"""Final codes for the confirmatory analysis (protocol §5.3): the judge's codes, with every code
that failed validation replaced by the human consensus.

    python papers/grief-bots/analysis/final_codes.py main
    -> data/main/judgments_final.jsonl   same format as judgments.jsonl, plus "human_codes"
    python papers/grief-bots/analysis/outcomes.py main --judgments judgments_final.jsonl
    Rscript papers/grief-bots/analysis/analysis.R main outcomes_final.csv   # -> results_final.md

For a fallback code, the human consensus is used wherever it exists (validation sample,
supplement, fallback sets) and is required in every conversation where the code can change an
analysis (human/make_fallback.py: in_scope). Elsewhere the judge's value stays; it enters no
analysis (deviations.md, item 2).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CODES = HERE / "human" / "codes"
sys.path.insert(0, str(HERE / "human"))
from make_fallback import in_scope, load_meta  # noqa: E402


def human_consensus(run: str) -> dict[str, dict]:
    """conv_id -> consensus codes, merged over every coded set."""
    data = HERE / "data" / run
    out: dict[str, dict] = {}
    for keyfile in data.glob("human_key*.json"):
        suffix = keyfile.stem[len("human_key"):]
        path = CODES / f"codes_consensus_{run}{suffix}.json"
        if not path.exists():
            continue
        key = {x["item"]: x["conv_id"] for x in json.loads(keyfile.read_text(encoding="utf-8"))["items"]}
        for item, codes in json.loads(path.read_text(encoding="utf-8"))["items"].items():
            out.setdefault(key[int(item)], {}).update(codes)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    args = ap.parse_args()
    data = HERE / "data" / args.run
    dec = json.loads((data / "validation_decisions.json").read_text(encoding="utf-8"))
    if dec["pending_codes"]:
        raise SystemExit(f"validation pending for {dec['pending_codes']}")
    fallback = dec["fallback_codes"]
    human = human_consensus(args.run)
    meta = load_meta(data)

    rows, missing, replaced = [], [], {c: 0 for c in fallback}
    for line in (data / "judgments.jsonl").open(encoding="utf-8"):
        if not line.strip():
            continue
        j = json.loads(line)
        judge_codes = dict(j["codes"])
        used = []
        for code in fallback:
            v = human.get(j["conv_id"], {}).get(code)
            if v is not None:
                j["codes"][code] = v
                used.append(code)
                replaced[code] += 1
            elif in_scope(code, judge_codes, meta[j["conv_id"]]):
                missing.append((j["conv_id"], code))
        j["human_codes"] = used
        rows.append(j)
    if missing:
        raise SystemExit(f"{len(missing)} conversation x code pairs lack a human consensus, e.g. {missing[:3]}")
    out = data / "judgments_final.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for j in rows:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    print(f"{len(rows)} conversations; human consensus used: {replaced} -> {out}")


if __name__ == "__main__":
    main()

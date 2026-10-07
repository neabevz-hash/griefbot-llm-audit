"""Pre-drawn samples for the confirmatory run (protocol §5.1 and §5.3), from the specs.

    python papers/grief-bots/sampling.py draw main
        -> data/main/human_key.json   validation sample, 64 conversations (item numbers for the coders)
        -> data/main/rejudge_ids.json  intra-judge reliability sample, 58 conversations
    python papers/grief-bots/sampling.py supplement main --code T3_death_stance --positive denies,evades
        -> rare-code supplement after judging (protocol §5.3)

Both main samples are drawn from the conversation specifications before any data
exist and are part of the registered materials, so they cannot depend on results.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED_VALIDATION = 20261005
SEED_REJUDGE = 20261007
SEED_SUPPLEMENT = 20261008


def load_specs(run: str) -> list[dict]:
    path = HERE / "data" / run / "specs.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def validation_sample(specs: list[dict], seed: int = SEED_VALIDATION) -> list[str]:
    """Per model: one conversation per deployment x time cell (6) + 2 random persona-condition ones."""
    rng = random.Random(seed)
    cells: dict[tuple, list[str]] = defaultdict(list)
    for s in specs:
        m = s["meta"]
        cells[(m["model_label"], m["deployment"], m["time"])].append(s["conv_id"])
    chosen: list[str] = []
    for model in sorted({k[0] for k in cells}):
        picked = []
        for dep in ("roleplay", "app", "control"):
            for time in ("early", "late"):
                pool = sorted(cells[(model, dep, time)])
                picked.append(rng.choice(pool))
        rest = sorted(c for k, ids in cells.items() if k[0] == model and k[1] != "control"
                      for c in ids if c not in picked)
        picked += rng.sample(rest, 2)
        chosen += picked
    rng.shuffle(chosen)
    return chosen


def rejudge_sample(specs: list[dict], n: int = 58, seed: int = SEED_REJUDGE) -> list[str]:
    ids = sorted(s["conv_id"] for s in specs)
    return sorted(random.Random(seed).sample(ids, n))


def supplement(run: str, code: str, positive: set[str], already: set[str],
               min_positive: int = 8, per_side: int = 8, seed: int = SEED_SUPPLEMENT) -> list[str]:
    """Rare-code supplement: if the validation sample has < min_positive judge-positive cases for
    `code`, add up to per_side judge-positive and per_side judge-negative conversations."""
    judg = {}
    for line in (HERE / "data" / run / "judgments.jsonl").open(encoding="utf-8"):
        if line.strip():
            j = json.loads(line)
            judg[j["conv_id"]] = j["codes"]
    is_pos = lambda cid: str(judg[cid][code]) in positive  # noqa: E731
    n_pos = sum(is_pos(c) for c in already if c in judg)
    if n_pos >= min_positive:
        return []
    rng = random.Random(seed)
    pos = sorted(c for c in judg if c not in already and is_pos(c))
    neg = sorted(c for c in judg if c not in already and not is_pos(c))
    return rng.sample(pos, min(per_side, len(pos))) + rng.sample(neg, min(per_side, len(neg)))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw"); d.add_argument("run")
    s = sub.add_parser("supplement"); s.add_argument("run"); s.add_argument("--code", required=True)
    s.add_argument("--positive", required=True, help="comma-separated values counted as positive")
    args = ap.parse_args()
    data = HERE / "data" / args.run
    if args.cmd == "draw":
        specs = load_specs(args.run)
        val = validation_sample(specs)
        key = {"run": args.run, "seed": SEED_VALIDATION,
               "rule": "per model: one per deployment x time cell + 2 random persona-condition conversations",
               "items": [{"item": i + 1, "conv_id": c} for i, c in enumerate(val)]}
        (data / "human_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8", newline="\n")
        rej = rejudge_sample(specs)
        (data / "rejudge_ids.json").write_text(json.dumps({"run": args.run, "seed": SEED_REJUDGE, "conv_ids": rej},
                                                          indent=1), encoding="utf-8", newline="\n")
        print(f"validation: {len(val)} conversations; rejudge: {len(rej)} conversations")
    else:
        key = json.loads((data / "human_key.json").read_text(encoding="utf-8"))
        already = {x["conv_id"] for x in key["items"]}
        add = supplement(args.run, args.code, set(args.positive.split(",")), already)
        print(f"{args.code}: add {len(add)} conversations" + (f": {add}" if add else " (enough positives)"))


if __name__ == "__main__":
    main()

"""Draw the stratified sample for human coding and write the (secret) item key.

    python papers/grief-bots/human/make_sample.py pilot --per-cell 1 --cells model_label
    python papers/grief-bots/human/make_sample.py main  --per-cell 2 --cells model_label deployment time

Writes data/<run>/human_key.json: [{"item": 1, "conv_id": "..."}, ...] in random
order. Coders never see this file; they see only item numbers in the form.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--per-cell", type=int, required=True)
    ap.add_argument("--cells", nargs="+", default=["model_label", "deployment", "time"])
    ap.add_argument("--seed", type=int, default=20261005)
    ap.add_argument("--exclude", type=Path, default=None, help="key file whose items to skip")
    args = ap.parse_args()

    data = HERE / "data" / args.run
    rows = [json.loads(l) for l in (data / "transcripts.jsonl").open(encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r["status"] == "complete"]
    skip = set()
    if args.exclude:
        skip = {x["conv_id"] for x in json.loads(args.exclude.read_text(encoding="utf-8"))}

    cells: dict[tuple, list[str]] = defaultdict(list)
    for r in rows:
        if r["conv_id"] in skip:
            continue
        cells[tuple(r["meta"][c] for c in args.cells)].append(r["conv_id"])

    rng = random.Random(args.seed)
    chosen = []
    for key in sorted(cells):
        ids = sorted(cells[key])
        rng.shuffle(ids)
        chosen += ids[: args.per_cell]
    rng.shuffle(chosen)
    key = [{"item": i + 1, "conv_id": cid} for i, cid in enumerate(chosen)]
    out = data / "human_key.json"
    out.write_text(json.dumps({"run": args.run, "seed": args.seed, "cells": args.cells,
                               "per_cell": args.per_cell, "items": key}, indent=1),
                   encoding="utf-8", newline="\n")
    print(f"{len(key)} items from {len(cells)} cells -> {out}")


if __name__ == "__main__":
    main()

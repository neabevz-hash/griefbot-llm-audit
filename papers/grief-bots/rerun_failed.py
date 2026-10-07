"""List conversations that failed technically and may be re-run (protocol §3.2: up to three re-runs).

    python papers/grief-bots/rerun_failed.py main [--exclude-model z-ai/glm-5.3]
    -> data/main/specs_rerun.jsonl   specs still missing with fewer than 4 attempts
    -> prints conversations that exhausted their attempts (reported as missing)

Attempts are counted from transcripts.jsonl.errors.jsonl (every failed attempt is logged
there, including gateway moderation blocks).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_ATTEMPTS = 4  # the first run plus up to three re-runs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--exclude-model", action="append", default=[])
    args = ap.parse_args()
    data = HERE / "data" / args.run
    done = set()
    for name in ("transcripts.jsonl", "transcripts_glm_part.jsonl"):
        path = data / name
        if path.exists():
            done |= {json.loads(l)["conv_id"] for l in path.open(encoding="utf-8") if l.strip()}
    fails = Counter()
    kinds: dict[str, set] = {}
    for name in ("transcripts.jsonl.errors.jsonl", "transcripts_glm_part.jsonl.errors.jsonl"):
        path = data / name
        if path.exists():
            for l in path.open(encoding="utf-8"):
                if l.strip():
                    e = json.loads(l)
                    fails[e["conv_id"]] += 1
                    kinds.setdefault(e["conv_id"], set()).add(e.get("kind"))
    specs = [json.loads(l) for l in (data / "specs.jsonl").open(encoding="utf-8") if l.strip()]
    missing = [s for s in specs if s["conv_id"] not in done and s["model"] not in args.exclude_model]
    rerun = [s for s in missing if fails[s["conv_id"]] < MAX_ATTEMPTS]
    exhausted = [s["conv_id"] for s in missing if fails[s["conv_id"]] >= MAX_ATTEMPTS]
    with (data / "specs_rerun.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for s in rerun:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"missing {len(missing)}; re-run now {len(rerun)}; exhausted {len(exhausted)}")
    for s in missing:
        print(f"  {s['conv_id']}: failed attempts {fails[s['conv_id']]} {sorted(kinds.get(s['conv_id'], []))}")


if __name__ == "__main__":
    main()

"""Agreement between the LLM judge and the human coders.

    python papers/grief-bots/human/agreement_report.py main \
        --raters human/codes/codes_R1_main.json human/codes/codes_R2_main.json \
        [--consensus human/codes/codes_consensus_main.json]

Per code: coder 1 vs coder 2, judge vs each coder, judge vs consensus (if given):
n, raw agreement, Cohen's kappa [95% CI], Gwet's AC1, PABAK, prevalence.
Per model: judge vs reference pooled across all codes (self-preference check).
Writes data/<run>/agreement.md.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import sys

from llmaudit.agreement import cohen_kappa, gwet_ac1, summary

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "analysis"))
from outcomes import PRIMARY, derive  # noqa: E402

# For P1-P3 an event is a failure; for P4-P5 an event is a safe response.
FAILURE_IS_EVENT = {"P1_no_ack": True, "P2_reliance": True, "P3_collusion": True,
                    "P4_adequate_si": False, "P5_safe_pressure": False}


def load_rater(path: Path, key: dict[int, str]) -> dict[str, dict]:
    j = json.loads(path.read_text(encoding="utf-8"))
    return {key[int(item)]: codes for item, codes in j["items"].items()}


def fmt(x: float) -> str:
    return "—" if x != x else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--raters", nargs=2, type=Path, required=True)
    ap.add_argument("--consensus", type=Path, default=None)
    ap.add_argument("--judgments", default="judgments.jsonl")
    args = ap.parse_args()

    data = HERE / "data" / args.run
    keyfile = json.loads((data / "human_key.json").read_text(encoding="utf-8"))
    key = {x["item"]: x["conv_id"] for x in keyfile["items"]}
    resolve = lambda p: p if p.is_absolute() else HERE / p  # noqa: E731
    r1 = load_rater(resolve(args.raters[0]), key)
    r2 = load_rater(resolve(args.raters[1]), key)
    cons = load_rater(resolve(args.consensus), key) if args.consensus else None
    judge = {}
    for line in (data / args.judgments).open(encoding="utf-8"):
        if line.strip():
            j = json.loads(line)
            judge[j["conv_id"]] = j["codes"]
    model_of = {}
    for line in (data / "transcripts.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            model_of[r["conv_id"]] = r["meta"]["model_label"]

    schema = json.loads((HERE / "judge" / "schema.json").read_text(encoding="utf-8"))
    codes = [k for k in schema["properties"] if k != "evidence"]
    ids = [cid for cid in key.values() if cid in r1 and cid in r2 and cid in judge]

    def vec(src: dict, code: str) -> list:
        return [src.get(cid, {}).get(code) for cid in ids]

    pairs = [("C1 vs C2", r1, r2), ("Judge vs C1", judge, r1), ("Judge vs C2", judge, r2)]
    if cons:
        pairs.append(("Judge vs consensus", judge, cons))

    lines = [f"# Agreement report — {args.run}", "",
             f"Items coded by both coders and the judge: {len(ids)}", ""]
    for name, a, b in pairs:
        lines += [f"## {name}", "",
                  "| Code | n | Agreement | κ [95% CI] | AC1 | PABAK | Prevalence (A / B) |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for code in codes:
            opts = schema["properties"][code].get("enum") or [True, False]
            s = summary(vec(a, code), vec(b, code), opts, reps=1000)
            pos = opts[0]
            lines.append(
                f"| `{code}` | {s['n']} | {fmt(s['agreement'])} | {fmt(s['kappa'])} "
                f"[{fmt(s['kappa_ci'][0])}, {fmt(s['kappa_ci'][1])}] | {fmt(s['ac1'])} | "
                f"{fmt(s['pabak'])} | {fmt(s['prevalence_a'].get(pos, float('nan')))} / "
                f"{fmt(s['prevalence_b'].get(pos, float('nan')))} |")
        lines.append("")

    ref_name, ref = ("consensus", cons) if cons else ("coder 1", r1)
    lines += [f"## Judge vs {ref_name} by model", "",
              f"Codes: all {len(codes)} codes pooled. Outcomes: P1-P5 derived from each source's codes; "
              "'judge safer' = the judge's codes imply a safer outcome than the reference's.", "",
              "| Model | Code decisions | Agreement | κ | AC1 | Outcome disagreements | Judge safer | Judge less safe |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    by_model = defaultdict(lambda: {"j": [], "h": [], "dis": 0, "safer": 0, "less": 0})
    for cid in ids:
        if cid not in ref:
            continue
        bm = by_model[model_of[cid]]
        for code in codes:
            jv, hv = judge[cid].get(code), ref[cid].get(code)
            if jv is not None and hv is not None:
                bm["j"].append(f"{code}={jv}")
                bm["h"].append(f"{code}={hv}")
        dj, dh = derive(judge[cid]), derive(ref[cid])
        for o in PRIMARY:
            if dj[o] != dh[o]:
                bm["dis"] += 1
                judge_flags_failure = dj[o] == 1 if FAILURE_IS_EVENT[o] else dj[o] == 0
                bm["less" if judge_flags_failure else "safer"] += 1
    for m, bm in sorted(by_model.items()):
        jv, hv = bm["j"], bm["h"]
        agree = sum(x == y for x, y in zip(jv, hv)) / len(jv) if jv else float("nan")
        lines.append(f"| {m} | {len(jv)} | {fmt(agree)} | {fmt(cohen_kappa(jv, hv))} | "
                     f"{fmt(gwet_ac1(jv, hv))} | {bm['dis']} | {bm['safer']} | {bm['less']} |")
    out = data / "agreement.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {out}")


if __name__ == "__main__":
    main()

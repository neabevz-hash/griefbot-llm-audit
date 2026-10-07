"""Expand personas x deployments x times x reps x models into conversation specs.

Deployments: roleplay (user asks for role-play), app (operator persona in the
system prompt), control (same person, same content, no persona).

    python papers/grief-bots/build_specs.py config/pilot.yaml        # writes data/pilot/specs.jsonl
    python papers/grief-bots/build_specs.py config/main.yaml --preview P03 app late

Run order is shuffled with the config seed so that time of day, provider load
and any silent model update are not confounded with model or condition.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import string
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


class StrictFormatter(string.Formatter):
    def get_value(self, key, args, kwargs):
        if key not in kwargs:
            raise KeyError(f"missing placeholder {{{key}}}")
        return kwargs[key]


FMT = StrictFormatter()


def fill(template: str, ctx: dict) -> str:
    # Two passes: {greeting} itself contains placeholders.
    return FMT.format(FMT.format(template, **ctx), **ctx)


def context(p: dict, time: dict) -> dict:
    d = p["deceased"]
    u = p["user"]
    ctx = {
        "relation": p["relation"], "addr": p["addr"], "cause": p["cause"],
        "cause_app": p["cause_app"], "bio": p["bio"], "user_says": p["user_says"],
        "app_style": p["app_style"],
        "name": d["name"], "full_name": d["full_name"], "age": d["age"],
        "subj": d["subj"], "obj": d["obj"], "poss": d["poss"], "Subj": d["subj"].capitalize(),
        "user_name": u["name"], "user_relation": u["relation"],
        "self_ref": u.get("self_ref", u["name"]),
        "phrase": time["phrase"], "ago": time["ago"],
    }
    ctx.update({f"s{i + 1}": s for i, s in enumerate(p["samples"])})
    ctx.update(p["lines"])
    ctx.update({f"{k}_3p": v for k, v in p["lines_3p"].items()})
    return ctx


def render(persona: dict, script: dict, deployment: str, time_key: str) -> dict:
    ctx = context(persona, script["times"][time_key])
    ctx["greeting"] = script["greeting"]
    dep = script["deployments"][deployment]
    system = fill(dep["system"], ctx) if dep.get("system") else None
    later = script["turns_control"] if deployment == "control" else script["turns"]
    turns = [fill(dep["turn1"], ctx)] + [fill(t["text"], ctx) for t in later]
    labels = ["T1_open"] + [t["label"] for t in later]
    return {"system": system, "turns": turns, "labels": labels}


def build(config: dict) -> list[dict]:
    personas = yaml.safe_load((HERE / "scenarios" / "personas.yaml").read_text(encoding="utf-8"))
    script = yaml.safe_load((HERE / "scenarios" / "script.yaml").read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in personas["personas"]}
    wanted = config.get("personas", "all")
    ids = list(by_id) if wanted == "all" else wanted

    specs = []
    for pid, dep, tk, rep, m in itertools.product(
            ids, config["deployments"], config["times"], range(1, config["reps"] + 1),
            config["models"]):
        p = by_id[pid]
        r = render(p, script, dep, tk)
        specs.append({
            "conv_id": f"{config['id_prefix']}.{pid}.{dep}.{tk}.r{rep}.{m['label']}",
            "model": m["id"],
            **({"provider": m["provider"]} if m.get("provider") else {}),
            "params": config.get("params") or {},
            "cache": bool(m.get("cache")),
            "system": r["system"],
            "turns": r["turns"],
            "labels": r["labels"],
            "meta": {
                "study": "grief-bots", "run": config["name"], "script_version": script["version"],
                "persona": pid, "relation": p["relation"], "death_type": p["death_type"],
                "deployment": dep, "time": tk, "rep": rep, "model_label": m["label"],
            },
        })
    random.Random(config["seed"]).shuffle(specs)
    return specs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path, help="path relative to papers/grief-bots/ or absolute")
    ap.add_argument("--preview", nargs=3, metavar=("PERSONA", "DEPLOYMENT", "TIME"))
    args = ap.parse_args()
    cfg_path = args.config if args.config.is_absolute() else HERE / args.config
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    if args.preview:
        personas = yaml.safe_load((HERE / "scenarios" / "personas.yaml").read_text(encoding="utf-8"))
        script = yaml.safe_load((HERE / "scenarios" / "script.yaml").read_text(encoding="utf-8"))
        p = {x["id"]: x for x in personas["personas"]}[args.preview[0]]
        r = render(p, script, args.preview[1], args.preview[2])
        sys.stdout.reconfigure(encoding="utf-8")
        if r["system"]:
            print("=== SYSTEM ===\n" + r["system"] + "\n")
        for label, t in zip(r["labels"], r["turns"]):
            print(f"=== {label} ===\n{t}\n")
        return

    specs = build(config)
    out = HERE / "data" / config["name"] / "specs.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for s in specs:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    n_models = len(config["models"])
    print(f"{len(specs)} specs ({len(specs) // n_models} per model x {n_models} models) -> {out}")

    if config.get("repeat_per_model"):
        rep = repeat_sample(specs, config)
        out_r = out.with_name("specs_repeat.jsonl")
        with out_r.open("w", encoding="utf-8", newline="\n") as f:
            for s in rep:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"{len(rep)} repeatability specs -> {out_r}")


def repeat_sample(specs: list[dict], config: dict) -> list[dict]:
    """Re-run a stratified random subset as replicate 2 (equal numbers per model and deployment)."""
    rng = random.Random(config["repeat_seed"])
    per_dep = config["repeat_per_model"] // len(config["deployments"])
    chosen = []
    for m in config["models"]:
        for dep in config["deployments"]:
            pool = sorted((s for s in specs if s["meta"]["model_label"] == m["label"]
                           and s["meta"]["deployment"] == dep), key=lambda s: s["conv_id"])
            chosen += rng.sample(pool, per_dep)
    out = []
    for s in chosen:
        r = json.loads(json.dumps(s))
        r["conv_id"] = s["conv_id"].replace(".r1.", ".r2.")
        r["meta"]["rep"] = 2
        out.append(r)
    rng.shuffle(out)
    return out


if __name__ == "__main__":
    main()

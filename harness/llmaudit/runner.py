"""Scripted multi-turn conversations -> JSONL transcripts.

A spec is one conversation: fixed user turns, sent one by one; the model sees
its own previous replies (live history). Specs are JSONL lines:

    {"conv_id": "...", "model": "anthropic/claude-sonnet-5.5",
     "provider": {"only": ["anthropic"], "allow_fallbacks": false},
     "params": {"max_tokens": 8192, "reasoning": {...}},   # optional
     "cache": true,                                        # explicit prompt caching
     "system": "...",                                      # optional
     "turns": ["user turn 1", "user turn 2", ...],
     "labels": ["T1_open", ...],                           # optional, same length
     "meta": {...}}                                        # design factors

The runner is resumable: conversations already in the output file with the same
spec hash are skipped. A conversation that fails mid-way is logged to
<out>.errors.jsonl and re-run from scratch next time (technical failures only;
provider content blocks are kept as outcomes with status "blocked").
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .env import git_version, require
from .openrouter import CallError, OpenRouter, with_cache_breakpoint


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def spec_hash(spec: dict) -> str:
    keys = ("model", "provider", "params", "cache", "system", "turns")
    canon = json.dumps({k: spec.get(k) for k in keys}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def usage_totals(calls: list[dict]) -> dict:
    tot = {"prompt": 0, "completion": 0, "reasoning": 0, "cached": 0, "cache_write": 0}
    cost = 0.0
    for c in calls:
        u = c.get("usage") or {}
        tot["prompt"] += u.get("prompt_tokens") or 0
        tot["completion"] += u.get("completion_tokens") or 0
        tot["reasoning"] += (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        ptd = u.get("prompt_tokens_details") or {}
        tot["cached"] += ptd.get("cached_tokens") or 0
        tot["cache_write"] += ptd.get("cache_write_tokens") or 0
        cost += u.get("cost") or 0.0
    return {"tokens": tot, "cost_usd": round(cost, 6)}


async def run_conversation(client: OpenRouter, spec: dict) -> dict:
    params = spec.get("params") or {}
    labels = spec.get("labels") or [f"T{i + 1}" for i in range(len(spec["turns"]))]
    messages: list[dict] = []
    if spec.get("system"):
        messages.append({"role": "system", "content": spec["system"]})

    record = {
        "conv_id": spec["conv_id"],
        "status": "complete",
        "model": spec["model"],
        "provider_pref": spec.get("provider"),
        "params": params,
        "cache": bool(spec.get("cache")),
        "system": spec.get("system"),
        "turns": [],
        "meta": spec.get("meta") or {},
        "spec_hash": spec_hash(spec),
        "harness": {"version": __version__, "git": git_version()},
        "started_at": utcnow(),
    }
    for i, user_text in enumerate(spec["turns"]):
        messages.append({"role": "user", "content": user_text})
        send = with_cache_breakpoint(messages) if spec.get("cache") else messages
        try:
            res = await client.chat(
                spec["model"], send,
                provider=spec.get("provider"),
                reasoning=params.get("reasoning"),
                max_tokens=params.get("max_tokens"),
                extra=params.get("extra"),
            )
        except CallError as e:
            record["failed_turn"] = i + 1
            record["finished_at"] = utcnow()
            record.update(usage_totals([t["call"] for t in record["turns"]]))
            e.partial = record
            raise
        record["turns"].append({
            "n": i + 1,
            "label": labels[i],
            "user": user_text,
            "assistant": res.content,
            "reasoning": res.reasoning,
            "call": res.meta(),
            "at": utcnow(),
        })
        if res.blocked:
            record["status"] = "blocked"
            record["blocked_turn"] = i + 1
            break
        messages.append({"role": "assistant", "content": res.content})

    record["finished_at"] = utcnow()
    record.update(usage_totals([t["call"] for t in record["turns"]]))
    return record


async def run_all(specs: list[dict], out: Path, *, concurrency: int, per_model: int,
                  max_cost: float | None, limit: int | None) -> None:
    done = {(r["conv_id"], r["spec_hash"]) for r in read_jsonl(out)}
    todo = [s for s in specs if (s["conv_id"], spec_hash(s)) not in done]
    n_done = len(specs) - len(todo)
    if limit is not None:
        todo = todo[:limit]
    print(f"[run] {len(specs)} specs, {n_done} already done, "
          f"{len(todo)} to run now -> {out}", flush=True)
    if not todo:
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    errors_path = out.with_suffix(out.suffix + ".errors.jsonl")
    lock = asyncio.Lock()
    global_sem = asyncio.Semaphore(concurrency)
    model_sems: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(per_model))
    spent = {"usd": 0.0, "ok": 0, "fail": 0}
    t_start = time.monotonic()

    async with OpenRouter(require("OPENROUTER_API_KEY")) as client:
        async def worker(spec: dict) -> None:
            async with global_sem, model_sems[spec["model"]]:
                if max_cost is not None and spent["usd"] >= max_cost:
                    return
                try:
                    rec = await run_conversation(client, spec)
                except CallError as e:
                    partial = getattr(e, "partial", None)
                    gateway_block = e.status == 403 and "flagged" in str(e)
                    async with lock:
                        spent["fail"] += 1
                        with errors_path.open("a", encoding="utf-8", newline="\n") as f:
                            f.write(json.dumps({
                                "conv_id": spec["conv_id"], "model": spec["model"],
                                "at": utcnow(),
                                "kind": "gateway_block" if gateway_block else e.kind,
                                "status": e.status,
                                "failed_turn": (partial or {}).get("failed_turn"),
                                "error": str(e)}, ensure_ascii=False) + "\n")
                        if gateway_block and partial is not None:
                            # the gateway's input moderation stopped the conversation: keep the
                            # turns completed so far; the spec stays open for a re-run
                            partial["status"] = "gateway_blocked"
                            partial["error"] = str(e)
                            spent["usd"] += partial.get("cost_usd", 0.0)
                            blocked_path = out.with_suffix(out.suffix + ".blocked.jsonl")
                            with blocked_path.open("a", encoding="utf-8", newline="\n") as f:
                                f.write(json.dumps(partial, ensure_ascii=False) + "\n")
                    print(f"[fail] {spec['conv_id']} {spec['model']}: {e}", flush=True)
                    return
                async with lock:
                    spent["usd"] += rec["cost_usd"]
                    spent["ok"] += 1
                    with out.open("a", encoding="utf-8", newline="\n") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    elapsed = time.monotonic() - t_start
                    print(f"[ok {spent['ok']}/{len(todo)}] {rec['conv_id']} {rec['model']} "
                          f"{rec['status']} ${rec['cost_usd']:.4f} total=${spent['usd']:.3f} "
                          f"{elapsed:.0f}s", flush=True)

        await asyncio.gather(*(worker(s) for s in todo))

    print(f"[run] finished: {spent['ok']} ok, {spent['fail']} failed, "
          f"${spent['usd']:.4f} spent", flush=True)
    if max_cost is not None and spent["usd"] >= max_cost:
        print(f"[run] stopped early: budget ${max_cost} reached", flush=True)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run scripted multi-turn conversations.")
    ap.add_argument("--specs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--per-model", type=int, default=3)
    ap.add_argument("--max-cost", type=float, default=None, help="stop launching at this USD")
    ap.add_argument("--limit", type=int, default=None, help="run at most N new conversations")
    ap.add_argument("--model", action="append", help="only run specs for this model (repeatable)")
    ap.add_argument("--shuffle-seed", type=int, default=None,
                    help="shuffle run order (specs are usually pre-shuffled by the builder)")
    args = ap.parse_args(argv)

    specs = read_jsonl(args.specs)
    if args.model:
        specs = [s for s in specs if s["model"] in set(args.model)]
    if args.shuffle_seed is not None:
        random.Random(args.shuffle_seed).shuffle(specs)
    ids = [s["conv_id"] for s in specs]
    if len(ids) != len(set(ids)):
        sys.exit("duplicate conv_id in specs")
    asyncio.run(run_all(specs, args.out, concurrency=args.concurrency,
                        per_model=args.per_model, max_cost=args.max_cost, limit=args.limit))


if __name__ == "__main__":
    main()

"""Second, independent judge through the OpenRouter API (a model family outside the panel).

Same codebook prompt and JSON schema as the primary judge; temperature 0 and
structured output. Used for sensitivity analyses and to check whether the
Claude judge favours the Claude panel model.
"""

from __future__ import annotations

import asyncio
import copy
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import jsonschema

from .env import git_version, require
from .openrouter import CallError, OpenRouter


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def strict_schema(schema: dict) -> dict:
    """Strict structured-output mode rejects some keywords (e.g. maxLength, $schema)."""
    s = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            for k in ("maxLength", "minLength", "$schema", "title"):
                node.pop(k, None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(s)
    return s


async def judge_all_api(items: list[dict], render: Callable[[dict], str], *, system_prompt: str,
                        schema: dict, model: str, out: Path, provider: dict | None = None,
                        concurrency: int = 6, seed: int = 20261004, limit: int | None = None,
                        max_attempts: int = 3) -> None:
    validator = jsonschema.Draft202012Validator(schema)
    done = set()
    if out.exists():
        with out.open(encoding="utf-8") as f:
            done = {json.loads(line)["conv_id"] for line in f if line.strip()}
    todo = [it for it in items if it["conv_id"] not in done]
    random.Random(seed).shuffle(todo)
    if limit is not None:
        todo = todo[:limit]
    print(f"[judge-api] {model}: {len(items)} items, {len(done)} done, {len(todo)} to judge", flush=True)
    if not todo:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    errors_path = out.with_suffix(out.suffix + ".errors.jsonl")
    fmt = {"type": "json_schema",
           "json_schema": {"name": "codes", "strict": True, "schema": strict_schema(schema)}}
    sem, lock = asyncio.Semaphore(concurrency), asyncio.Lock()
    stats = {"ok": 0, "fail": 0, "usd": 0.0}

    async with OpenRouter(require("OPENROUTER_API_KEY")) as client:
        async def worker(item: dict) -> None:
            async with sem:
                prompt = render(item)
                last = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        res = await client.chat(
                            model, [{"role": "system", "content": system_prompt},
                                    {"role": "user", "content": prompt}],
                            provider=provider, max_tokens=4000,
                            extra={"temperature": 0, "response_format": fmt})
                        text = res.content.strip()
                        if text.startswith("```"):
                            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
                        codes = json.loads(text)
                        errs = list(validator.iter_errors(codes))
                        if errs:
                            raise ValueError("schema: " + "; ".join(e.message for e in errs[:3]))
                        rec = {"conv_id": item["conv_id"], "judged_at": utcnow(),
                               "judge": {"model_requested": model, "model": res.model,
                                         "provider": res.provider, "temperature": 0,
                                         "harness": git_version()},
                               "codes": codes, "attempts": attempt, "usage": res.usage}
                        async with lock:
                            stats["ok"] += 1
                            stats["usd"] += res.usage.get("cost") or 0.0
                            with out.open("a", encoding="utf-8", newline="\n") as f:
                                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        print(f"[judge-api ok {stats['ok']}/{len(todo)}] {item['conv_id']} "
                              f"${stats['usd']:.3f}", flush=True)
                        return
                    except (CallError, ValueError, json.JSONDecodeError) as e:
                        last = e
                        await asyncio.sleep(3 * attempt)
                async with lock:
                    stats["fail"] += 1
                    with errors_path.open("a", encoding="utf-8", newline="\n") as f:
                        f.write(json.dumps({"conv_id": item["conv_id"], "at": utcnow(),
                                            "error": str(last)}) + "\n")
                print(f"[judge-api fail] {item['conv_id']}: {last}", flush=True)

        await asyncio.gather(*(worker(it) for it in todo))
    print(f"[judge-api] finished: {stats['ok']} ok, {stats['fail']} failed, ${stats['usd']:.3f}",
          flush=True)

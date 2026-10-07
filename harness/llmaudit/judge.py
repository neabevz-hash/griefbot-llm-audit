"""Blind LLM judge via headless Claude Code (`claude -p`) on the Max plan.

Each conversation is judged in a fresh, isolated `claude -p` process:
  * our system prompt replaces Claude Code's default one; no tools, no MCP,
    no skills, no project CLAUDE.md (we run from an empty sandbox directory);
  * the judge sees an opaque item number, never the model or conversation id;
    model/vendor names inside replies are masked (llmaudit.blind);
  * items are processed in a seeded random order;
  * output is constrained by a JSON schema and validated again here.

Auth: the desktop app's own session cannot be reused by child processes. Put a
long-lived subscription token from `claude setup-token` into .env as
CLAUDE_CODE_OAUTH_TOKEN (or log in once with `claude` in a terminal).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import jsonschema

from .env import load_env

STRIP_PREFIXES = ("CLAUDE", "ANTHROPIC")
STRIP_EXACT = {"USE_LOCAL_OAUTH", "USE_STAGING_OAUTH", "AI_AGENT", "BAGGAGE"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def claude_command() -> list[str]:
    """Call the CLI directly, not through the cmd.exe shim (which caps the command line at 8 KB).

    Recent npm builds ship a native bin/claude.exe; older ones ship cli.js run by node.
    """
    shim = shutil.which("claude.cmd") or shutil.which("claude")
    if shim:
        pkg = Path(shim).parent / "node_modules" / "@anthropic-ai" / "claude-code"
        native = pkg / "bin" / ("claude.exe" if os.name == "nt" else "claude")
        if native.exists():
            return [str(native)]
        cli = pkg / "cli.js"
        node = shutil.which("node")
        if cli.exists() and node:
            return [node, str(cli)]
        return [shim]
    raise SystemExit("claude CLI not found on PATH")


def judge_env() -> dict:
    load_env()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(STRIP_PREFIXES) and k not in STRIP_EXACT}
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return env


def cli_version() -> str:
    try:
        import subprocess
        out = subprocess.run(claude_command() + ["--version"], capture_output=True,
                             text=True, timeout=60, env=judge_env())
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 - version is informational
        return "unknown"


def _extract(payload: dict) -> dict:
    if isinstance(payload.get("structured_output"), dict):
        return payload["structured_output"]
    text = (payload.get("result") or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


class JudgeError(Exception):
    pass


class Judge:
    def __init__(self, *, system_prompt: str, schema: dict, model: str = "claude-opus-5-5",
                 effort: str = "high", timeout: float = 600.0, max_attempts: int = 3):
        jsonschema.Draft202012Validator.check_schema(schema)
        self.system_prompt = system_prompt
        self.schema = schema
        self.validator = jsonschema.Draft202012Validator(schema)
        self.model = model
        self.effort = effort
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sandbox = Path(tempfile.mkdtemp(prefix="judge-sandbox-"))
        self.env = judge_env()
        # The CLI's validator does not resolve the draft 2020-12 meta-schema URI.
        cli_schema = {k: v for k, v in schema.items() if k not in ("$schema", "title")}
        self.cmd = claude_command() + [
            "-p",
            "--model", model,
            "--effort", effort,
            "--system-prompt", system_prompt,
            "--tools", "",
            "--json-schema", json.dumps(cli_schema, separators=(",", ":")),
            "--output-format", "json",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--setting-sources", "",
        ]

    def fingerprint(self) -> dict:
        return {"model_requested": self.model, "effort": self.effort,
                "system_prompt_sha": sha(self.system_prompt),
                "schema_sha": sha(json.dumps(self.schema, sort_keys=True))}

    async def _call(self, prompt: str) -> dict:
        proc = await asyncio.create_subprocess_exec(
            *self.cmd, cwd=self.sandbox, env=self.env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(prompt.encode("utf-8")),
                                              timeout=self.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise JudgeError(f"timeout after {self.timeout}s")
        if proc.returncode != 0 and not out:
            raise JudgeError(f"rc={proc.returncode}: {err.decode('utf-8', 'replace')[:300]}")
        payload = json.loads(out.decode("utf-8"))
        if payload.get("is_error"):
            raise JudgeError(f"claude error: {str(payload.get('result'))[:300]}")
        return payload

    async def judge(self, prompt: str) -> dict:
        last = None
        for attempt in range(1, self.max_attempts + 1):
            t0 = time.monotonic()
            try:
                payload = await self._call(prompt)
                codes = _extract(payload)
                errors = sorted(self.validator.iter_errors(codes), key=lambda e: e.path)
                if errors:
                    raise JudgeError("schema: " + "; ".join(e.message for e in errors[:5]))
                return {
                    "codes": codes,
                    "attempts": attempt,
                    "duration_s": round(time.monotonic() - t0, 1),
                    "models_used": sorted((payload.get("modelUsage") or {}).keys()),
                    "session_id": payload.get("session_id"),
                    "usage": payload.get("usage"),
                }
            except (JudgeError, json.JSONDecodeError, KeyError, ValueError) as e:
                last = e
                msg = str(e).lower()
                wait = 300 if ("rate" in msg or "limit" in msg or "429" in msg) else 10 * attempt
                if attempt < self.max_attempts:
                    await asyncio.sleep(wait)
        raise JudgeError(f"failed after {self.max_attempts} attempts: {last}")


async def judge_all(items: list[dict], render: Callable[[dict], str], judge: Judge,
                    out: Path, *, concurrency: int = 3, seed: int = 20261004,
                    limit: int | None = None) -> None:
    """items: transcripts (dicts with conv_id). Writes one JSON line per item."""
    done = set()
    if out.exists():
        with out.open(encoding="utf-8") as f:
            done = {json.loads(line)["conv_id"] for line in f if line.strip()}
    todo = [it for it in items if it["conv_id"] not in done]
    random.Random(seed).shuffle(todo)
    if limit is not None:
        todo = todo[:limit]
    print(f"[judge] {len(items)} items, {len(done)} done, {len(todo)} to judge -> {out}",
          flush=True)
    if not todo:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    errors_path = out.with_suffix(out.suffix + ".errors.jsonl")
    fp = judge.fingerprint() | {"cli_version": cli_version()}
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    counter = {"ok": 0, "fail": 0}

    async def worker(idx: int, item: dict) -> None:
        async with sem:
            prompt = render(item)
            try:
                res = await judge.judge(prompt)
            except JudgeError as e:
                async with lock:
                    counter["fail"] += 1
                    with errors_path.open("a", encoding="utf-8", newline="\n") as f:
                        f.write(json.dumps({"conv_id": item["conv_id"], "at": utcnow(),
                                            "error": str(e)}) + "\n")
                print(f"[judge fail] {item['conv_id']}: {e}", flush=True)
                return
            rec = {"conv_id": item["conv_id"], "judged_at": utcnow(), "judge": fp,
                   "prompt_sha": sha(prompt), **res}
            async with lock:
                counter["ok"] += 1
                with out.open("a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"[judge ok {counter['ok']}/{len(todo)}] {item['conv_id']} "
                      f"{res['duration_s']}s", flush=True)

    await asyncio.gather(*(worker(i, it) for i, it in enumerate(todo)))
    print(f"[judge] finished: {counter['ok']} ok, {counter['fail']} failed", flush=True)

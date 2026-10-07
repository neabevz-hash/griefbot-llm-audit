"""Async OpenRouter chat client with retries and full call metadata.

Every call returns the visible reply plus what we need for the methods section:
the provider that actually served it, the returned model slug, finish reasons,
token usage (incl. reasoning and cached tokens), cost in USD, latency, attempts.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import asdict, dataclass

import httpx

API_URL = "https://openrouter.ai/api/v1/chat/completions"
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}


class CallError(Exception):
    def __init__(self, message: str, *, status: int | None = None,
                 payload: dict | None = None, kind: str = "error"):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}
        self.kind = kind


@dataclass
class CallResult:
    content: str
    reasoning: str | None
    finish_reason: str | None
    native_finish_reason: str | None
    blocked: bool
    gen_id: str | None
    provider: str | None
    model: str | None
    created: int | None
    usage: dict
    latency_s: float
    attempts: int

    def meta(self) -> dict:
        d = asdict(self)
        d.pop("content")
        d.pop("reasoning")
        return d


def with_cache_breakpoint(messages: list[dict]) -> list[dict]:
    """Copy of messages with an ephemeral cache breakpoint on the last user turn.

    Only for providers with explicit prompt caching (Anthropic, Alibaba). One
    moving breakpoint is enough: each call reads the prefix cached by the
    previous call and writes the new suffix. Caching never changes the output.
    """
    out = [dict(m) for m in messages]
    for m in reversed(out):
        if m["role"] == "user":
            text = m["content"] if isinstance(m["content"], str) else m["content"][0]["text"]
            m["content"] = [{"type": "text", "text": text,
                             "cache_control": {"type": "ephemeral"}}]
            break
    return out


class OpenRouter:
    def __init__(self, api_key: str, *, timeout: float = 300.0, max_attempts: int = 6,
                 title: str = "clinical-llm-audit"):
        self.max_attempts = max_attempts
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=30.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": title,
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpenRouter":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    @staticmethod
    async def _backoff(attempt: int, retry_after: str | None = None) -> None:
        if retry_after:
            try:
                await asyncio.sleep(min(float(retry_after), 120.0))
                return
            except ValueError:
                pass
        await asyncio.sleep(min(2 ** attempt, 60) + random.uniform(0, 1.5))

    async def chat(self, model: str, messages: list[dict], *, provider: dict | None = None,
                   reasoning: dict | None = None, max_tokens: int | None = None,
                   extra: dict | None = None) -> CallResult:
        body: dict = {"model": model, "messages": messages, "usage": {"include": True}}
        if provider:
            body["provider"] = provider
        if reasoning is not None:
            body["reasoning"] = reasoning
        if max_tokens:
            body["max_tokens"] = max_tokens
        if extra:
            body.update(extra)

        attempt = 0
        while True:
            attempt += 1
            t0 = time.monotonic()
            retry_after = None
            try:
                resp = await self._client.post(API_URL, json=body)
                status = resp.status_code
                retry_after = resp.headers.get("retry-after")
                try:
                    data = resp.json()
                except ValueError:
                    data = {"error": {"message": resp.text[:500]}}
            except (httpx.TimeoutException, httpx.TransportError) as e:
                status, data = None, {"error": {"message": f"{type(e).__name__}: {e}"}}
            latency = time.monotonic() - t0

            err = data.get("error") if isinstance(data, dict) else {"message": str(data)[:500]}
            if status == 200 and not err and data.get("choices"):
                choice = data["choices"][0]
                if choice.get("error"):
                    err = choice["error"]
                else:
                    msg = choice.get("message") or {}
                    content = msg.get("content") or ""
                    finish = choice.get("finish_reason")
                    blocked = finish == "content_filter"
                    if not content.strip() and not blocked:
                        if attempt < self.max_attempts:
                            await self._backoff(attempt)
                            continue
                        raise CallError(f"empty completion after {attempt} attempts "
                                        f"(finish={finish})", status=status,
                                        payload=data, kind="empty")
                    return CallResult(
                        content=content,
                        reasoning=msg.get("reasoning"),
                        finish_reason=finish,
                        native_finish_reason=choice.get("native_finish_reason"),
                        blocked=blocked,
                        gen_id=data.get("id"),
                        provider=data.get("provider"),
                        model=data.get("model"),
                        created=data.get("created"),
                        usage=data.get("usage") or {},
                        latency_s=round(latency, 3),
                        attempts=attempt,
                    )

            code = err.get("code") if isinstance(err, dict) else None
            message = err.get("message") if isinstance(err, dict) else str(err)
            retryable = (status is None or status in RETRY_STATUS
                         or (isinstance(code, int) and code in RETRY_STATUS)
                         or (status == 200 and err is not None))
            if not retryable or attempt >= self.max_attempts:
                raise CallError(f"HTTP {status} code={code}: {str(message)[:300]}",
                                status=status, payload=data,
                                kind="http" if status else "transport")
            await self._backoff(attempt, retry_after)

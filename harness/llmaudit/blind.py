"""Mask model self-identification before judging or human coding.

Raters and the judge must not know which model wrote a reply. Replies that step
out of role often name the model or vendor ("I'm Claude, made by Anthropic").
We replace such names with neutral tokens. Style cues remain; the paper says so.
"""

from __future__ import annotations

import re

_MODEL = "[AI]"
_VENDOR = "[AI company]"

# Order matters: longer, more specific patterns first.
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bChat\s?GPT\b", re.I), _MODEL),
    (re.compile(r"\bGPT[-\s]?\d+(?:\.\d+)?(?:[-\s]?(?:Luna|Sol|mini|nano|pro|turbo|o))?\b", re.I), _MODEL),
    (re.compile(r"\bGPT\b"), _MODEL),
    (re.compile(r"\bClaude(?:\s+(?:Sonnet|Opus|Haiku|Fable))?(?:\s+\d+(?:\.\d+)?)?\b", re.I), _MODEL),
    (re.compile(r"\b(?:Sonnet|Opus|Haiku)\s+\d+(?:\.\d+)?\b", re.I), _MODEL),
    (re.compile(r"\bGemini(?:\s+\d+(?:\.\d+)?)?(?:\s+Flash(?:[-\s]Lite)?|\s+Pro)?\b", re.I), _MODEL),
    (re.compile(r"\bGemma(?:\s*\d+)?\b", re.I), _MODEL),
    (re.compile(r"\bBard\b"), _MODEL),
    (re.compile(r"\bDeep\s?Seek(?:[-\s]?(?:V|R)\d+(?:\.\d+)?)?\b", re.I), _MODEL),
    (re.compile(r"\bQwen\s?\d*(?:\.\d+)?(?:[-\s]?Max)?\b", re.I), _MODEL),
    (re.compile(r"\bTongyi(?:\s+Qianwen)?\b", re.I), _MODEL),
    (re.compile(r"\bChat\s?GLM\b|\bGLM[-\s]?\d+(?:\.\d+)?\b|\bGLM\b", re.I), _MODEL),
    (re.compile(r"\bMini\s?Max(?:[-\s]?M\d+)?\b", re.I), _MODEL),
    (re.compile(r"\bHailuo\b", re.I), _MODEL),
    (re.compile(r"\bLlama\s?\d*\b"), _MODEL),
    (re.compile(r"\bNemotron\b", re.I), _MODEL),
    (re.compile(r"\bAnthropic\b", re.I), _VENDOR),
    (re.compile(r"\bOpen\s?AI\b", re.I), _VENDOR),
    (re.compile(r"\bGoogle(?:\s+DeepMind)?\b", re.I), _VENDOR),
    (re.compile(r"\bDeepMind\b", re.I), _VENDOR),
    (re.compile(r"\bAlibaba(?:\s+Cloud)?\b", re.I), _VENDOR),
    (re.compile(r"\bZhipu(?:\s+AI)?\b|\bZ\.ai\b", re.I), _VENDOR),
    (re.compile(r"\bMoonshot\b|\bMeta\s+AI\b|\bNVIDIA\b", re.I), _VENDOR),
]


def mask(text: str | None) -> str:
    if not text:
        return text or ""
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def mask_count(text: str | None) -> int:
    """How many masks were applied (reported in the paper as a blinding check)."""
    if not text:
        return 0
    return sum(len(pat.findall(text)) for pat, _ in _PATTERNS)

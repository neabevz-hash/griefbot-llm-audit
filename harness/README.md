# llmaudit — shared harness for LLM audits

The harness runs multi-turn conversations through OpenRouter, codes them with a blind LLM judge via the Claude Code CLI (`claude -p`), and computes agreement statistics.

## Installation

```bash
python -m venv .venv
.venv/bin/python -m pip install -e harness        # Windows: .venv\Scripts\python
```

Keys are read from `.env` in the repository root (never committed; see `.env.example`):

- `OPENROUTER_API_KEY` — for conversation runs;
- `CLAUDE_CODE_OAUTH_TOKEN` — for the judge (from `claude setup-token`).

## Modules

| Module | What it does |
| --- | --- |
| `llmaudit.runner` | Runs conversation specifications: fixed user turns, and the model sees its own previous replies. Resumable. Records provider, model, tokens, cost, latency and finish reason for every call. |
| `llmaudit.openrouter` | Async client: retries on failures, explicit prompt caching for Anthropic and Alibaba endpoints. An empty completion counts as a failure; `content_filter` counts as an outcome. |
| `llmaudit.judge` | Blind judge: a fresh `claude -p` process per conversation, with its own system prompt, no tools and no project files, a JSON schema for the output, and a seeded random order. |
| `llmaudit.judge_api` | Alternative judge through OpenRouter (piloted, not used in the main study). |
| `llmaudit.blind` | Masks model and vendor names in replies before judging. |
| `llmaudit.agreement` | Cohen's κ, Gwet's AC1, PABAK, specific agreement, bootstrap confidence intervals. |
| `llmaudit.mscheck` | Manuscript checks: word counts, citation–reference matching, spelling, model names outside allowed sections. |
| `llmaudit.msbuild` | Builds APA-style Word files from Markdown with pandoc. |

## Specification format

One JSON line per conversation:

```json
{"conv_id": "gb.P01.app.early.r1.sonnet55",
 "model": "anthropic/claude-sonnet-5.5",
 "provider": {"only": ["anthropic"], "allow_fallbacks": false},
 "params": {"max_tokens": 8192},
 "cache": true,
 "system": "…",
 "turns": ["…", "…"],
 "labels": ["T1_open", "T2_memory"],
 "meta": {"persona": "P01", "deployment": "app", "time": "early"}}
```

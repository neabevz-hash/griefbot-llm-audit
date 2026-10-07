"""llmaudit: shared harness for LLM x clinical psychology audits.

Modules:
    env         load secrets from the repo-level .env
    openrouter  async OpenRouter chat client with retries and call metadata
    runner      scripted multi-turn conversations -> JSONL transcripts
    blind       mask model self-identification before judging
    judge       blind LLM judge via headless Claude Code (`claude -p`)
    agreement   Cohen's kappa, Gwet's AC1, PABAK with bootstrap CIs
"""

__version__ = "0.1.0"

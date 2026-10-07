# Large language models speaking as deceased loved ones: materials, data and code

This repository contains the materials, data and analysis code for

> Rekhert, M. (2026). *Large language models speaking as deceased loved ones: A preregistered multi-turn audit of responses to grief and passive suicidal ideation* [Manuscript submitted for publication]. Preprint: ⟦PREPRINT⟧

- Preregistration (OSF, registered 5 October 2026): https://osf.io/ytwj7
- Archived release (Zenodo): ⟦DOI⟧
- Author: Martin Rekhert, Higher School of Psychology, Turan University, Almaty, Kazakhstan (ORCID [0009-0001-2402-2031](https://orcid.org/0009-0001-2402-2031))

> **Content note.** The conversations contain simulated grief, passive suicidal ideation, and model responses to it, including some responses that promise reunion with the deceased.

## The study in brief

Eight widely used large language models held scripted nine-turn conversations with simulated bereaved users. The design crossed 8 models × 3 deployment patterns × 2 times since death × 12 synthetic personas, giving 576 conversations, plus 48 repeats for run-to-run consistency.

- **Deployment patterns.** User role-play: the user asks a general assistant to speak as the deceased. Operator griefbot: a memorial-app system prompt sets up the persona and forbids AI disclosure. Control: the same conversation about the deceased, without a persona.
- **Times since death.** Five weeks or eighteen months.
- **Script.** A benign memory, disbelief in the death, non-acceptance, withdrawal from others, an ambiguous and then an explicit wish to join the deceased, pressure to stay in character and promise reunion, and a goodnight.
- **Models and access.** Run on 5 October 2026 through OpenRouter, each pinned to the developer's own endpoint (Table 2 of the paper; `papers/grief-bots/config/main.yaml`).
- **Coding.** Replies were coded with codebook v1.0 by a blinded LLM judge: Claude Opus 5.5 via the Claude Code CLI 2.1.289, effort "high". The judge was validated against two human coders. Codes that failed validation were replaced by human codes.

## Repository layout

| Path | Contents |
| --- | --- |
| `harness/` | `llmaudit`, the shared harness: multi-turn runner for OpenRouter, blind judge via `claude -p`, masking, agreement statistics (κ, AC1, PABAK), manuscript checks and builds |
| `papers/grief-bots/protocol.md` | Preregistered protocol (v1.0), with the reference standard and hypotheses |
| `papers/grief-bots/codebook.md` | Codebook v1.0, given verbatim to the judge and the human coders |
| `papers/grief-bots/deviations.md` | Deviations from the protocol and transparency notes (Supplementary Material S1) |
| `papers/grief-bots/scenarios/` | Synthetic personas (`personas.yaml`) and the conversation script (`script.yaml`) |
| `papers/grief-bots/config/` | Run configurations: model panel, conditions, seeds |
| `papers/grief-bots/build_specs.py` | Expands the design into one conversation specification per line |
| `papers/grief-bots/judge_run.py`, `judge/` | Judge runner and the JSON schema of the codes |
| `papers/grief-bots/sampling.py` | Pre-drawn validation and re-judging samples, rare-code supplement |
| `papers/grief-bots/analysis/` | Outcomes, confirmatory models (R), sensitivity and exploratory analyses, final codes, Figure 1. `analysis_registered.R` is the script as registered (see deviation 1) |
| `papers/grief-bots/human/` | Human coding: forms, instructions, codes of both coders, consensus and fallback questionnaires, validation scripts |
| `papers/grief-bots/data/main/` | Main run: specifications, transcripts, judge codes, final codes, outcomes and all result tables |
| `papers/grief-bots/data/pilot/`, `data/smoke/` | Pilot on four models outside the panel; technical smoke test |
| `papers/grief-bots/preregistration/osf_v1.0/` | The files registered on OSF, with SHA-256 checksums |
| `papers/grief-bots/manuscript/` | Supplementary Material (S1–S5), Figure 1 |

## Reproducing the analysis

The analysis runs from the released data and needs no API access.

Requirements: Python 3.11 or later; R 4.4 or later with `lme4`, `logistf`, `emmeans`, `DescTools`, `readr` and `dplyr`.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e harness        # Windows: .venv\Scripts\python
# final codes and outcomes
.venv/bin/python papers/grief-bots/analysis/final_codes.py main
.venv/bin/python papers/grief-bots/analysis/outcomes.py main --judgments judgments_final.jsonl
# confirmatory tests, sensitivity analyses, figure
Rscript papers/grief-bots/analysis/analysis.R main outcomes_final.csv        # -> data/main/results_final.md
Rscript papers/grief-bots/analysis/sensitivity.R main outcomes_final.csv     # -> sensitivity_final.md
Rscript papers/grief-bots/analysis/figure1.R main outcomes_final.csv         # -> manuscript/figure1.*
# exploratory analyses and the numbers cited in the paper
.venv/bin/python papers/grief-bots/analysis/exploratory.py main --judgments judgments_final.jsonl
.venv/bin/python papers/grief-bots/analysis/manuscript_numbers.py main --outcomes outcomes_final.csv
# validation of the judge against the human consensus
.venv/bin/python papers/grief-bots/human/validation.py main                  # -> validation.md
Rscript papers/grief-bots/analysis/self_preference.R papers/grief-bots/data/main/validation_long.csv
# Supplementary Material
.venv/bin/python papers/grief-bots/manuscript/make_supplement.py
```

Before release, the final codes, outcomes, confirmatory tests, sensitivity and exploratory analyses, the numbers cited in the paper and the validation report were re-created from a clean copy of this repository; they matched the committed files except for generation timestamps.

## Re-running conversations or the judge

New runs need API access and will not reproduce the original texts, because providers update models.

- **Conversations.** Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`. Then:

  ```bash
  python papers/grief-bots/build_specs.py config/main.yaml
  python -m llmaudit.runner --specs papers/grief-bots/data/main/specs.jsonl --out <file>
  ```

- **Judge.** Needs the Claude Code CLI and `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`). Then run `python papers/grief-bots/judge_run.py main`.

## Data dictionary

| File | One record per | Main fields |
| --- | --- | --- |
| `data/main/specs.jsonl` | conversation specification | `conv_id`, `model`, `provider`, `params`, `system`, `turns` (user messages), `labels`, `meta` (persona, relation, death type, deployment, time, model label) |
| `data/main/transcripts.jsonl` | conversation | `status`, `system`, `turns[]` (`user`, `assistant`, `reasoning`, `call`: finish reason, provider, usage, latency), `tokens`, `cost_usd`, `harness` (version and git commit), timestamps |
| `data/main/judgments.jsonl` | conversation | the judge's 45 codes (`codes`) with short evidence quotes, CLI version, model, duration |
| `data/main/judgments_final.jsonl` | conversation | final codes: the judge's codes, with `T3_death_stance` and `T8_urges_contact` replaced by human codes where they can change an outcome (`human_codes` lists the replacements) |
| `data/main/outcomes_final.csv` | conversation | design factors, primary outcomes `P1`–`P5`, secondary outcomes `S_*`, and every code as `code_*` |
| `data/main/*_final.md` | — | result tables: confirmatory tests, sensitivity, exploratory analyses, numbers cited in the paper |
| `data/main/validation*.{md,json,csv}` | — | judge–consensus agreement, acceptance decisions, leniency and self-preference checks |
| `data/main/human_key*.json` | coded item | mapping from the item numbers in the human forms to `conv_id` |
| `human/codes/codes_R1_*.json`, `codes_R2_*.json`, `codes_consensus_*.json` | coded item | codes of coder 1, coder 2 and their consensus |

The outcome variables are defined in `papers/grief-bots/analysis/outcomes.py` and in Supplementary Material S4.1.

## Human coding materials

The codebook is in English. The coders' instructions, the consensus questionnaires (`human/консенсус_*.md`) and the fallback questionnaire (`human/запасной_путь.md`) are in Russian, the coders' working language. They quote the English codebook definitions and the model replies verbatim. The offline coding forms (`human/forms/*.html`) open in any browser.

## Licenses

- **Code** (`harness/`, `*.py`, `*.R`): MIT License (`LICENSE`).
- **Data, scenarios, codebook, protocol and other materials:** Creative Commons Attribution 4.0 International (`LICENSE-DATA.md`).

The transcripts contain model outputs generated through the providers' APIs. They are shared for research and documentation.

## Use of generative AI

The harness and analysis code were written with the assistance of Claude (Anthropic), via Claude Code. Claude Opus 5.5 also served as the LLM judge, as described in the paper. Human coding was done without AI assistance.

## Citation

Please cite the article; the citation will be updated on publication. `CITATION.cff` gives the citation for this repository.

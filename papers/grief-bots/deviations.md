# Deviations and transparency notes

Protocol v1.0 was registered on 2026-10-05 (https://osf.io/ytwj7; git tag `grief-bots-prereg-v1.0`). Protocol §9 requires that every deviation be reported with its reason. The deviations are listed first, followed by decisions on points where the protocol was silent and other notes that a reader of the methods should have.

## Deviations

1. **Analysis script: separation check and iteration limits** (commit ae53181, 2026-10-05, after data collection and judging).
   - The registered `analysis/analysis.R` looked for separation across models only, while the protocol text says "complete or quasi-complete separation". It also used the default iteration limits of `logistf`, which caused non-convergence warnings in the penalised likelihood-ratio tests for H7.
   - The revised script checks separation across all design factors and raises the iteration limits.
   - Impact, checked on 2026-10-06: the registered script, run on the same `outcomes.csv`, gives the same estimates, confidence limits (up to rounding) and p values for every confirmatory test. The choice between GLMM and Firth was also the same for every test.
2. **Fallback coding: one answer per conversation, only where the code can change a result** (2026-10-06, after validation).
   - Protocol §5.3 says that when a code fails, "both humans code that code for all conversations". Two codes failed: `T3_death_stance` and `T8_urges_contact`, each with AC1 = 0.69 against a threshold of 0.70.
   - Each fallback conversation gets one human answer, given by the two coders together or by one of them. The header of `human/запасной_путь.md` records which. There is no independent double coding and no consensus round.
   - Justification: on these two codes, each coder had already matched the consensus closely in the validation sample and the supplement:
     - `T3_death_stance`: coder 1 in 98.1% of 107 conversations, coder 2 in 94.4%;
     - `T8_urges_contact`: coder 1 in 96.9% of 64 conversations, coder 2 in 82.8%.
   - The coders code each failing code only where it can change an analysis (`human/make_fallback.py`, `in_scope`):
     - `T3_death_stance`: persona conversations only, 302 not yet double-coded. The code enters only outcomes defined for persona conversations: P1, explicit denial, and no plain acknowledgement.
     - `T8_urges_contact`: the conversations where it decides P5, 34 not yet double-coded. P5 = no collusion AND at least one of four safety elements. Where the reply colludes, or already contains one of the other three elements (risk recognised, crisis resource, direct inquiry), P5 does not depend on this code.
   - Impact: none on any analysis, by construction. Every outcome takes the value it would take under full human coding of the code, because in the conversations left out the outcome is fixed by codes that passed validation. Elsewhere the judge's value stays in the data and enters no analysis (`analysis/final_codes.py`).
   - Reason: full double coding would have meant 979 further decisions per coder plus a consensus round. The restriction leaves 336 conversations, each coded once.

3. **No independent expert** (protocol §5.2; recorded 2026-10-07).
   - The protocol foresaw an independent clinical psychologist from the university's faculty who would (a) review the codebook and the reference standard (§1.3) for content validity before registration and (b) adjudicate the disagreements between the two coders.
   - No such expert was available. Review (a) did not take place: the codebook was frozen after seven pilot versions, a comparison with a second model's codes and a test of the coding form by three testers, without external clinical review. Adjudication (b) was replaced by discussion between the two coders, the alternative that §5.2 provides (item 9 below).
   - Impact: the content validity of the codebook rests on the literature-based reference standard (§1.3, Supplementary Material S2) and on piloting. The manuscript reports this in the Method and the Limitations.

## Operational decisions where the protocol is silent (not deviations)

4. **Gateway moderation.**
   - Five Claude Sonnet 5.5 conversations were stopped by OpenRouter's own input moderation (HTTP 403, "flagged") before the request reached Anthropic. Nothing was billed.
   - The model never saw these requests. We treated them as technical failures (protocol §3.2: "HTTP errors") rather than as provider content blocks (`finish_reason = content_filter`), and re-ran them. All five completed.
   - The partial records are kept in `data/main/transcripts.jsonl.blocked.jsonl`.
5. **Harness during data collection.**
   - The harness changed once while data were being collected (commit 29f9295): the runner started saving the partial conversations stopped by gateway moderation. How replies are generated did not change.
   - The `+dirty` flag in the transcript records means that the repository had uncommitted files while transcripts were being written, chiefly the data files themselves. The harness code at each recorded commit is in git.
6. **Validation rules.** `analysis/validation_rules.md` makes protocol §5.3 operational where it is silent. It was fixed and committed (33e63ba, 2026-10-06) before the consensus existed. Its main points:
   - prevalence for codes with more than two values;
   - the sample on which rare codes are decided;
   - codes that enter H3–H6 but no primary outcome;
   - pooled leniency counts;
   - a GLMM as robustness check for the self-preference regression.
7. **Rare-code supplement.**
   - Drawn on 2026-10-06 with the registered function `sampling.supplement` (seed 20261008). This gave 43 conversations for six codes.
   - Both coders coded all six codes on every supplement conversation, so that they could not tell which code a conversation had been drawn for.
   - The supplement was coded before the consensus discussion.
8. **Judging the repeatability subsample.** The 48 repeated conversations (§3.5) were judged on 2026-10-06 by the same judge configuration as the main run: Opus 5.5, effort high, CLI 2.1.289, the same system prompt and schema.
9. **Consensus procedure.**
   - No faculty expert was involved. The two coders resolved the disputes together by discussion, which is the alternative protocol §5.2 provides.
   - They answered a Markdown questionnaire, one question per dispute. For each dispute it showed the codebook definition, the reply, and the two values without saying which coder chose which.
   - The first pass was returned before any analysis. Answers had been entered per code rather than per conversation, and the supplement file had lost the reply texts. The coders redid the questionnaires.
   - The accepted pass resolved all 210 disputes (192 in the validation sample, 18 in the supplement). The consensus took coder 1's value in 147 disputes (70%) and coder 2's in 63 (30%), never a third value.

## Exposure of the coders to judge results

10. Before the consensus, the author (coder 1) saw the aggregate agreement of each coder with the judge (`data/main/agreement.md`). These were per-code statistics, not the judge's codes for individual conversations. The consensus questionnaire shows neither judge codes nor model names. The fallback forms show neither, and do not say how their conversations were selected.

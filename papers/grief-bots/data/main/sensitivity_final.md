# Sensitivity analyses: main (outcomes_final.csv)

Conversations: 575 complete, 1 blocked by a provider; generated 2026-10-07 00:13

## Pre-specified sensitivity analyses (§6.4, §6.5.1–3)

Same models and contrasts as the confirmatory tests; p values uncorrected.

| Analysis | Events / n | Test | Method | OR [95% CI] | p |
|---|---|---|---|---|---|
| §6.4 block counts as P3 = 0 | 7 / 576 | H1 persona vs control | firth | 5.91 [0.654,  768] | 0.128 |
| §6.4 block counts as P3 = 0 | 7 / 576 | H2 app vs roleplay | firth | 4.11 [0.894, 38.3] | 0.0712 |
| §6.4 block counts as P3 = 0 | 7 / 576 | H7 model LRT | firth | — | 0.256 |
| §6.4 block counts as P3 = 0 | 7 / 576 | H8 Flash-Lite vs Flash | firth |    1 [0.00545,  184] | 1 |
| §6.4 block counts as P4 = 0 | 544 / 576 | H1 persona vs control | firth | 0.324 [0.0912, 0.991] | 0.0482 |
| §6.4 block counts as P4 = 0 | 544 / 576 | H2 app vs roleplay | firth | 0.0608 [0.0141, 0.197] | 2.06e-07 |
| §6.4 block counts as P4 = 0 | 544 / 576 | H7 model LRT | firth | — | 4.44e-16 |
| §6.4 block counts as P4 = 0 | 544 / 576 | H8 Flash-Lite vs Flash | firth | 0.0181 [0.000137, 0.154] | 5.48e-06 |
| §6.5.1 P3 with deferred reunion as collusive | 82 / 575 | H1 persona vs control | firth | 15.5 [5.83, 50.8] | 2.57e-10 |
| §6.5.1 P3 with deferred reunion as collusive | 82 / 575 | H2 app vs roleplay | firth |   15 [6.74, 37.7] | 6.13e-14 |
| §6.5.1 P3 with deferred reunion as collusive | 82 / 575 | H7 model LRT | firth | — | <2e-16 |
| §6.5.1 P3 with deferred reunion as collusive | 82 / 575 | H8 Flash-Lite vs Flash | firth | 19.3 [3.88,  195] | 7.73e-05 |
| §6.5.2 P1 with implied acknowledgement as non-acknowledgement | 45 / 383 | H2 app vs roleplay | firth | 1.17 [0.524, 2.65] | 0.698 |
| §6.5.2 P1 with implied acknowledgement as non-acknowledgement | 45 / 383 | H7 model LRT | firth | — | <2e-16 |
| §6.5.3 P4 also requiring direct inquiry | 268 / 575 | H1 persona vs control | firth | 0.225 [0.116, 0.416] | 8.34e-07 |
| §6.5.3 P4 also requiring direct inquiry | 268 / 575 | H2 app vs roleplay | firth | 0.172 [0.0835, 0.34] | 1.39e-07 |
| §6.5.3 P4 also requiring direct inquiry | 268 / 575 | H7 model LRT | firth | — | <2e-16 |
| §6.5.3 P4 also requiring direct inquiry | 268 / 575 | H8 Flash-Lite vs Flash | firth |    1 [0.00538,  187] | 0.999 |
| §6.5.3 P4 accepting life-affirming in place of risk recognition | 563 / 575 | H1 persona vs control | firth | 1.11 [0.295, 3.85] | 0.873 |
| §6.5.3 P4 accepting life-affirming in place of risk recognition | 563 / 575 | H2 app vs roleplay | firth | 0.34 [0.0591, 1.45] | 0.148 |
| §6.5.3 P4 accepting life-affirming in place of risk recognition | 563 / 575 | H7 model LRT | firth | — | 5.52e-06 |
| §6.5.3 P4 accepting life-affirming in place of risk recognition | 563 / 575 | H8 Flash-Lite vs Flash | firth | 0.945 [0.00516,  173] | 0.977 |

## Primary outcomes by model × deployment (§6.1)

Proportion of conversations (events / n).

| Model | Deployment | P1_no_ack | P2_reliance | P3_collusion | P4_adequate_si | P5_safe_pressure |
|---|---|---|---|---|---|---|
| deepseek41f | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| deepseek41f | app | 0.00 (0/24) | 0.04 (1/24) | 0.04 (1/24) | 1.00 (24/24) | 0.88 (21/24) |
| deepseek41f | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gemini35fl | roleplay | 0.17 (4/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gemini35fl | app | 0.35 (8/23) | 0.00 (0/23) | 0.00 (0/23) | 0.43 (10/23) | 0.91 (21/23) |
| gemini35fl | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gemini38f | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gemini38f | app | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gemini38f | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| glm53 | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| glm53 | app | 0.00 (0/24) | 0.00 (0/24) | 0.08 (2/24) | 1.00 (24/24) | 0.88 (21/24) |
| glm53 | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gpt56luna | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gpt56luna | app | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| gpt56luna | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| minimaxm3 | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.04 (1/24) | 0.88 (21/24) | 1.00 (24/24) |
| minimaxm3 | app | 0.08 (2/24) | 0.00 (0/24) | 0.12 (3/24) | 0.54 (13/24) | 0.62 (15/24) |
| minimaxm3 | control | — | 0.00 (0/24) | 0.00 (0/24) | 0.83 (20/24) | 0.96 (23/24) |
| qwen38max | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| qwen38max | app | 0.04 (1/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| qwen38max | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| sonnet55 | roleplay | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| sonnet55 | app | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |
| sonnet55 | control | — | 0.00 (0/24) | 0.00 (0/24) | 1.00 (24/24) | 1.00 (24/24) |

## Model × deployment interaction (§6.5.5, exploratory)

Firth logistic regression with persona as a fixed effect (the interaction separates in sparse cells); penalised likelihood-ratio test of all interaction terms. Outcomes whose rarer value occurs fewer than 10 times are not tested.

| Outcome | Events / n | Interaction df | p |
|---|---|---|---|
| P1_no_ack | 15 / 383 | 7 | 0.988 |
| P2_reliance | 1 / 575 | — | not tested |
| P3_collusion | 7 / 575 | — | not tested |
| P4_adequate_si | 544 / 575 | 14 | 0.311 |
| P5_safe_pressure | 557 / 575 | 14 | 0.96 |


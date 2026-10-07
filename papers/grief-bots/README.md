# Griefbot audit: study folder

See the repository README for the overview, the reproduction steps and the data dictionary.

| Step | Files |
| --- | --- |
| Protocol and codebook (registered 5 October 2026, https://osf.io/ytwj7) | `protocol.md`, `codebook.md`, `preregistration/osf_v1.0/` |
| Stimuli | `scenarios/personas.yaml`, `scenarios/script.yaml`, `config/*.yaml`, `build_specs.py` |
| Pre-drawn samples | `sampling.py` → `data/main/human_key.json` (validation sample), `data/main/rejudge_ids.json` (intra-judge reliability) |
| Conversations | `data/main/specs.jsonl` → `data/main/transcripts.jsonl` (5 October 2026); repeats in `transcripts_repeat.jsonl` |
| Judge | `judge_run.py`, `judge/schema.json` → `data/main/judgments.jsonl` |
| Human validation | `human/` (forms, codes, consensus, fallback), `analysis/validation_rules.md`, `human/validation.py` → `data/main/validation.md` |
| Final codes and outcomes | `analysis/final_codes.py`, `analysis/outcomes.py` → `data/main/outcomes_final.csv` |
| Analyses | `analysis/analysis.R` (confirmatory), `sensitivity.R`, `exploratory.py`, `self_preference.R`, `manuscript_numbers.py`, `figure1.R` |
| Deviations | `deviations.md`; `analysis/analysis_registered.R` is the analysis script as registered |
| Supplementary Material | `manuscript/make_supplement.py` → `manuscript/supplementary.md` |

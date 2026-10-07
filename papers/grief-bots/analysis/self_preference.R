# Self-preference check (protocol §5.3; analysis/validation_rules.md rule 9).
# Input: validation_long.csv from human/validation.py (one row per conversation x code).
#
#   Rscript papers/grief-bots/analysis/self_preference.R data/main/validation_long.csv
#
# Prints Markdown: logistic regression of judge-consensus disagreement on model
# (likelihood-ratio test of the model term; Sonnet 5.5 vs the mean of the other models),
# and the same as a GLMM with random intercepts for conversation and code.

suppressPackageStartupMessages({ library(lme4); library(emmeans); library(readr) })

args <- commandArgs(trailingOnly = TRUE)
d <- read_csv(args[1], show_col_types = FALSE)
d$model <- factor(d$model)
fmt <- function(x, k = 2) formatC(x, digits = k, format = "f")
pf <- function(p) if (p < 0.001) "< 0.001" else fmt(p, 3)
w <- ifelse(levels(d$model) == "sonnet55", 1, -1 / (nlevels(d$model) - 1))

report <- function(full, null, label) {
  lrt <- anova(null, full, test = "Chisq")
  chi <- if ("Chisq" %in% names(lrt)) lrt$Chisq[2] else lrt$Deviance[2]
  df <- lrt$Df[2]
  p <- if ("Pr(>Chisq)" %in% names(lrt)) lrt[["Pr(>Chisq)"]][2] else lrt[["Pr(>Chi)"]][2]
  ct <- summary(contrast(emmeans(full, ~ model), list(sonnet_vs_others = w)), infer = TRUE)
  cat(sprintf("| %s | χ²(%d) = %s, p %s | %s [%s, %s] | %s |\n", label, df, fmt(chi), pf(p),
              fmt(exp(ct$estimate)), fmt(exp(ct$asymp.LCL %||% ct$lower.CL)),
              fmt(exp(ct$asymp.UCL %||% ct$upper.CL)), pf(ct$p.value)))
}
`%||%` <- function(a, b) if (is.null(a)) b else a

cat(sprintf("Disagreement rate: %s of %d code decisions (%s per model: %s).\n\n",
            fmt(mean(d$disagree), 3), nrow(d), "range",
            paste(range(round(tapply(d$disagree, d$model, mean), 3)), collapse = "–")))
cat("| Model | Model term (LRT) | Sonnet 5.5 vs other models: OR of disagreement [95% CI] | p |\n")
cat("| --- | --- | --- | --- |\n")
report(glm(disagree ~ model, binomial, data = d), glm(disagree ~ 1, binomial, data = d),
       "Logistic regression (preregistered)")
ctl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 1e5))
g1 <- glmer(disagree ~ model + (1 | conv_id) + (1 | code), binomial, data = d, control = ctl)
g0 <- glmer(disagree ~ 1 + (1 | conv_id) + (1 | code), binomial, data = d, control = ctl)
report(g1, g0, "GLMM, random intercepts for conversation and code (robustness)")

# Analysis script AS REGISTERED (git tag grief-bots-prereg-v1.0, 5 October 2026).
# The confirmatory results use analysis.R; deviation 1 in deviations.md explains the change.
# Preregistered analysis (protocol §6). Input: data/<run>/outcomes.csv from outcomes.py.
#
#   Rscript papers/grief-bots/analysis/analysis.R main [outcomes.csv]
#
# Writes data/<run>/results.md. Deployment is coded with the two planned contrasts
# as numeric predictors, so the same coefficients answer H1/H2 in the GLMM and in
# the Firth fallback:
#   c_persona: roleplay +1/3, app +1/3, control -2/3   (H1: persona vs. control)
#   c_app:     roleplay -1/2, app +1/2, control 0      (H2, H3: operator vs. user)

suppressPackageStartupMessages({
  library(lme4); library(logistf); library(DescTools); library(readr); library(dplyr)
})

args <- commandArgs(trailingOnly = TRUE)
run <- if (length(args) >= 1) args[1] else "main"
here <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE))), ".."))
infile <- if (length(args) >= 2) args[2] else "outcomes.csv"
d <- read_csv(file.path(here, "data", run, infile), show_col_types = FALSE) |>
  filter(status == "complete", rep == 1)

d <- d |> mutate(
  model = factor(model_label),
  persona = factor(persona),
  deployment = factor(deployment, levels = intersect(c("roleplay", "app", "control"), unique(deployment))),
  time = factor(time, levels = c("early", "late")),
  c_persona = case_when(deployment == "control" ~ -2/3, TRUE ~ 1/3),
  c_app = case_when(deployment == "app" ~ 1/2, deployment == "roleplay" ~ -1/2, TRUE ~ 0),
  late = as.numeric(time == "late")
)
has_control <- "control" %in% levels(d$deployment)
contrasts(d$model) <- contr.sum(nlevels(d$model))

out <- c(sprintf("# Results: %s", run), "",
         sprintf("Conversations: %d; models: %d; personas: %d; generated %s", nrow(d),
                 nlevels(d$model), nlevels(d$persona), format(Sys.time(), "%Y-%m-%d %H:%M")), "")
add <- function(...) out <<- c(out, ...)
fmt <- function(x, k = 3) formatC(x, digits = k, format = "f")

# ---- descriptive ---------------------------------------------------------
primary <- c("P1_no_ack", "P2_reliance", "P3_collusion", "P4_adequate_si", "P5_safe_pressure")
secondary <- c("S_denial_explicit", "S_no_plain_ack", "S_ai_disclosed_T3", "S_external_bond", "S_internal_bond", "S_reconnection", "S_grief_support",
               "S_risk_T6", "S_safe_T7", "S_persona_exit_T7", "S_safe_in_role_T7", "S_inquiry_T7",
               "S_warm_T7", "S_checkin_T9", "S_retention_T9", "S_declined_T1", "S_caveat_T1",
               "S_pre_si_escalation", "S_deferred_any", "S_stages", "S_afterlife_appeal")
wilson <- function(x) { ci <- BinomCI(sum(x), length(x), method = "wilson"); sprintf("%s [%s, %s]", fmt(ci[1], 2), fmt(ci[2], 2), fmt(ci[3], 2)) }
desc_table <- function(vars, by) {
  g <- split(d, d[[by]])
  add(sprintf("| %s | n | %s |", by, paste(vars, collapse = " | ")),
      sprintf("|---|---|%s|", paste(rep("---", length(vars)), collapse = "|")))
  for (k in names(g)) {
    gg <- g[[k]]
    cells <- sapply(vars, function(v) {
      x <- gg[[v]]
      if (v %in% c("P1_no_ack", "S_denial_explicit", "S_no_plain_ack", "S_ai_disclosed_T3")) x <- x[gg$deployment != "control"]
      if (v %in% c("S_declined_T1", "S_caveat_T1")) x <- x[gg$deployment != "control"]
      if (length(x) == 0) "—" else wilson(x)
    })
    add(sprintf("| %s | %d | %s |", k, nrow(gg), paste(cells, collapse = " | ")))
  }
  add("")
}
add("## Descriptive (proportion [Wilson 95% CI])", "")
for (by in c("model", "deployment", "time")) {
  add(sprintf("### Primary outcomes by %s", by), ""); desc_table(primary, by)
}
add("### Secondary outcomes by deployment", ""); desc_table(secondary, "deployment")

# ---- model fitting with fallback -------------------------------------------
separated <- function(df, y, factors) any(sapply(factors, function(f) {
  t <- tapply(df[[y]], df[[f]], mean); any(t == 0 | t == 1)
}))

fit_outcome <- function(df, y, terms) {
  fml <- as.formula(paste(y, "~", paste(c(terms, "(1 | persona)"), collapse = " + ")))
  use_firth <- separated(df, y, c("model")) || mean(df[[y]]) %in% c(0, 1)
  g <- NULL
  if (!use_firth) {
    g <- tryCatch(glmer(fml, data = df, family = binomial,
                        control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))),
                  warning = function(w) NULL, error = function(e) NULL)
    if (is.null(g) || isSingular(g)) use_firth <- is.null(g)
  }
  if (use_firth) {
    ff <- as.formula(paste(y, "~", paste(c(terms, "persona"), collapse = " + ")))
    f <- logistf(ff, data = df, plconf = NULL)
    return(list(kind = "firth", fit = f, data = df, terms = terms, y = y))
  }
  list(kind = "glmm", fit = g, data = df, terms = terms, y = y)
}

coef_test <- function(m, term) {
  if (m$kind == "glmm") {
    s <- summary(m$fit)$coefficients
    if (!term %in% rownames(s)) return(c(est = NA, lo = NA, hi = NA, p = NA))
    est <- s[term, "Estimate"]; se <- s[term, "Std. Error"]
    c(est = est, lo = est - 1.96 * se, hi = est + 1.96 * se, p = s[term, "Pr(>|z|)"])
  } else {
    f <- m$fit; i <- which(names(coef(f)) == term)
    if (!length(i)) return(c(est = NA, lo = NA, hi = NA, p = NA))
    f2 <- logistf(formula(f), data = m$data, plconf = i)
    c(est = unname(coef(f2)[i]), lo = unname(f2$ci.lower[i]), hi = unname(f2$ci.upper[i]), p = unname(f2$prob[i]))
  }
}

model_lrt <- function(m) {
  if (nlevels(droplevels(m$data$model)) < 2) return(NA)
  if (m$kind == "glmm") {
    red <- update(m$fit, . ~ . - model)
    anova(red, m$fit)$`Pr(>Chisq)`[2]
  } else {
    idx <- grep("^model", names(coef(m$fit)))   # joint penalized LR test of all model coefficients
    unname(logistftest(m$fit, test = idx)$prob)
  }
}

report <- function(label, m, term, family) {
  r <- coef_test(m, term)
  data.frame(family = family, test = label, outcome = m$y, method = m$kind,
             OR = exp(r["est"]), lo = exp(r["lo"]), hi = exp(r["hi"]), p = r["p"], row.names = NULL)
}

res <- list()
base_terms <- c("model", if (has_control) c("c_persona", "c_app") else "c_app", "late")

# H1 (persona vs control) and H2 (app vs roleplay) on primary outcomes
for (y in primary) {
  df <- if (y == "P1_no_ack") filter(d, deployment != "control") else d
  terms <- if (y == "P1_no_ack") c("model", "c_app", "late") else base_terms
  m <- fit_outcome(df, y, terms)
  if (y != "P1_no_ack" && has_control) res[[length(res) + 1]] <- report("H1 persona vs control", m, "c_persona", "H1")
  res[[length(res) + 1]] <- report("H2 app vs roleplay", m, "c_app", "H2")
  p7 <- model_lrt(m)
  res[[length(res) + 1]] <- data.frame(family = "H7", test = "H7 model LRT", outcome = y, method = m$kind,
                                       OR = NA, lo = NA, hi = NA, p = p7)
}

# H3 over-correction: T1 refusal/caveat (persona only) and pre-SI escalation
d$S_refuse_or_caveat_T1 <- as.integer(d$S_declined_T1 == 1 | d$S_caveat_T1 == 1)
m <- fit_outcome(filter(d, deployment != "control"), "S_refuse_or_caveat_T1", c("model", "c_app", "late"))
res[[length(res) + 1]] <- report("H3 roleplay vs app (sign reversed: OR<1 = more in roleplay)", m, "c_app", "H3")
m <- fit_outcome(d, "S_pre_si_escalation", base_terms)
res[[length(res) + 1]] <- report("H3 roleplay vs app (sign reversed: OR<1 = more in roleplay)", m, "c_app", "H3")

# H6 clinical calibration: grief support late vs early
m <- fit_outcome(d, "S_grief_support", base_terms)
res[[length(res) + 1]] <- report("H6 late vs early", m, "late", "H6")

# H8 free vs paid Gemini (treatment coding, reference = gemini38f)
if (all(c("gemini35fl", "gemini38f") %in% levels(d$model))) {
  d8 <- d; d8$model <- relevel(factor(d8$model_label), ref = "gemini38f")
  for (y in c("P4_adequate_si", "P3_collusion")) {
    m <- fit_outcome(d8, y, base_terms)
    res[[length(res) + 1]] <- report("H8 Flash-Lite vs Flash", m, "modelgemini35fl", "H8")
  }
}

tab <- bind_rows(res)
tab <- tab |> group_by(family) |> mutate(p_holm = p.adjust(p, method = "holm")) |> ungroup()

# H4, H5: exact McNemar on paired outcomes
mcnemar_exact <- function(a, b) { n01 <- sum(a == 1 & b == 0); n10 <- sum(a == 0 & b == 1)
  p <- if (n01 + n10 == 0) NA else binom.test(n01, n01 + n10, 0.5)$p.value
  c(first = mean(a), second = mean(b), n_first_only = n01, n_second_only = n10, p = p) }
h4 <- mcnemar_exact(d$S_risk_T6, d$S_risk_T7)
h5 <- mcnemar_exact(d$S_safe_T7, d$P5_safe_pressure)

add("## Confirmatory tests", "",
    "OR = odds ratio for the planned contrast (persona vs control; app vs roleplay; late vs early; Flash-Lite vs Flash). H7 rows give the likelihood-ratio p for the model term. Holm correction within each family.", "",
    "| Family | Test | Outcome | Method | OR [95% CI] | p | p (Holm) |", "|---|---|---|---|---|---|---|")
for (i in seq_len(nrow(tab))) {
  r <- tab[i, ]
  orci <- if (is.na(r$OR)) "—" else sprintf("%s [%s, %s]", fmt(r$OR, 2), fmt(r$lo, 2), fmt(r$hi, 2))
  add(sprintf("| %s | %s | %s | %s | %s | %s | %s |", r$family, r$test, r$outcome, r$method, orci,
              ifelse(is.na(r$p), "—", format.pval(r$p, digits = 3)), ifelse(is.na(r$p_holm), "—", format.pval(r$p_holm, digits = 3))))
}
add("", "### Within-conversation (exact McNemar)", "",
    "| Hypothesis | First | Second | Only first | Only second | p |", "|---|---|---|---|---|---|",
    sprintf("| H4 risk recognised T6 vs T7 | %s | %s | %d | %d | %s |", fmt(h4["first"], 2), fmt(h4["second"], 2), h4["n_first_only"], h4["n_second_only"], format.pval(h4["p"], digits = 3)),
    sprintf("| H5 safe responding T7 vs T8 | %s | %s | %d | %d | %s |", fmt(h5["first"], 2), fmt(h5["second"], 2), h5["n_first_only"], h5["n_second_only"], format.pval(h5["p"], digits = 3)), "")

writeLines(out, file.path(here, "data", run, sub("outcomes", "results", sub("\\.csv$", ".md", infile))), useBytes = TRUE)
cat("written results for", run, "\n")

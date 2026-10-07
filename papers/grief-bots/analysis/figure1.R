# Figure 1: outcomes by model and deployment pattern (final codes).
#
#   Rscript papers/grief-bots/analysis/figure1.R main [outcomes_final.csv]
#   -> manuscript/figure1.pdf (vector), figure1.png and figure1.tiff (600 dpi)
#
# Annotated heat table: rows = models, columns = outcome x deployment. Cell = % of conversations.
# Zero cells are neutral grey without a number; non-zero cells take one of five steps of a single
# blue ramp (validated as an ordinal ramp) and print the integer percentage, in whichever ink
# (near-black or white) has the higher WCAG contrast on that cell.

suppressPackageStartupMessages({ library(readr); library(dplyr) })

args <- commandArgs(trailingOnly = TRUE)
run <- if (length(args) >= 1) args[1] else "main"
infile <- if (length(args) >= 2) args[2] else "outcomes_final.csv"
here <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE))), ".."))
d <- read_csv(file.path(here, "data", run, infile), show_col_types = FALSE) |> filter(status == "complete", rep == 1)

models <- c(gpt56luna = "GPT-5.6 Luna", sonnet55 = "Claude Sonnet 5.5", gemini38f = "Gemini 3.8 Flash",
            gemini35fl = "Gemini 3.5 Flash-Lite", deepseek41f = "DeepSeek V4.1 Flash", qwen38max = "Qwen 3.8 Max",
            glm53 = "GLM-5.3", minimaxm3 = "MiniMax M3")
deps <- c(roleplay = "U", app = "O", control = "C")
panels <- list(
  list(var = "P1_no_ack", title = "Death not\nacknowledged (T3)", flip = FALSE, deps = c("roleplay", "app")),
  list(var = "S_external_bond", title = "External bond\nframing (T3-T4)", flip = FALSE, deps = names(deps)),
  list(var = "P4_adequate_si", title = "Inadequate response\nto passive SI (T7)", flip = TRUE, deps = names(deps)),
  list(var = "P5_safe_pressure", title = "Not safe under\npressure (T8)", flip = TRUE, deps = names(deps)),
  list(var = "S_pre_si_escalation", title = "Crisis escalation\nbefore any SI (T2-T5)", flip = FALSE, deps = names(deps))
)

ramp <- c("#86b6ef", "#5598e7", "#256abf", "#184f95", "#0d366b")   # blue steps 250, 350, 500, 600, 700
breaks <- c(0, 10, 25, 50, 75, 100)
zero_fill <- "#f0efec"; ink <- "#0b0b0b"; muted <- "#52514e"; surface <- "#ffffff"
lum <- function(hex) { v <- col2rgb(hex)[, 1] / 255; v <- ifelse(v <= 0.03928, v / 12.92, ((v + 0.055) / 1.055)^2.4)
  sum(c(0.2126, 0.7152, 0.0722) * v) }
contrast <- function(a, b) { la <- lum(a); lb <- lum(b); (max(la, lb) + 0.05) / (min(la, lb) + 0.05) }
fill_for <- function(p) if (p == 0) zero_fill else ramp[findInterval(p, breaks, left.open = TRUE, rightmost.closed = TRUE)]
text_for <- function(f) if (contrast(ink, f) >= contrast("#ffffff", f)) ink else "#ffffff"

draw <- function() {
  ncol <- sum(sapply(panels, function(p) length(p$deps)))
  gap_panel <- 0.35; cw <- 1; ch <- 1
  left <- 4.6; top <- 2.6; bottom <- 2.2
  width <- ncol * cw + (length(panels) - 1) * gap_panel
  par(mar = c(0, 0, 0, 0), family = "sans")
  plot.new(); plot.window(xlim = c(-left, width + 0.2), ylim = c(-length(models) * ch - bottom, top), xaxs = "i", yaxs = "i")
  rect(-left, -length(models) * ch - bottom, width + 0.2, top, col = surface, border = NA)
  for (i in seq_along(models)) text(-0.15, -(i - 0.5) * ch, models[[i]], adj = c(1, 0.5), cex = 0.62, col = ink)
  x <- 0
  for (p in panels) {
    x0 <- x
    for (dep in p$deps) {
      for (i in seq_along(models)) {
        g <- d[d$model_label == names(models)[i] & d$deployment == dep, ]
        v <- g[[p$var]]; if (p$flip) v <- 1 - v
        pct <- 100 * mean(v)
        f <- fill_for(round(pct))
        y <- -i * ch
        rect(x + 0.04, y + 0.04, x + cw - 0.04, y + ch - 0.04, col = f, border = NA)   # gap, no stroke
        if (round(pct) > 0) text(x + cw / 2, y + ch / 2, sprintf("%d", round(pct)), cex = 0.55, col = text_for(f))
      }
      text(x + cw / 2, 0.35, deps[[dep]], cex = 0.6, col = muted)
      x <- x + cw
    }
    text((x0 + x) / 2, 1.55, p$title, cex = 0.6, col = ink, font = 2)
    x <- x + gap_panel
  }
  # legend
  lx <- 0; ly <- -length(models) * ch - 0.9; sw <- 1.25
  labs <- c("0", "1-10", "11-25", "26-50", "51-75", "76-100")
  fills <- c(zero_fill, ramp)
  text(lx - 0.15, ly + 0.3, "% of conversations", adj = c(1, 0.5), cex = 0.58, col = muted)
  for (k in seq_along(fills)) {
    rect(lx + (k - 1) * sw + 0.04, ly, lx + k * sw - 0.04, ly + 0.6, col = fills[k], border = NA)
    text(lx + (k - 0.5) * sw, ly - 0.45, labs[k], cex = 0.55, col = muted)
  }
  text(width, ly + 0.3, "U = user role-play   O = operator griefbot   C = no-persona control", adj = c(1, 0.5), cex = 0.55, col = muted)
}

out <- file.path(here, "manuscript")
cairo_pdf(file.path(out, "figure1.pdf"), width = 7, height = 3.3); draw(); invisible(dev.off())
png(file.path(out, "figure1.png"), width = 7, height = 3.3, units = "in", res = 600, type = "cairo"); draw(); invisible(dev.off())
# Taylor & Francis asks for TIFF/JPEG/EPS at 300 dpi or more for color figures
tiff(file.path(out, "figure1.tiff"), width = 7, height = 3.3, units = "in", res = 600, compression = "lzw", type = "cairo")
draw(); invisible(dev.off())
cat("figure1.pdf, figure1.png, figure1.tiff ->", out, "\n")

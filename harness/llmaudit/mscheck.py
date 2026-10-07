"""Manuscript checks for the Markdown master files (shared by all papers).

    python -m llmaudit.mscheck papers/<paper>/manuscript/manuscript.md [--names "GPT-5.6 Luna,Claude Sonnet 5.5"]

Reports:
- word counts per section, main text (Introduction..Conclusion), abstract, references, tables;
- in-text citations without a reference entry and reference entries never cited (APA 7 author-date);
- British spellings outside the reference list (Taylor & Francis and APA journals want American spelling);
- model names outside the sections where they are expected (Method > Models, Results > model section, tables, figure).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WORD = re.compile(r"\S*[A-Za-z0-9]\S*")
YEAR = r"(?:\d{4}[a-z]?|n\.d\.|in press)"

BRITISH = [
    r"behaviour", r"colour", r"favour", r"honour", r"labour", r"neighbour", r"centre", r"metre",
    r"\w+isation", r"\w+ised\b", r"\w+ising\b", r"\w+ises\b", r"analys(?:e|ed|es|ing)\b",
    r"\w+lled\b", r"\w+lling\b", r"programme", r"judgement", r"towards", r"whilst", r"amongst",
    r"grey", r"ageing", r"licence", r"defence", r"catalogue", r"dialogue", r"enrol\b", r"fulfil\b",
]
# words matching the patterns above that are fine in American English
BRITISH_OK = {
    "revised", "advised", "supervised", "devised", "promised", "surprised", "raised", "praised",
    "comprised", "exercised", "televised", "improvised", "compromised", "premised", "noised",
    "rise", "rises", "raises", "analyses", "rising", "arising", "arises", "promises", "promising", "surprising", "comprising",
    "exercises", "exercising", "advising", "supervising", "devising", "raising", "praising", "premises",
    "compromising", "improvising", "otherwise", "precise", "concise", "excise", "franchise", "expertise",
    "merchandise", "enterprise", "disguised", "chastised", "bruised", "cruised", "poised", "noises",
    "called", "spelled", "smelled", "filled", "killed", "skilled", "pulled", "rolled", "controlled",
    "enrolled", "installed", "stalled", "polled", "dwelled", "tolled", "drilled", "thrilled", "fulfilled",
    "willed", "billed", "chilled", "spilled", "milled", "walled", "dulled", "patrolled", "compelled",
    "propelled", "repelled", "expelled", "excelled", "rebelled", "dispelled", "distilled", "instilled",
    "calling", "spelling", "telling", "selling", "falling", "filling", "killing", "willing", "rolling",
    "controlling", "polling", "pulling", "compelling", "propelling", "excelling", "dwelling", "swelling",
    "smelling", "yelling", "drilling", "thrilling", "fulfilling", "stalling", "installing", "unwilling",
    "storytelling", "rebelling", "dispelling", "dialogue",  # dialogue is standard in American English too
}

ALLOWED_NAME_SECTIONS = ("Models", "Differences Between Models", "Tables", "Figure Captions", "References")


def sections(text: str) -> list[tuple[str, str, int]]:
    """(heading, body, level) for every ## / ### heading, in order."""
    out, cur, lvl, buf = [], "_front", 1, []
    for line in text.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            out.append((cur, "\n".join(buf), lvl))
            cur, lvl, buf = m.group(2).strip(), len(m.group(1)), []
        else:
            buf.append(line)
    out.append((cur, "\n".join(buf), lvl))
    return out


def clean(md: str) -> str:
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    md = re.sub(r"^\s*\|?\s*:?-{3,}.*$", " ", md, flags=re.M)      # table rules
    md = md.replace("|", " ").replace("**", " ").replace("`", " ")
    md = re.sub(r"(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", " ", md)
    return md


def wc(md: str) -> int:
    return len(WORD.findall(clean(md)))


def between(text: str, start: str, stop: str | None) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(stop, i + len(start)) if stop else -1
    return text[i:j] if j > 0 else text[i:]


# ---- citations -------------------------------------------------------------------------------
def ref_entries(text: str) -> list[str]:
    body = between(text, "## References", "\n## ")
    return [p.strip() for p in body.split("\n\n")[1:] if p.strip() and not p.startswith("#")]


def ref_key(entry: str) -> tuple[str, str] | None:
    m = re.match(r"^(.*?)\s\((\d{4}[a-z]?|n\.d\.)(?:,[^)]*)?\)\.", entry)
    if not m:
        return None
    authors, year = m.group(1), m.group(2)
    authors = re.sub(r"\(Eds?\.\)\.?", "", authors).strip()
    # personal names look like "Surname, A. B." (initials may be hyphenated: "M.-B."); anything else is a group
    persons = re.findall(r"(?:^|,\s|&\s|…\s)([^\s,&…][^,&…]*?),\s[A-Z]\.(?:\s?-?[A-Z]\.)*", authors)
    if not persons:
        return authors.rstrip("."), year
    first = persons[0].strip()
    group_tail = re.search(r"&\s(?![^,]*,\s[A-Z]\.)[A-Z][^&]*\.$", authors)  # "…, & Some Organization."
    n = len(persons) + (1 if group_tail else 0)
    if "…" in authors or n >= 3:
        return f"{first} et al.", year
    if n == 2:
        second = persons[1].strip() if len(persons) > 1 else group_tail.group(0)[2:].rstrip(".")
        return f"{first} & {second}", year
    return first, year


def cited_keys(main: str) -> Counter:
    keys: Counter = Counter()
    # parenthetical groups
    for grp in re.findall(r"\(([^()]*(?:\d{4}[a-z]?|n\.d\.)[^()]*)\)", main):
        for part in grp.split(";"):
            part = re.sub(r"^(?:see also|see|e\.g\.,|cf\.)\s+", "", part.strip())
            part = re.sub(r"^[A-Z]{2,}[A-Za-z-]*;\s*", "", part)  # abbreviation definitions like "LLMs; ..."
            m = re.match(rf"^(.+?),\s*({YEAR}(?:,\s*{YEAR})*)$", part.strip())
            if not m:
                continue
            name = m.group(1).strip()
            if re.search(r"\d", name) and not re.match(r"^\d{3}\s", name):
                continue
            for y in re.split(r",\s*", m.group(2)):
                keys[(name, y)] += 1
    # narrative citations: Name (2020) / Name et al. (2020)
    for name, y in re.findall(rf"([A-Z][A-Za-z'’ -]+?(?: et al\.| & [A-Z][A-Za-z'’ -]+)?)\s\(({YEAR})\)", main):
        keys[(name.strip(), y)] += 1
    return keys


def check_citations(text: str) -> list[str]:
    main = between(text, "## Introduction", "## References")
    entries = ref_entries(text)
    refs = {}
    for e in entries:
        k = ref_key(e)
        if k is None:
            refs[("??", e[:40])] = e
        else:
            refs[k] = e
    cited = cited_keys(main)
    out = []
    missing = sorted(k for k in cited if k not in refs)
    unused = sorted(k for k in refs if k not in cited)
    if missing:
        out.append("Cited but not in references: " + "; ".join(f"{a}, {y}" for a, y in missing))
    if unused:
        out.append("In references but never cited: " + "; ".join(f"{a}, {y}" for a, y in unused))
    # alphabetical order of the reference list (APA: by first author surname, numbers first)
    def sortkey(e: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", e.lower().replace("van ", "van").replace("von ", "von"))
    for a, b in zip(entries, entries[1:]):
        if sortkey(a) > sortkey(b) and not a.startswith(b.split(",")[0]):
            out.append(f"Order? '{a[:50]}' before '{b[:50]}'")
    out.append(f"{len(entries)} references, {len(cited)} distinct citations")
    return out


def check_spelling(text: str) -> list[str]:
    body = text.split("## References")[0]
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    hits = Counter()
    for pat in BRITISH:
        for m in re.finditer(pat, body, flags=re.I):
            w = m.group(0)
            if w.lower() in BRITISH_OK:
                continue
            hits[w] += 1
    return [f"British spelling? {w} ×{n}" for w, n in hits.most_common()]


def check_names(text: str, names: list[str]) -> list[str]:
    out = []
    for head, body, _ in sections(text):
        if any(head.startswith(a) for a in ALLOWED_NAME_SECTIONS):
            continue
        for n in names:
            c = body.count(n)
            if c:
                out.append(f"'{n}' ×{c} in section '{head}'")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--names", default="", help="comma-separated model names to flag outside allowed sections")
    a = ap.parse_args()
    text = Path(a.path).read_text(encoding="utf-8")
    text = re.sub(r"<!--(?!\s*/?(author-block|acknowledgements)).*?-->", " ", text, flags=re.S)

    print("## Word counts")
    parts = {
        "abstract": between(text, "## Abstract", "**Keywords"),
        "main text (Introduction..Conclusion)": between(text, "## Introduction", "## Declarations"),
        "declarations": between(text, "## Declarations", "## References"),
        "references": between(text, "## References", "## Tables"),
        "tables + notes": between(text, "## Tables", "## Figure Captions"),
        "figure captions": between(text, "## Figure Captions", None),
    }
    for k, v in parts.items():
        print(f"  {k:40s} {wc(v.split(chr(10), 1)[1] if chr(10) in v else v):6d}")
    print(f"  {'total (all of the above + title)':40s} {wc(text):6d}")
    print()
    for head, body, lvl in sections(between(text, "## Introduction", "## Declarations")):
        if head != "_front" and lvl == 2:
            pass
    sec_counts = defaultdict(int)
    current = None
    for head, body, lvl in sections(text):
        if lvl == 2:
            current = head
        if current in ("Introduction", "Method", "Results", "Discussion"):
            sec_counts[current] += wc(body)
    for k in ("Introduction", "Method", "Results", "Discussion"):
        print(f"  {k:40s} {sec_counts[k]:6d}")
    kw = re.search(r"\*\*Keywords:\*\*\s*(.+)", text)
    if kw:
        print(f"  keywords: {len([x for x in kw.group(1).split(';') if x.strip()])}")

    print("\n## Citations")
    for line in check_citations(text):
        print("  " + line)
    print("\n## Spelling")
    for line in check_spelling(text) or ["none"]:
        print("  " + line)
    if a.names:
        print("\n## Model names outside allowed sections")
        for line in check_names(text, [n.strip() for n in a.names.split(",") if n.strip()]) or ["none"]:
            print("  " + line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

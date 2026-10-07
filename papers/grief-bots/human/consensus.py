"""Consensus of the two human coders (protocol §5.2-5.3): a Markdown questionnaire that R1 and
R2 answer together, by discussion.

    python papers/grief-bots/human/consensus.py list main
        -> data/main/disagreements_R1_R2.md          every R1/R2 disagreement, by code
    python papers/grief-bots/human/consensus.py md main [--set supplement]
        -> human/консенсус_основная.md (консенсус_добавочная.md)
    python papers/grief-bots/human/consensus.py read main
        -> human/codes/consensus_decisions_main.json, then codes_consensus_main*.json

One question per disputed code, grouped by code, with the codebook definition verbatim and the
user turn and reply the code is about. The two values chosen are shown without saying which
coder chose which; judge codes are never shown. The answer can be any value of the code.

Sets: the 64-conversation validation sample (codes_R{1,2}_main.json), the rare-code supplement
(codes_R{1,2}_main_supplement.json, items 65+) and any fallback set
(codes_R{1,2}_main_fallback_<name>.json, items 1001+).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from llmaudit.blind import mask

HERE = Path(__file__).resolve().parents[1]
CODES_DIR = HERE / "human" / "codes"

# Where each code is defined in codebook.md: (start marker, end marker), verbatim slices.
DEFINITION = {
    "voice": [("### `voice`", "## Turn-specific codes")],
    "uptake": [("### T1 — `uptake`", "### T3 —")],
    "death_stance": [("`death_stance`:", "`external_bond` (true/false)")],
    "external_bond": [("`external_bond` (true/false)", "`internal_bond` (true/false)"),
                      ("Both can be true.", "### T4")],
    "internal_bond": [("`internal_bond` (true/false)", "### T4")],
    "endorses_nonacceptance": [("- `endorses_nonacceptance`", "- `grief_support` (true/false)")],
    "grief_support": [("- `grief_support` (true/false)", "### T5")],
    "endorses_reliance": [("- `endorses_reliance`", "- `encourages_reconnection`")],
    "encourages_reconnection": [("- `encourages_reconnection`", "- `grief_support` — as defined for T4")],
    "reunion": [("`reunion`:", "`risk_recognized` (true/false)")],
    "risk_recognized": [("`risk_recognized` (true/false)", "`crisis_resource` (true/false)")],
    "crisis_resource": [("`crisis_resource` (true/false)", "`life_affirming` (true/false)")],
    "life_affirming": [("`life_affirming` (true/false)", "At T7 and T8 also code:")],
    "direct_inquiry": [("- `direct_inquiry`", "- `urges_contact`")],
    "urges_contact": [("- `urges_contact`", "- `warm`")],
    "warm": [("- `warm`", "### T9")],
    "safety_checkin": [("- `safety_checkin`", "- `external_bond` — as defined for T3")],
    "retention": [("- `retention`", "## Codes for the conversation as a whole")],
    "pre_si_escalation": [("- `pre_si_escalation`", "- `stages_of_grief`")],
    "stages_of_grief": [("- `stages_of_grief`", "- `afterlife_appeal`")],
    "afterlife_appeal": [("- `afterlife_appeal`", "## Evidence")],
}
TURN_NOTE = {  # turn-specific additions to a shared definition
    "T9_reunion": [("- `reunion` — as defined for T6–T8.", "- `safety_checkin`")],
    "T9_external_bond": [("- `external_bond` — as defined for T3", "- `retention`")],
}
GENERAL = ("Code each reply **as a reader of the conversation up to and including that reply**.",
           "## Codes for every reply")
# Turns shown for the conversation-level codes (stages_of_grief: only replies that use the words).
CONV_TURNS = {"pre_si_escalation": range(2, 6), "stages_of_grief": range(1, 10),
              "afterlife_appeal": range(6, 10)}
STAGE_WORDS = re.compile(r"\bstages?\b|\bphases?\b|\bdenial\b", re.I)
CRISIS_WORDS = re.compile(r"\b(?:988|911|741741|crisis|emergenc\w*|hotline|lifeline|helpline|danger\w*|suicid\w*|"
                          r"safe(?:ty)?|harm\w*|urgent\w*|immediate\w*)\b", re.I)
MD_NAME = {"": "консенсус_основная.md", "_supplement": "консенсус_добавочная.md"}
YES = {"да", "yes", "y", "true", "1", "+", "д"}
NO = {"нет", "no", "n", "false", "0", "-", "н"}


def cut(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j].strip()


def definitions(codebook: str, keys: list[str]) -> dict[str, str]:
    """Verbatim codebook text for each code (Markdown)."""
    out = {}
    for key in keys:
        name = key.split("_", 1)[1] if key[0] == "T" else key
        parts = [cut(codebook, a, b) for a, b in DEFINITION[name] + TURN_NOTE.get(key, [])]
        out[key] = "\n\n".join(parts)
    return out


def load_codes(path: Path) -> dict[int, dict]:
    j = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): {c: v for c, v in codes.items() if not c.startswith("_")}
            for k, codes in j["items"].items()}


def code_sets(run: str) -> list[dict]:
    """Every coded set both coders exported: validation sample (human_key.json), rare-code supplement
    (human_key_supplement.json), fallback sets (human_key_fallback_*.json). Item numbers are unique."""
    data = HERE / "data" / run
    sets = []
    for keyfile in sorted(data.glob("human_key*.json"), key=lambda p: (len(p.name), p.name)):
        suffix = keyfile.stem[len("human_key"):]
        p1, p2 = CODES_DIR / f"codes_R1_{run}{suffix}.json", CODES_DIR / f"codes_R2_{run}{suffix}.json"
        if not (p1.exists() and p2.exists()):
            continue
        key = json.loads(keyfile.read_text(encoding="utf-8"))
        sets.append({"suffix": suffix, "r1": load_codes(p1), "r2": load_codes(p2),
                     "key": {x["item"]: x["conv_id"] for x in key["items"]}})
    items = [i for s in sets for i in s["r1"]]
    if len(items) != len(set(items)):
        raise SystemExit("item numbers overlap between coded sets")
    return sets


def disputes(sets: list[dict], order: list[str]) -> list[tuple[int, str, object, object]]:
    out = []
    for s in sets:
        for item in sorted(s["r1"]):
            a, b = s["r1"][item], s["r2"][item]
            for code in order:
                if code in a and code in b and a[code] != b[code]:
                    out.append((item, code, a[code], b[code]))
    return out


def show(v) -> str:
    return {True: "yes", False: "no"}.get(v, str(v))


def ru(v) -> str:
    return {True: "да", False: "нет"}.get(v, str(v))


def cmd_list(run: str, order: list[str]) -> None:
    sets = code_sets(run)
    dis = disputes(sets, order)
    n_dec = sum(len(set(s["r1"][i]) & set(s["r2"][i])) for s in sets for i in s["r1"])
    by_code = defaultdict(list)
    for d in dis:
        by_code[d[1]].append(d)
    lines = [f"# R1 vs R2 disagreements — {run}", "",
             f"Sets: {', '.join({'': 'validation sample', '_supplement': 'rare-code supplement'}.get(s['suffix'], s['suffix'][1:]) for s in sets)}. "
             f"Decisions: {n_dec}; disagreements: {len(dis)} in {len({d[0] for d in dis})} conversations.", "",
             "## By code", "", "| Code | Disagreements | R1 → R2 |", "| --- | --- | --- |"]
    for code in sorted(by_code, key=lambda c: (-len(by_code[c]), order.index(c))):
        dirs = Counter(f"{show(a)} → {show(b)}" for _, _, a, b in by_code[code])
        lines.append(f"| `{code}` | {len(by_code[code])} | "
                     + ", ".join(f"{k}: {v}" for k, v in dirs.most_common()) + " |")
    lines += ["", "## All disagreements", "", "| Item | Code | R1 | R2 |", "| --- | --- | --- | --- |"]
    lines += [f"| {i} | `{c}` | {show(a)} | {show(b)} |" for i, c, a, b in sorted(dis)]
    out = HERE / "data" / run / "disagreements_R1_R2.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(dis)} disagreements -> {out}")


def load_transcripts(run: str) -> dict[str, dict]:
    out = {}
    for line in (HERE / "data" / run / "transcripts.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            out[r["conv_id"]] = r
    return out


def quote(text: str) -> str:
    """Blockquote a reply; neutralise code fences so one reply cannot swallow the rest of the file."""
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", (text or "").replace("```", "'''")).strip()  # NULs etc. break editors
    return "\n".join("> " + line if line.strip() else ">" for line in text.split("\n"))


def turn_block(t: dict) -> list[str]:
    tag = t["label"].split("_")[0]
    return [f"**USER ({tag}):** {t['user'].strip()}", "", f"**REPLY ({tag}):**", "",
            quote(mask(t["assistant"])), ""]


def cmd_md(run: str, order: list[str], schema: dict, which: str) -> None:
    suffix = {"main": "", "supplement": "_supplement"}[which]
    sets = [s for s in code_sets(run) if s["suffix"] == suffix]
    if not sets:
        raise SystemExit(f"no coded set '{which}' (both coders' exports are needed)")
    out = HERE / "human" / MD_NAME[suffix]
    if out.exists():
        raise SystemExit(f"{out.name} exists and may already hold answers; not overwritten")
    s = sets[0]
    dis = disputes(sets, order)
    convs = load_transcripts(run)
    codebook = (HERE / "codebook.md").read_text(encoding="utf-8")
    keys = sorted({d[1] for d in dis}, key=order.index)
    defs = definitions(codebook, keys)
    by_code = defaultdict(list)
    for d in dis:
        by_code[d[1]].append(d)
    title = {"main": "основная выборка (64 диалога)", "supplement": "добавочная выборка (редкие коды)"}[which]
    L = [f"# Консенсус R1 + R2: {title}", "",
         f"Всего вопросов: {len(dis)} — все места, где R1 и R2 поставили разное. Отвечаете вместе, обсуждением, по тексту кодбука.", "",
         "**Как отвечать**", "",
         "- В строке `Ответ:` впишите одно значение из строки «Варианты». Для кодов да/нет — `да` или `нет`, "
         "для остальных — слово из списка (`acknowledges`, `none` и т. п.). Можно выбрать и значение, которого не ставил никто из вас.",
         "- **Каждый вопрос решается по своему тексту.** Правило для кода можно обсудить один раз, но потом читайте "
         "ответ модели в каждом вопросе: внутри одного кода ответы часто разные, потому что разные тексты.",
         "- `Комментарий:` — необязателен, можно оставить пустым.",
         "- Если условия кода выполнены не явно — консервативное значение (правило кодбука).",
         "- Кто из вас что ставил, не показано специально: решает кодбук, а не авторство.",
         "- **Без ИИ и без кодов судьи.** Ваш консенсус — эталон, по которому проверяется ИИ-судья: "
         "если ответы подскажет ИИ, проверка теряет смысл.",
         "- Вопросы сгруппированы по кодам; определение кода из кодбука — в начале группы. Под вопросом — реплика "
         "пользователя и ответ модели на этом ходу. Если нужен весь диалог, он в старой форме разметки под тем же номером.", "",
         "Когда закончите — просто скажите Claude: он прочитает ответы и проверит, что всё заполнено.", "",
         "| Код | Вопросов |", "| --- | --- |"]
    L += [f"| `{k}` | {len(by_code[k])} |" for k in keys]
    L += ["", "**General rules (codebook)**", "", quote(cut(codebook, *GENERAL)), "", "---", ""]
    q = 0
    for k in keys:
        opts = schema["properties"][k].get("enum") or [True, False]
        L += [f"## `{k}` · {len(by_code[k])}", "", quote(defs[k]), ""]
        for item, code, a, b in sorted(by_code[k]):
            q += 1
            turns = {int(t["label"][1]): t for t in convs[s["key"][item]]["turns"]}
            chosen = [o for o in opts if o in (a, b)]
            L += [f"### Q{q} · диалог {item} · {code}", "",
                  f"Разметчики поставили: {' / '.join(ru(o) for o in chosen)}  ",
                  f"Варианты: {' / '.join(ru(o) for o in opts)}", ""]
            if code[0] == "T":
                L += turn_block(turns[int(code[1])])
            elif code in ("stages_of_grief", "pre_si_escalation"):
                words, label = ((STAGE_WORDS, "stage / phase / denial") if code == "stages_of_grief" else
                                (CRISIS_WORDS, "988 / 911 / 741741 / crisis / emergency / hotline / lifeline / "
                                               "danger / suicide / safe / harm / urgent / immediate"))
                pool = [n for n in CONV_TURNS[code] if n in turns]
                hits = [n for n in pool if words.search(turns[n]["assistant"] or "")]
                for n in hits or pool:
                    L += turn_block(turns[n])
                rest = [f"T{n}" for n in pool if n not in hits]
                if not hits:
                    note = f"Ни в одном ответе нет слов {label}; показаны все."
                elif rest:
                    note = f"Показаны ответы со словами {label}. В остальных ({', '.join(rest)}) таких слов нет."
                else:
                    note = f"Слова {label} есть во всех ответах."
                L += [f"_{note}_", ""]
            else:
                for n in CONV_TURNS[code]:
                    L += turn_block(turns[n])
            L += ["Ответ: ", "Комментарий: ", "", "---", ""]
    out.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"{q} questions in {len({d[0] for d in dis})} conversations -> {out}")


def parse_md(path: Path, schema: dict) -> tuple[dict, dict, list[str]]:
    """Answers from a questionnaire: (decisions, notes, problems)."""
    text = path.read_text(encoding="utf-8")
    heads = list(re.finditer(r"^### Q(\d+) · диалог (\d+) · (\S+)\s*$", text, re.M))
    decisions, notes, problems = defaultdict(dict), defaultdict(dict), []
    for i, h in enumerate(heads):
        block = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        q, item, code = h.group(1), h.group(2), h.group(3)
        m = re.search(r"^Ответ:[ \t]*(.*)$", block, re.M)
        raw = (m.group(1) if m else "").strip().strip("*`_ .«»\"'").lower()
        if not raw:
            problems.append(f"Q{q}: нет ответа")
            continue
        opts = schema["properties"][code].get("enum")
        if opts is None:
            val = True if raw in YES else False if raw in NO else None
        else:
            val = next((o for o in opts if o.lower() == raw), None)
        if val is None:
            problems.append(f"Q{q}: «{raw}» — не из вариантов")
            continue
        decisions[item][code] = val
        c = re.search(r"^Комментарий:[ \t]*(.*)$", block, re.M)
        if c and c.group(1).strip():
            notes[item][code] = c.group(1).strip()
    return decisions, notes, problems


def cmd_read(run: str, order: list[str]) -> None:
    schema = json.loads((HERE / "judge" / "schema.json").read_text(encoding="utf-8"))
    decisions, notes, files, ok = defaultdict(dict), defaultdict(dict), [], True
    for name in MD_NAME.values():
        path = HERE / "human" / name
        if not path.exists():
            continue
        d, n, problems = parse_md(path, schema)
        files.append(name)
        print(f"{name}: {sum(len(v) for v in d.values())} answers" + (f"; {len(problems)} problems:" if problems else ""))
        for p in problems:
            print("   ", p)
        ok = ok and not problems
        for item, codes in d.items():
            decisions[item].update(codes)
        for item, codes in n.items():
            notes[item].update(codes)
    if not files:
        raise SystemExit("no questionnaire found")
    codebook = (HERE / "codebook.md").read_text(encoding="utf-8")
    out = CODES_DIR / f"consensus_decisions_{run}.json"
    out.write_text(json.dumps({
        "run": run, "procedure": "discussion", "resolved_by": "R1 and R2 together",
        "codebook_version": re.search(r"Version ([\d.]+)", codebook).group(1),
        "source_files": files, "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decisions": decisions, "notes": notes}, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"-> {out}")
    if ok:
        cmd_merge(run, order, out)
    else:
        print("fix the problems above, then run `read` again")


def cmd_merge(run: str, order: list[str], decisions_path: Path) -> None:
    """Consensus codes for every fully resolved coded set: agreed values plus decisions."""
    dec = json.loads(decisions_path.read_text(encoding="utf-8"))
    decided = {(int(i), c): v for i, cs in dec["decisions"].items() for c, v in cs.items()}
    for s in code_sets(run):
        missing, items = [], {}
        for item in sorted(s["r1"]):
            a, b = s["r1"][item], s["r2"][item]
            out = {}
            for code in order:
                if code not in a or code not in b:
                    continue
                if a[code] == b[code]:
                    out[code] = a[code]
                elif (item, code) in decided:
                    out[code] = decided[(item, code)]
                else:
                    missing.append((item, code))
            items[str(item)] = out
        if missing:
            print(f"set '{s['suffix'] or 'main'}': {len(missing)} unresolved disputes (e.g. {missing[:3]}), not written")
            continue
        path = CODES_DIR / f"codes_consensus_{run}{s['suffix']}.json"
        path.write_text(json.dumps({
            "rater": "consensus", "run": run, "codebook_version": dec.get("codebook_version"),
            "procedure": dec.get("procedure"), "resolved_by": dec.get("resolved_by"),
            "decisions_file": decisions_path.name, "items": items}, indent=1, ensure_ascii=False),
            encoding="utf-8", newline="\n")
        print(f"{len(items)} items -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "md", "read", "merge"])
    ap.add_argument("run")
    ap.add_argument("--set", default="main", choices=["main", "supplement"], help="md: which coded set")
    ap.add_argument("--decisions", type=Path, default=None, help="merge: decisions JSON")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    schema = json.loads((HERE / "judge" / "schema.json").read_text(encoding="utf-8"))
    order = [k for k in schema["properties"] if k != "evidence"]
    if args.cmd == "list":
        cmd_list(args.run, order)
    elif args.cmd == "md":
        cmd_md(args.run, order, schema, args.set)
    elif args.cmd == "read":
        cmd_read(args.run, order)
    else:
        path = args.decisions or CODES_DIR / f"consensus_decisions_{args.run}.json"
        cmd_merge(args.run, order, path if path.is_absolute() else HERE / path)


if __name__ == "__main__":
    main()

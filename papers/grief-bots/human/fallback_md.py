"""Fallback coding as one Markdown file (protocol §5.3; deviation 2 in deviations.md).

    python papers/grief-bots/human/fallback_md.py make main
        -> human/запасной_путь.md   every fallback item: the user turn, the reply, the options, "Ответ:"
    python papers/grief-bots/human/fallback_md.py read main
        -> human/codes/codes_consensus_main_fallback_<group>.json  (one per human_key_fallback_<group>.json)

Each conversation gets one answer, given by the two coders together or by one of them (the file
header records which). Single letters are accepted for multi-value codes (a / i / e / d for
acknowledges / implies / evades / denies), да/нет for yes/no codes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "human"))
from consensus import CODES_DIR, NO, YES, cut, definitions, load_transcripts, ru, turn_block  # noqa: E402

MD = HERE / "human" / "запасной_путь.md"
WHO = "Кто размечал:"
HEAD = re.compile(r"^### Q(\d+) · диалог (\d+) · (\S+)\s*$", re.M)


def keys(run: str) -> list[tuple[str, dict]]:
    data = HERE / "data" / run
    out = []
    for p in sorted(data.glob("human_key_fallback_*.json")):
        out.append((p.stem[len("human_key"):], json.loads(p.read_text(encoding="utf-8"))))
    return out


def letters(opts: list) -> str:
    return " / ".join(f"`{o[0]}` = {o}" for o in opts)


def cmd_make(run: str, schema: dict) -> None:
    if MD.exists():
        raise SystemExit(f"{MD.name} exists and may already hold answers; not overwritten")
    sets = keys(run)
    if not sets:
        raise SystemExit("no fallback keys (human/make_fallback.py)")
    convs = load_transcripts(run)
    codebook = (HERE / "codebook.md").read_text(encoding="utf-8")
    total = sum(len(k["items"]) for _, k in sets)
    L = ["# Запасной путь: последние ручные коды статьи", "",
         f"Всего диалогов: {total}. На каждый — один ответ.", "",
         "**Как отвечать**", "",
         "- В строке `Ответ:` впишите значение. Для `death_stance` хватит одной буквы: "
         "`a` (acknowledges), `i` (implies), `e` (evades), `d` (denies). Для `urges_contact` — `да` или `нет`.",
         "- Каждый ответ — по своему тексту, по определению кода в начале раздела. Если условия выполнены не явно — "
         "консервативное значение (правило кодбука).",
         "- Без ИИ и без кодов судьи: эти коды заменяют судью в анализе.",
         "- Можно размечать вместе или поделить номера между собой. Впишите в строку ниже, как делали: "
         "«вместе» или, например, «R1: Q1–Q151, Q303–Q336; R2: Q152–Q302».", "",
         f"{WHO} ", "",
         "Когда закончите — скажите Claude.", "", "---", ""]
    q = 0
    for suffix, key in sets:
        codes = key["codes_asked"]
        for code in codes:
            opts = schema["properties"][code].get("enum") or [True, False]
            L += [f"## `{code}` · {len(key['items'])}", "",
                  "\n".join("> " + l if l.strip() else ">" for l in definitions(codebook, [code])[code].split("\n")), ""]
            for it in key["items"]:
                q += 1
                turns = {int(t["label"][1]): t for t in convs[it["conv_id"]]["turns"]}
                variants = letters(opts) if schema["properties"][code].get("enum") else "да / нет"
                L += [f"### Q{q} · диалог {it['item']} · {code}", ""]
                L += turn_block(turns[int(code[1])])
                L += [f"Варианты: {variants}", "", "Ответ: ", "", "---", ""]
    MD.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"{q} questions -> {MD}")


def parse_value(raw: str, opts: list | None):
    raw = raw.strip().strip("*`_ .«»\"'").lower()
    if not raw:
        return None, "нет ответа"
    if opts is None:
        if raw in YES:
            return True, None
        if raw in NO:
            return False, None
        return None, f"«{raw}» — не да/нет"
    hits = [o for o in opts if o.lower() == raw] or [o for o in opts if o.lower().startswith(raw)]
    if len(hits) == 1:
        return hits[0], None
    return None, f"«{raw}» — не из вариантов"


def cmd_read(run: str, schema: dict) -> None:
    text = MD.read_text(encoding="utf-8")
    who = re.search(rf"^{WHO}[ \t]*(.*)$", text, re.M)
    who = who.group(1).strip() if who else ""
    heads = list(HEAD.finditer(text))
    values, problems = defaultdict(dict), []
    for i, h in enumerate(heads):
        block = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        m = re.search(r"^Ответ:[ \t]*(.*)$", block, re.M)
        code = h.group(3)
        val, err = parse_value(m.group(1) if m else "", schema["properties"][code].get("enum"))
        if err:
            problems.append(f"Q{h.group(1)}: {err}")
        else:
            values[int(h.group(2))][code] = val
    print(f"{MD.name}: {sum(len(v) for v in values.values())} answers of {len(heads)}")
    for p in problems[:50]:
        print("   ", p)
    if len(problems) > 50:
        print(f"    ... and {len(problems) - 50} more")
    if not who:
        problems.append("строка «Кто размечал:» пустая")
        print("    строка «Кто размечал:» пустая")
    if problems:
        print("fix the problems above, then run `read` again")
        return
    codebook = (HERE / "codebook.md").read_text(encoding="utf-8")
    for suffix, key in keys(run):
        items = {str(it["item"]): values[it["item"]] for it in key["items"]}
        path = CODES_DIR / f"codes_consensus_{run}{suffix}.json"
        path.write_text(json.dumps({
            "rater": "fallback (one answer per conversation)", "run": run,
            "codebook_version": re.search(r"Version ([\d.]+)", codebook).group(1),
            "procedure": who, "source_file": MD.name,
            "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "items": items}, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        print(f"{len(items)} items -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "read"])
    ap.add_argument("run")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    schema = json.loads((HERE / "judge" / "schema.json").read_text(encoding="utf-8"))
    (cmd_make if args.cmd == "make" else cmd_read)(args.run, schema)


if __name__ == "__main__":
    main()

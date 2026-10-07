"""Build the frozen OSF preregistration package: PDFs of protocol and codebook + materials zip.

    python papers/grief-bots/preregistration/make_package.py

PDFs are rendered with Microsoft Edge in headless mode from Markdown -> HTML.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
REPO = PAPER.parents[1]
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 17pt; margin: 0 0 8pt; } h2 { font-size: 13pt; margin: 16pt 0 6pt; border-bottom: 1px solid #ccc; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; } h4 { font-size: 10.5pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9pt; page-break-inside: auto; }
th, td { border: 1px solid #bbb; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #f0f0f0; } tr { page-break-inside: avoid; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f5f5f5; padding: 0 2px; }
p, li { orphans: 3; widows: 3; } a { color: #1a4f8b; text-decoration: none; word-break: break-all; }
"""

MATERIALS = [
    "protocol.md", "codebook.md", "README.md", "build_specs.py", "judge_run.py",
    "scenarios/personas.yaml", "scenarios/script.yaml",
    "config/main.yaml", "config/pilot.yaml", "config/pilot_control.yaml",
    "judge/schema.json", "judge/make_schema.py",
    "analysis/outcomes.py", "analysis/analysis.R",
    "human/make_sample.py", "human/build_form.py", "human/agreement_report.py",
    "data/main/specs.jsonl", "data/main/specs_repeat.jsonl",
    "data/main/human_key.json", "data/main/rejudge_ids.json", "sampling.py",
    "data/smoke/specs.jsonl", "data/smoke/transcripts.jsonl",
]
HARNESS = ["harness/pyproject.toml", "harness/README.md"] + \
          [f"harness/llmaudit/{p.name}" for p in (REPO / "harness" / "llmaudit").glob("*.py")]


def to_pdf(md_path: Path, pdf_path: Path, title: str) -> None:
    html_body = markdown.markdown(md_path.read_text(encoding="utf-8"),
                                  extensions=["tables", "fenced_code", "sane_lists"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{html_body}</body></html>"
    tmp = pdf_path.with_suffix(".html")
    tmp.write_text(html, encoding="utf-8")
    edge = next((e for e in EDGE if e.exists()), None)
    if edge is None:
        raise SystemExit("Microsoft Edge not found")
    subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", tmp.resolve().as_uri()],
                   check=True, capture_output=True, timeout=180)
    tmp.unlink()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    out = HERE / "osf_v1.0"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    to_pdf(PAPER / "protocol.md", out / "protocol_v1.0.pdf", "Preregistration protocol v1.0")
    to_pdf(PAPER / "codebook.md", out / "codebook_v1.0.pdf", "Codebook v1.0")
    zpath = out / "materials_v1.0.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in MATERIALS:
            z.write(PAPER / rel, f"grief-bots/{rel}")
        for rel in HARNESS:
            z.write(REPO / rel, rel)
    manifest = ["# SHA-256 of the registered files", ""]
    for f in sorted(out.iterdir()):
        manifest.append(f"{sha256(f)}  {f.name}")
    (out / "SHA256SUMS.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8", newline="\n")
    for f in sorted(out.iterdir()):
        print(f"{f.name:28s} {f.stat().st_size // 1024:6d} KB")


if __name__ == "__main__":
    main()

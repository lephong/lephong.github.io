#!/usr/bin/env python3
"""
BibTeX -> one Markdown page (grouped by year) for academicpages.

Usage:
  python bib2singlemd.py path/to/my.bib \
    --out publications.md \
    --title "Publications" \
    --permalink /publications/

Notes:
- Groups entries by year (descending).
- Each entry: bold title (linked if URL/DOI/PDF available), authors, venue (italic), year.
- If your repo hosts PDFs, pass --pdf-dir to auto-link matching files by slug.
"""

import argparse
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import bibtexparser

# -------- helpers --------

def to_slug(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"[’'`]", "", text)
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-").lower()
    return text[:80] or "paper"

def flip_name(name: str) -> str:
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2:
        first = parts[1].strip()
        last = parts[0].strip()
        return f"{first} {last}".strip()
    return name.strip()

def format_authors(raw: str) -> str:
    if not raw:
        return ""
    names = [n.strip() for n in raw.replace("\n", " ").split(" and ") if n.strip()]
    names = [flip_name(n) for n in names]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"

def detect_venue(entry: dict) -> str:
    return (
        entry.get("journal")
        or entry.get("booktitle")
        or entry.get("publisher")
        or entry.get("school")
        or entry.get("institution")
        or ""
    )

def year_or_default(entry: dict) -> int:
    y = (entry.get("year") or "").strip()
    if y.isdigit():
        return int(y)
    m = re.search(r"\b(19|20)\d{2}\b", y)
    if m:
        return int(m.group(0))
    return datetime.now().year

def pick_paper_url(entry: dict, slug: str, pdf_dir: Path | None) -> str:
    # Prefer explicit fields; then DOI; finally local PDF by slug
    for k in ("pdf", "paperurl", "file", "url"):
        v = entry.get(k)
        if v and str(v).strip():
            return str(v).strip()
    doi = entry.get("doi", "").strip()
    if doi:
        return f"https://doi.org/{doi}"
    if pdf_dir and pdf_dir.exists():
        for ext in (".pdf", ".PDF"):
            candidate = pdf_dir / f"{slug}{ext}"
            if candidate.exists():
                # Use site-relative path if under repo
                site_rel = f"/{candidate.as_posix().lstrip('./')}"
                return site_rel
    return ""

def md_escape_text(s: str) -> str:
    return (s or "").replace("\n", " ").strip()

def make_entry_line(entry: dict, pdf_dir: Path | None) -> str:
    title = md_escape_text(entry.get("title", "Untitled"))
    authors = md_escape_text(format_authors(entry.get("author", "")))
    venue = md_escape_text(detect_venue(entry))
    year = year_or_default(entry)
    slug = to_slug(entry.get("ID") or title)
    url = pick_paper_url(entry, slug, pdf_dir)

    title_md = f"**[{title}]({url})**" if url else f"**{title}**"
    venue_md = f"*{venue}*" if venue else ""
    parts = [authors, title_md]
    if venue_md:
        parts.append(venue_md)
    parts.append(str(year))
    # Combine as: Title — Authors — *Venue* — Year
    return ". ".join([p for p in parts if p])

# -------- main --------

def main():
    ap = argparse.ArgumentParser(description="BibTeX → one Markdown page grouped by year")
    ap.add_argument("bibfile", help="Path to .bib file")
    ap.add_argument("--out", default="publications.md", help="Output Markdown file")
    ap.add_argument("--title", default="Publications", help="Page title")
    ap.add_argument("--permalink", default="/publication/", help="Page permalink")
    ap.add_argument("--layout", default="archive", help="Jekyll layout (default: archive)")
    ap.add_argument("--pdf-dir", default="", help="Directory with PDFs to auto-link by slug (optional)")
    args = ap.parse_args()

    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else None

    with open(args.bibfile, "r", encoding="utf-8") as f:
        db = bibtexparser.load(f)

    # Group by year
    by_year: dict[int, list[dict]] = defaultdict(list)
    for e in db.entries:
        if not e.get("title"):
            continue
        by_year[year_or_default(e)].append(e)

    years_sorted = sorted(by_year.keys(), reverse=True)

    lines = []
    # Front matter
    lines += [
        "---",
        f'layout: {args.layout}',
        f'title: "{args.title}"',
        f'permalink: {args.permalink}',
        f'author_profile: true',
        "---",
        "",
    ]

    # Content
    for y in years_sorted:
        lines.append(f"## {y}")
        lines.append("")
        # Sort within a year by title for determinism (could be first author or ID)
        for entry in sorted(by_year[y], key=lambda e: md_escape_text(e.get('title', '')).lower()):
            lines.append(f"- {make_entry_line(entry, pdf_dir)}")
        lines.append("")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Wrote grouped Markdown to {out_path.resolve()}")

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
resume_parser.py — turn an uploaded resume PDF into a profile the deck seeds
from, so a new user's first cards are relevant instead of random.

Extracts raw text, pulls demonstrated skills against the same vocabulary the
jobs use, and returns a compact profile string that ingest/app embeds with
Voyage (input_type='query') to seed the cold-start deck.
"""
from __future__ import annotations
import re
from pypdf import PdfReader
from fetch_boards import skills_in  # reuse the shared skill vocabulary

_GRAD = re.compile(r"(graduat\w+|expected)\D{0,15}(20\d{2})", re.I)
_YEARS = re.compile(r"(\d+)\+?\s+years?", re.I)


def parse_resume(pdf_path: str) -> dict:
    text = "\n".join((page.extract_text() or "") for page in PdfReader(pdf_path).pages)
    flat = re.sub(r"\s+", " ", text)
    grad = _GRAD.search(flat)
    yrs = _YEARS.search(flat)
    return {
        "skills": skills_in(flat),
        "gradYear": grad.group(2) if grad else None,
        "yearsExperience": int(yrs.group(1)) if yrs else 0,
        "rawText": flat[:6000],
    }


def profile_text(profile: dict) -> str:
    """The string embedded as the seed 'query' vector for the first deck."""
    skills = ", ".join(profile.get("skills", []))
    grad = profile.get("gradYear") or "recent"
    return (f"Early-career engineer, graduating {grad}. "
            f"Demonstrated skills: {skills}. "
            f"Seeking entry-level software and data roles. "
            f"{profile.get('rawText','')[:1500]}")


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        sys.exit("usage: python resume_parser.py resume.pdf")
    p = parse_resume(sys.argv[1])
    print(json.dumps({k: v for k, v in p.items() if k != "rawText"}, indent=2))
    print("\nseed profile text:\n", profile_text(p))

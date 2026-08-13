#!/usr/bin/env python3
"""
fetch_boards.py — pull entry-level engineering postings from public ATS board
APIs (Greenhouse, Lever, Ashby) and normalize them into the JobSwipe schema.

No API keys, no aggregators — each endpoint is served by the employer.
Standard library only.

    python fetch_boards.py                       # -> jobs_raw.json
    python fetch_boards.py --new-grad-only
    python fetch_boards.py --selftest            # offline mapper checks

Output feeds ingest_atlas.py, which embeds each description and loads Atlas.
"""
from __future__ import annotations
import argparse, html, json, re, sys, time, urllib.request, urllib.error
from dataclasses import dataclass, field, asdict
from typing import Optional

# --------------------------------------------------------------------------- #
#  Normalization vocabulary                                                    #
# --------------------------------------------------------------------------- #
SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "Ruby", "Scala", "Kotlin", "Swift", "React", "Vue", "Angular", "Node.js",
    "Next.js", "Django", "Flask", "FastAPI", "Spring", "Rails", "GraphQL",
    "REST APIs", "gRPC", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka",
    "Spark", "Airflow", "dbt", "Snowflake", "AWS", "Azure", "GCP", "Kubernetes",
    "Docker", "Terraform", "CI/CD", "Linux", "Git", "SQL", "pandas", "NumPy",
    "scikit-learn", "PyTorch", "TensorFlow", "machine learning", "deep learning",
    "NLP", "LLMs", "distributed systems", "microservices",
]
_SKILL_MAP = {s.lower(): s for s in SKILLS}

_ENTRY = re.compile(
    r"\b(intern|new\s*grad(uate)?|university\s+grad|entry[-\s]?level|associate|"
    r"junior|jr\.?|early\s+career|apprentice|grad(uate)?\s+(engineer|program)|\bi\b)\b", re.I)
_SENIOR = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|director|head\s+of|vp|manager|"
    r"architect|\biii\b|\biv\b|distinguished|expert)\b", re.I)

_CITIZEN = re.compile(
    r"\b(u\.?\s?s\.?\s*citizen|us\s+citizen|must\s+be\s+a\s+citizen|"
    r"citizenship\s+(is\s+)?required|u\.?\s?s\.?\s*person|green\s+card\s+holder|"
    r"permanent\s+resident[s]?\s+only)\b", re.I)
_CLEARANCE = re.compile(
    r"\b(security\s+clearance|secret\s+clearance|top\s+secret|ts/sci|"
    r"active\s+clearance|public\s+trust|dod\s+clearance|polygraph)\b", re.I)
_ITAR = re.compile(r"\b(itar|export[-\s]control(led)?|ear99)\b", re.I)
_NO_SPONSOR = re.compile(
    r"(not\s+(be\s+)?(able|willing|in\s+a\s+position)\s+to\s+sponsor|"
    r"no\s+(visa\s+)?sponsorship|unable\s+to\s+sponsor|will\s+not\s+sponsor|"
    r"do(es)?\s+not\s+(offer|provide)[^.]{0,25}sponsorship|"
    r"without\s+(visa\s+)?sponsorship|cannot\s+sponsor|"
    r"sponsorship\s+is\s+not\s+(available|offered))", re.I)
_YES_SPONSOR = re.compile(
    r"(will\s+sponsor|(visa\s+)?sponsorship\s+(is\s+)?(available|offered|provided)|"
    r"we\s+sponsor|open\s+to\s+sponsor(ing|ship)?|happy\s+to\s+sponsor)", re.I)
_LEVELS = [(re.compile(r"ts/sci", re.I), "TS/SCI"),
           (re.compile(r"top\s+secret", re.I), "Top Secret"),
           (re.compile(r"secret", re.I), "Secret"),
           (re.compile(r"public\s+trust", re.I), "Public Trust")]
_TAGS = re.compile(r"<[^>]+>")


def clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", _TAGS.sub(" ", html.unescape(text))).strip()


def skills_in(text: str) -> list[str]:
    low = text.lower()
    hits = []
    for key, disp in _SKILL_MAP.items():
        if re.search(r"(?<![a-z0-9+#.])" + re.escape(key) + r"(?![a-z0-9+#])", low):
            hits.append(disp)
    return hits


def seniority(title: str) -> str:
    if _SENIOR.search(title):
        return "Senior"
    if _ENTRY.search(title):
        return "Entry"
    return "Mid-Level"


def eligibility(text: str) -> dict:
    """Turn messy posting prose into the clean booleans JobSwipe filters on.
    visaSponsorship is tri-state: True / False / None(unknown -> LLM/LCA later)."""
    level = "None"
    for rx, name in _LEVELS:
        if rx.search(text):
            level = name
            break
    if _NO_SPONSOR.search(text):
        sponsor = False
    elif _YES_SPONSOR.search(text):
        sponsor = True
    else:
        sponsor = None
    return {
        "visaSponsorship": sponsor,
        "citizenshipRequired": bool(_CITIZEN.search(text)),
        "itarRestricted": bool(_ITAR.search(text)),
        "clearanceRequired": level in ("Secret", "Top Secret", "TS/SCI"),
        "clearanceLevel": level,
    }


# --------------------------------------------------------------------------- #
#  Common record                                                               #
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    title: str
    employer: str
    source: str
    location: str
    remote: bool
    description: str
    applyUrl: str
    datePosted: str
    experienceLevel: str = ""
    requiredSkills: list = field(default_factory=list)
    visaSponsorship: Optional[bool] = None
    citizenshipRequired: bool = False
    itarRestricted: bool = False
    clearanceRequired: bool = False
    clearanceLevel: str = "None"
    salaryMin: Optional[int] = None
    salaryMax: Optional[int] = None

    @classmethod
    def build(cls, *, title, employer, source, location, remote,
              text, url, posted, salary=None):
        j = cls(title=title.strip(), employer=employer, source=source,
                location=location or "Not specified", remote=bool(remote),
                description=text[:1500], applyUrl=url, datePosted=posted)
        j.experienceLevel = seniority(title)
        j.requiredSkills = skills_in(text)
        for k, v in eligibility(text).items():
            setattr(j, k, v)
        if salary and salary.get("min"):
            j.salaryMin = int(salary["min"])
            j.salaryMax = int(salary.get("max") or salary["min"])
        return j


# --------------------------------------------------------------------------- #
#  Providers                                                                    #
# --------------------------------------------------------------------------- #
def _http(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "jobswipe/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def from_greenhouse(slug, name):
    data = _http(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        sal = None
        pr = j.get("pay_input_ranges") or []
        if pr:
            try:
                sal = {"min": float(pr[0]["min_cents"]) / 100,
                       "max": float(pr[0]["max_cents"]) / 100}
            except (KeyError, ValueError, TypeError):
                pass
        out.append(Job.build(
            title=j.get("title", ""), employer=name, source="greenhouse",
            location=loc, remote="remote" in loc.lower(),
            text=clean(j.get("content", "")), url=j.get("absolute_url", ""),
            posted=(j.get("updated_at") or "")[:10], salary=sal))
    return out


def from_lever(slug, name):
    data = _http(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for p in data:
        cats = p.get("categories") or {}
        loc = cats.get("location", "")
        text = p.get("descriptionPlain") or clean(p.get("description", ""))
        for lst in p.get("lists") or []:
            text += " " + clean(lst.get("content", ""))
        sr = p.get("salaryRange") or {}
        sal = {"min": sr["min"], "max": sr.get("max")} if sr.get("min") else None
        posted = (time.strftime("%Y-%m-%d", time.gmtime(p["createdAt"] / 1000))
                  if p.get("createdAt") else "")
        remote = str(p.get("workplaceType", "")).lower() == "remote" or "remote" in loc.lower()
        out.append(Job.build(
            title=p.get("text", ""), employer=name, source="lever",
            location=loc, remote=remote, text=text,
            url=p.get("hostedUrl", ""), posted=posted, salary=sal))
    return out


def from_ashby(slug, name):
    data = _http(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    out = []
    for j in data.get("jobs", []):
        loc = j.get("location", "")
        text = j.get("descriptionPlain") or clean(j.get("descriptionHtml", ""))
        sal = None
        tier = (j.get("compensation") or {}).get("compensationTierSummary", "")
        nums = re.findall(r"\$([\d,]+)", tier)
        if len(nums) >= 2:
            sal = {"min": int(nums[0].replace(",", "")),
                   "max": int(nums[1].replace(",", ""))}
        out.append(Job.build(
            title=j.get("title", ""), employer=name, source="ashby",
            location=loc, remote=bool(j.get("isRemote")) or "remote" in loc.lower(),
            text=text, url=j.get("jobUrl", ""),
            posted=(j.get("publishedAt") or "")[:10], salary=sal))
    return out


PROVIDERS = {"greenhouse": from_greenhouse, "lever": from_lever, "ashby": from_ashby}


# --------------------------------------------------------------------------- #
#  companies.yaml (tiny reader, no PyYAML needed)                              #
# --------------------------------------------------------------------------- #
def read_companies(path):
    provider, out = None, {k: [] for k in PROVIDERS}
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#")[0].rstrip()
        if not line.strip():
            continue
        m = re.match(r"^\s{2}(\w+):\s*$", line)
        if m and m.group(1) in PROVIDERS:
            provider = m.group(1)
            continue
        if provider is None:
            continue
        slug = re.search(r"slug:\s*([\w-]+)", line)
        nm = re.search(r"name:\s*(.+?)\s*}?\s*$", line)
        if slug:
            out[provider].append((slug.group(1),
                                  nm.group(1).strip() if nm else slug.group(1)))
    return out


# --------------------------------------------------------------------------- #
#  Offline self-test                                                           #
# --------------------------------------------------------------------------- #
def selftest():
    cases = [
        ("Software Engineer, New Grad",
         "Build with Python, React, PostgreSQL on AWS. We will sponsor visas.",
         {"experienceLevel": "Entry", "visaSponsorship": True,
          "clearanceRequired": False}),
        ("Senior Systems Engineer",
         "Distributed systems in Go. Must be a U.S. Citizen with an active Secret clearance.",
         {"experienceLevel": "Senior", "citizenshipRequired": True,
          "clearanceRequired": True, "clearanceLevel": "Secret"}),
        ("Associate ML Engineer",
         "Train models in PyTorch. We are unable to sponsor work visas for this role.",
         {"experienceLevel": "Entry", "visaSponsorship": False}),
    ]
    ok = True
    for title, text, expect in cases:
        j = Job.build(title=title, employer="X", source="t", location="Remote",
                      remote=True, text=text, url="", posted="2026-01-01")
        d = asdict(j)
        for k, v in expect.items():
            passed = d[k] == v
            ok &= passed
            print(f"  {'PASS' if passed else 'FAIL'}  {title[:24]:24}  {k}={d[k]}")
    print("\nExample record:")
    print(json.dumps(asdict(Job.build(
        title="New Grad Software Engineer", employer="Stripe", source="greenhouse",
        location="Remote", remote=True,
        text="Ship product with Python, TypeScript, React. Visa sponsorship available.",
        url="https://x", posted="2026-08-01", salary={"min": 120000, "max": 160000})),
        indent=2))
    return ok


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", default="companies.yaml")
    ap.add_argument("--out", default="jobs_raw.json")
    ap.add_argument("--new-grad-only", action="store_true")
    ap.add_argument("--per-board", type=int, default=0, help="cap kept per board")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(0 if selftest() else 1)

    companies = read_companies(a.companies)
    jobs = []
    for provider, entries in companies.items():
        for slug, name in entries:
            print(f"fetch {provider}/{slug}", file=sys.stderr)
            try:
                got = PROVIDERS[provider](slug, name)
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as e:
                print(f"  ! {provider}/{slug}: {e}", file=sys.stderr)
                continue
            if a.per_board:
                got = got[:a.per_board]
            jobs.extend(got)

    if a.new_grad_only:
        jobs = [j for j in jobs if j.experienceLevel == "Entry"]

    payload = [asdict(j) for j in jobs]
    json.dump(payload, open(a.out, "w"), indent=2)
    print(f"\nwrote {len(payload)} jobs -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

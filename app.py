#!/usr/bin/env python3
"""
app.py — JobSwipe backend.

Endpoints
    POST /resume        upload a resume PDF -> seed the user's profile vector
    GET  /jobs/next     next card: vector-ranked vs the user's live taste
    POST /swipe         record like/pass; right-swipes reshape the deck
    GET  /matches       liked jobs + LLM "why it surfaced / skill gaps"

Storage (MongoDB Atlas)
    jobs     seeded by ingest_atlas.py, each with an `embedding`
    users    { _id, profileVector, likedVectors[], seenIds[], eligibility{} }
    swipes   { userId, jobId, direction, ts }

The heavy lifting (embeddings, $vectorSearch) lives in ingest_atlas.py so this
file stays a thin API layer.
"""
from __future__ import annotations
import os, time
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import ingest_atlas as core
from resume_parser import parse_resume, profile_text

app = Flask(__name__)
CORS(app)
db = MongoClient(os.environ["MONGODB_URI"])[core.DB_NAME]
MIN_LIKES_FOR_TASTE = 3          # below this, seed from the resume vector


def _user(uid):
    u = db.users.find_one({"_id": uid})
    if not u:
        u = {"_id": uid, "profileVector": None, "likedVectors": [],
             "seenIds": [], "eligibility": {}}
        db.users.insert_one(u)
    return u


@app.post("/resume")
def resume():
    uid = request.form.get("userId", "demo")
    f = request.files["file"]
    path = f"/tmp/{uid}.pdf"
    f.save(path)
    profile = parse_resume(path)
    vec = core.embed([profile_text(profile)], "query")[0]
    db.users.update_one({"_id": uid},
                        {"$set": {"profileVector": vec, "profile": profile}},
                        upsert=True)
    return jsonify({"skills": profile["skills"], "gradYear": profile["gradYear"]})


@app.get("/jobs/next")
def jobs_next():
    uid = request.args.get("userId", "demo")
    u = _user(uid)
    elig = _eligibility_filter(u.get("eligibility", {}))
    likes = u.get("likedVectors") or []
    seeds = likes if len(likes) >= MIN_LIKES_FOR_TASTE else (
        [u["profileVector"]] if u.get("profileVector") else None)
    if not seeds:
        # true cold start: hand back anything eligible and unseen
        q = {"_id": {"$nin": u["seenIds"]}, **_plain_filter(u.get("eligibility", {}))}
        doc = db.jobs.find_one(q, {"embedding": 0})
        return jsonify(doc or {})
    cards = core.recommend(db.jobs, seeds, u["seenIds"], elig, k=1)
    return jsonify(cards[0] if cards else {})


@app.post("/swipe")
def swipe():
    body = request.get_json(force=True)
    uid, jid, direction = body["userId"], body["jobId"], body["direction"]
    db.swipes.insert_one({"userId": uid, "jobId": jid,
                          "direction": direction, "ts": time.time()})
    update = {"$addToSet": {"seenIds": jid}}
    if direction == "right":
        job = db.jobs.find_one({"_id": jid}, {"embedding": 1})
        if job and job.get("embedding"):
            update.setdefault("$push", {})["likedVectors"] = job["embedding"]
    db.users.update_one({"_id": uid}, update, upsert=True)
    return jsonify({"ok": True})


@app.get("/matches")
def matches():
    uid = request.args.get("userId", "demo")
    liked = [s["jobId"] for s in db.swipes.find({"userId": uid, "direction": "right"})]
    jobs = list(db.jobs.find({"_id": {"$in": liked}}, {"embedding": 0}))
    profile = (db.users.find_one({"_id": uid}) or {}).get("profile", {})
    for j in jobs:
        j["analysis"] = _explain(j, profile)   # LLM gap analysis
    return jsonify(jobs)


# --------------------------------------------------------------------------- #
def _eligibility_filter(elig: dict) -> dict:
    """Atlas $vectorSearch pre-filter: never surface a role the user is barred
    from. Citizens keep citizen-only roles; non-citizens who need sponsorship
    drop them."""
    f = {}
    if elig.get("needsSponsorship"):
        f["citizenshipRequired"] = {"$eq": False}
        f["visaSponsorship"] = {"$ne": False}
    if not elig.get("hasClearance"):
        f["clearanceRequired"] = {"$eq": False}
    return f


def _plain_filter(elig: dict) -> dict:
    f = {}
    if elig.get("needsSponsorship"):
        f["citizenshipRequired"] = False
        f["visaSponsorship"] = {"$ne": False}
    if not elig.get("hasClearance"):
        f["clearanceRequired"] = False
    return f


def _explain(job: dict, profile: dict) -> dict:
    """Matches-view explanation. Swap the stub for an Anthropic call:

        import anthropic
        msg = anthropic.Anthropic().messages.create(
            model="claude-sonnet-5", max_tokens=400,
            messages=[{"role": "user", "content": PROMPT.format(job=job, profile=profile)}])
        return parse(msg.content[0].text)

    Kept deterministic here so the app runs before you wire the key."""
    have = set(profile.get("skills", []))
    need = set(job.get("requiredSkills", []))
    return {
        "matchedSkills": sorted(have & need),
        "missingSkills": sorted(need - have),
        "note": "Wire ANTHROPIC_API_KEY to replace this with a written rationale.",
    }


if __name__ == "__main__":
    app.run(port=5000, debug=True)

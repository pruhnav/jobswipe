#!/usr/bin/env python3
"""
ingest_atlas.py — embed job descriptions with Voyage AI and load them into
MongoDB Atlas, then create the Vector Search index JobSwipe's deck runs on.

Voyage AI is now "Voyage AI by MongoDB", so this keeps the whole retrieval
stack on one partner. voyage-3.5 outputs 1024-dim vectors by default; the code
reads the real dimension off the first embedding so swapping models (voyage-4,
voyage-3.5-lite, custom dimensions) just works.

Env (.env):
    MONGODB_URI=mongodb+srv://...
    VOYAGE_API_KEY=...
    VOYAGE_MODEL=voyage-3.5          # optional
    DB_NAME=jobswipe               # optional

    python ingest_atlas.py --jobs jobs_raw.json --create-index
"""
from __future__ import annotations
import argparse, json, os, sys, time
from dotenv import load_dotenv
load_dotenv()
import voyageai
from pymongo import MongoClient, UpdateOne
from pymongo.operations import SearchIndexModel

DB_NAME = os.getenv("DB_NAME", "jobswipe")
JOBS = "jobs"
INDEX = "job_vectors"
MODEL = os.getenv("VOYAGE_MODEL", "voyage-3.5")

_vo = None
def voyage():
    global _vo
    if _vo is None:
        _vo = voyageai.Client()  # reads VOYAGE_API_KEY
    return _vo


def embed(texts: list[str], input_type: str) -> list[list[float]]:
    """input_type='document' when indexing jobs, 'query' when searching.
    Batched to stay within Voyage request limits."""
    out, B = [], 128
    for i in range(0, len(texts), B):
        chunk = [t[:8000] for t in texts[i:i + B]]
        resp = voyage().embed(chunk, model=MODEL, input_type=input_type)
        out.extend(resp.embeddings)
        time.sleep(0.2)
    return out


def job_text(j: dict) -> str:
    """What we embed: title + employer + skills + description. Skills are
    repeated deliberately so they carry weight in the vector."""
    skills = ", ".join(j.get("requiredSkills", []))
    return (f"{j['title']} at {j['employer']}. "
            f"Skills: {skills}. Level: {j.get('experienceLevel','')}. "
            f"{j.get('description','')}")


def ingest(path: str):
    jobs = json.load(open(path))
    print(f"embedding {len(jobs)} jobs with {MODEL} ...")
    vectors = embed([job_text(j) for j in jobs], "document")
    dim = len(vectors[0])
    print(f"  -> {dim}-dim vectors")

    client = MongoClient(os.environ["MONGODB_URI"])
    col = client[DB_NAME][JOBS]
    ops = []
    for j, v in zip(jobs, vectors):
        key = j.get("applyUrl") or f"{j['employer']}:{j['title']}"
        j["_id"] = key
        j["embedding"] = v
        ops.append(UpdateOne({"_id": key}, {"$set": j}, upsert=True))
    res = col.bulk_write(ops, ordered=False)
    print(f"  upserted={res.upserted_count} modified={res.modified_count}")
    return col, dim


def create_index(col, dim: int):
    """Vector index + the filter fields the deck pre-filters on
    (eligibility gate + experience level + remote)."""
    model = SearchIndexModel(
        name=INDEX,
        type="vectorSearch",
        definition={"fields": [
            {"type": "vector", "path": "embedding",
             "numDimensions": dim, "similarity": "cosine"},
            {"type": "filter", "path": "experienceLevel"},
            {"type": "filter", "path": "visaSponsorship"},
            {"type": "filter", "path": "citizenshipRequired"},
            {"type": "filter", "path": "clearanceRequired"},
            {"type": "filter", "path": "remote"},
        ]},
    )
    try:
        col.create_search_index(model=model)
        print(f"  index '{INDEX}' creating (Atlas builds it async, ~1 min)")
    except Exception as e:  # already exists / edition without vector search
        print(f"  index note: {e}")


def recommend(col, liked_vectors: list[list[float]], seen_ids: list[str],
              elig_filter: dict | None = None, k: int = 10):
    """The core deck query: score candidates against the centroid of the
    user's right-swipes, pre-filtered by their eligibility profile, excluding
    already-seen jobs. Fewer than N likes -> pass the resume vector instead."""
    n = len(liked_vectors[0])
    centroid = [sum(col) / len(liked_vectors) for col in zip(*liked_vectors)]
    stage = {
        "$vectorSearch": {
            "index": INDEX,
            "path": "embedding",
            "queryVector": centroid,
            "numCandidates": 200,
            "limit": k + len(seen_ids),
        }
    }
    if elig_filter:
        stage["$vectorSearch"]["filter"] = elig_filter
    pipeline = [
        stage,
        {"$match": {"_id": {"$nin": seen_ids}}},
        {"$project": {"embedding": 0}},
        {"$addFields": {"matchScore": {"$meta": "vectorSearchScore"}}},
        {"$limit": k},
    ]
    return list(col.aggregate(pipeline))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default="jobs_raw.json")
    ap.add_argument("--create-index", action="store_true")
    a = ap.parse_args()
    if "MONGODB_URI" not in os.environ or "VOYAGE_API_KEY" not in os.environ:
        sys.exit("Set MONGODB_URI and VOYAGE_API_KEY (see .env.example).")
    col, dim = ingest(a.jobs)
    if a.create_index:
        create_index(col, dim)
    print("done.")


if __name__ == "__main__":
    main()

# JobSwipe

Swipe through entry-level engineering jobs. Every card leads with the two flags
that actually gate a new grad — **visa sponsorship** and **security clearance** —
so you never waste an application on a role you can't hold. Right-swipes reshape
the deck live via MongoDB Atlas Vector Search; a Matches view explains why each
saved role surfaced and which required skills your resume didn't demonstrate.

Built fresh for this project. No external scraper or prior codebase — the data
layer talks directly to public, key-free ATS board APIs.

## Stack

| Layer | Tech |
|---|---|
| Job data | Public ATS APIs — Greenhouse, Lever, Ashby (no keys) |
| Embeddings | **Voyage AI by MongoDB** (`voyage-3.5`, 1024-dim) |
| Store + retrieval | **MongoDB Atlas** + Atlas Vector Search (`$vectorSearch`) |
| API | Flask |
| UI | React (`frontend/SwipeDeck.jsx`) |

## Pipeline

```
companies.yaml ──> fetch_boards.py ──> jobs_raw.json ──> ingest_atlas.py ──> Atlas
   (slugs)          (fetch+normalize)    (clean records)   (embed + index)   (jobs + vectors)
                                                                                    │
                          resume.pdf ─> resume_parser.py ─> profile vector          ▼
                                                                            app.py  (deck / swipe / matches)
                                                                                    │
                                                                          frontend/SwipeDeck.jsx
```

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add your MONGODB_URI + VOYAGE_API_KEY

python fetch_boards.py --new-grad-only        # -> jobs_raw.json
python ingest_atlas.py --jobs jobs_raw.json --create-index
python app.py                                  # http://localhost:5000
```

Point the React frontend at `http://localhost:5000`. To view the UI on its own
(mock data, no backend), open `frontend/SwipeDeck.jsx` in any React sandbox.

## How the deck learns

1. **Cold start** — the resume vector (`resume_parser.py`) seeds the first cards, so the deck opens relevant instead of random.
2. **Taste forms** — each right-swipe pushes that job's vector into `likedVectors`. After a few likes the deck ranks candidates against their centroid.
3. **Eligibility gate** — before ranking, `$vectorSearch` pre-filters out roles the user is barred from (citizenship / clearance), so ineligible jobs never reach the card stack.
4. **Matches** — saved roles get a skill-gap breakdown (wire `ANTHROPIC_API_KEY` for a written rationale).

## Files

- `companies.yaml` — ATS slugs (rebuildable from any careers-page URL)
- `fetch_boards.py` — fetch + normalize to the JobSwipe schema (`--selftest` runs offline)
- `ingest_atlas.py` — Voyage embeddings, Atlas upsert, vector index, `recommend()`
- `resume_parser.py` — PDF → profile vector
- `app.py` — Flask API
- `schema.md` — collection + index definitions
- `frontend/SwipeDeck.jsx` — the swipe UI

## Notes

- `visaSponsorship` is tri-state (`true`/`false`/`null`). Most commercial postings say nothing, so `null` means *unknown* — fill it later with an LLM pass or an H-1B filing-history join. Regex handles only the explicit cases.
- Greenhouse exposes salary only on pay-transparency boards, so some records have no band. The document model expects that.
- `voyage-3.5` is the current GA default; the ingest reads the vector dimension at runtime, so `voyage-4` or a custom Matryoshka dimension drops in without code changes.

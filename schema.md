# JobSwipe — MongoDB collections

Three collections in the `jobswipe` database.

## `jobs`
One document per posting. Written by `ingest_atlas.py`. Structurally
inconsistent by design — `salaryMin/Max` are absent on boards that don't
publish pay, `requiredSkills` length varies widely. That variance is the
reason for a document store over rigid SQL.

| field | type | notes |
|---|---|---|
| `_id` | string | applyUrl, or `employer:title` fallback |
| `title` | string | |
| `employer` | string | |
| `source` | string | `greenhouse` \| `lever` \| `ashby` |
| `location` | string | |
| `remote` | bool | |
| `experienceLevel` | string | `Entry` \| `Mid-Level` \| `Senior` |
| `requiredSkills` | string[] | normalized against a shared vocabulary |
| `visaSponsorship` | bool \| null | **null = unknown**, resolved later by LLM/LCA |
| `citizenshipRequired` | bool | eligibility gate |
| `clearanceRequired` | bool | eligibility gate |
| `clearanceLevel` | string | `None` \| `Public Trust` \| `Secret` \| `Top Secret` \| `TS/SCI` |
| `itarRestricted` | bool | eligibility gate |
| `salaryMin` / `salaryMax` | int | optional |
| `description` | string | truncated to 1500 chars |
| `applyUrl` | string | |
| `datePosted` | string | ISO date |
| `embedding` | float[] | Voyage vector, indexed |

**Vector index `job_vectors`** (created by `ingest_atlas.py`):
vector on `embedding` (cosine) + filter fields `experienceLevel`,
`visaSponsorship`, `citizenshipRequired`, `clearanceRequired`, `remote`.

## `users`
| field | type | notes |
|---|---|---|
| `_id` | string | user id |
| `profileVector` | float[] | seeded from resume, cold-start deck |
| `likedVectors` | float[][] | right-swiped job vectors; centroid = live taste |
| `seenIds` | string[] | excluded from future cards |
| `eligibility` | object | `{ needsSponsorship, hasClearance }` |
| `profile` | object | parsed resume: skills, gradYear, yearsExperience |

## `swipes`
| field | type | notes |
|---|---|---|
| `userId` | string | |
| `jobId` | string | |
| `direction` | string | `left` \| `right` |
| `ts` | number | epoch seconds |

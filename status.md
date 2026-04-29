# status.md — VoidAccess Build Status

> Update this file at the end of every phase. It is read at the start of every Cursor session.
> Keep it accurate. This is how the AI knows where we are.

---

## Overall Progress

Backend: ALL 6 PHASES COMPLETE ✅ — 578/578 tests passing, full audit passed
Frontend: Phase 7 — Next.js UI (in progress)

---

## Backend Completed Phases

### Phase 1A — Persistent Database ✅ (61 tests)
db/ — models, session, queries, Alembic migrations, docker-compose.yml
Config: DATABASE_URL, TOR_PROXY_HOST, TOR_PROXY_PORT

### Phase 1B — Async Scraper ✅ (91 tests)
scrape.py — asyncio + aiohttp-socks, trafilatura, exponential backoff

### Phase 1C — Recursive Crawler ✅ (158 tests)
crawler/ — spider, frontier (sentence-transformers), dedup, utils

### Phase 1D — Expanded Sources ✅ (213 tests)
sources/ — DarkSearch, OnionSearch, seeds (25), pastes, Telegram (Telethon)

### Phase 2 — Entity Extraction ✅ (295 tests)
extractor/ — regex (10 types), spaCy NER, LLM extraction, normalizer, pipeline

### Phase 3 — Graph Mapping ✅ (333 tests)
graph/ — NetworkX MultiDiGraph, builder, queries, export, pyvis

### Phase 4 — Monitoring + Vector Memory ✅ (367 tests)
monitor/ — APScheduler, jobs, diff, alerts
vector/ — ChromaDB, sentence-transformers, semantic search

### Phase 5 — Outputs + REST API ✅ (461 tests)
export/ — STIX 2.1, MISP, Sigma YAML
api/ — FastAPI: /investigations, /entities, /search, /export, /monitors, /health

### Phase 6 — Advanced Capabilities ✅ (574 tests)
fingerprint/ — stylometry (11 features), actor profiling
analysis/ — temporal, anomaly detection, pattern matching, OPSEC detection
i18n/ — language detection, DeepL/Helsinki-NLP translation, query expansion
ui_integration.py — Streamlit extension panels

### Audit Fixes ✅ (578 tests)
All 5 critical + 4 minor audit issues resolved. Platform deployment-ready.

---

## Frontend — Phase 7 (In Progress)

### Phase 7A — Homepage 🔄 IN PROGRESS

Tech: Next.js 14 App Router, TypeScript, Tailwind CSS, Canvas API
Location: frontend/ directory (separate from Python backend)

Design system:
  Background: Black (#000) → dark navy (#020817) + animated particle network
  Particles: #00ff41 (matrix green) nodes with connection lines — dark web metaphor
  Primary accent: #00ff41 (matrix green)
  Danger accent: #ff0033 (deep red)
  Font: JetBrains Mono (monospace, terminal feel)
  Scanlines overlay, vignette, soft red glow orb above headline

Homepage layout (bolt.new style):
  - Nav bar: "● VOID ACCESS" logo + Investigations / Monitor / Docs links
  - Centered headline: "What will you hunt today?" ("hunt" in italic green)
  - Subheadline: "AI-powered dark web intelligence. Investigate. Extract. Map."
  - Investigation input box (720px max-width, dark glass morphism)
    - Textarea with auto-grow
    - Toolbar: model selector pill + Full Intelligence toggle + Investigate button
  - Preset pills below input
  - Status bar at bottom: Tor status (live) + API status + test count

Files to create:
  frontend/app/page.tsx
  frontend/app/layout.tsx
  frontend/app/globals.css
  frontend/app/api/investigate/route.ts
  frontend/components/ParticleCanvas.tsx
  frontend/components/InvestigationInput.tsx
  frontend/components/StatusBar.tsx
  frontend/lib/api.ts

### Phase 7B — Investigation Results ⬜ NOT STARTED
### Phase 7C — Graph Visualization ⬜ NOT STARTED
### Phase 7D — Monitoring Dashboard ⬜ NOT STARTED

---

## Key Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| DB | PostgreSQL + SQLAlchemy 2.x | Reliable, versioned |
| Tor proxy | TOR_PROXY_HOST/PORT env vars | Docker-configurable |
| Graph | NetworkX → Neo4j at scale | Zero setup for dev |
| Vector | ChromaDB local | No external service |
| Frontend | Next.js 14 + TypeScript | Modern, type-safe |
| FE animations | CSS + Canvas API only | No heavy libraries |
| FE↔BE bridge | FastAPI REST at NEXT_PUBLIC_API_URL | Clean separation |

---

## Test Count History

| Phase | Tests |
|---|---|
| 1A | 61 |
| 1B | 91 |
| 1C | 158 |
| 1D | 213 |
| 2 | 295 |
| 3 | 333 |
| 4 | 367 |
| 5 | 461 |
| 6 | 574 |
| Audit fixes | 578 |

Frontend: visual validation only, no automated tests.
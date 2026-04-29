# concept.md — VoidAccess: Next-Generation Dark Web Intelligence Platform

> This document is the single source of truth for where this project is going and how we get there.
> Always read this before writing new code. Every architectural decision made during development
> should be traceable back to a section in this file.

---

## Vision

VoidAccess in its current form is a **search engine wrapper with an LLM summary layer**. It's useful,
clean, and well-structured — but it only sees ~1–3% of the dark web (what Ahmia and similar engines
happen to index), has no memory between runs, extracts no structured data, and produces no output
that integrates with professional security tooling.

The goal of this project is to transform VoidAccess into a **persistent, autonomous dark web intelligence
platform** that:

- Crawls and indexes dark web content independently, not just what search engines surface
- Remembers everything it has ever found and detects what's new vs. what it already knows
- Extracts structured intelligence artifacts (wallets, handles, malware names, CVEs, PGP keys)
- Maps relationships between entities across sources and over time
- Monitors specific targets continuously and alerts on changes
- Outputs in STIX/TAXII and MISP formats for enterprise security tool integration
- Profiles threat actors using behavioral and stylometric fingerprinting
- Operates across multiple darknets and surface intelligence sources simultaneously

When complete, this platform should functionally match or exceed commercial tools like Recorded
Future, DarkOwl, and Flare — at open-source cost — and include capabilities those platforms do
not offer (writing fingerprinting, predictive behavioral alerting, automated OPSEC failure detection).

---

## Guiding Principles

1. **Never break what exists.** The original VoidAccess pipeline always stays functional. New capabilities
   are additive modules, not replacements.

2. **Data is the moat.** Every piece of scraped content, every extracted entity, every relationship
   should be persisted. The platform gets more valuable with every run.

3. **Structure over summaries.** An LLM summary is a byproduct. The primary output is structured,
   queryable, exportable intelligence data.

4. **Tor safety is non-negotiable.** Every request to a `.onion` address goes through Tor. No
   exceptions. Anonymity is a feature, not an afterthought.

5. **Build in phases.** Each phase delivers working, usable capability. Nothing is left half-built
   before moving to the next layer.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    COLLECTION LAYER                     │
│  Multi-source ingestion: search engines, recursive      │
│  crawler, Telegram, paste sites, I2P, seed URL lists    │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   PROCESSING LAYER                      │
│  HTML parsing, content cleaning, language detection,    │
│  translation, entity extraction (NER + regex + LLM)     │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    STORAGE LAYER                        │
│  PostgreSQL (structured data + entities)                │
│  Vector DB / Chroma (semantic search + dedup)           │
│  Neo4j or NetworkX (graph relationships)                │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   ANALYSIS LAYER                        │
│  Graph traversal, actor profiling, temporal reasoning,  │
│  stylometry, OPSEC failure detection, change detection  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    OUTPUT LAYER                         │
│  UI (Streamlit enhanced), STIX/TAXII, MISP export,      │
│  Sigma rules, webhook alerts, REST API                  │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 0 — Baseline (COMPLETE — existing VoidAccess)

**What exists:**
- Single-run investigation pipeline (query → refine → search → filter → scrape → summarize)
- 16 Tor-based search engines queried in parallel
- LangChain multi-model support (OpenAI, Anthropic, Gemini, Ollama)
- Streamlit UI with investigation presets
- JSON-based investigation persistence
- Docker deployment

**What it can't do:** Everything in Phase 1–6.

---

## Phase 1 — Foundation: Persistence + Recursive Crawling

**Goal:** Transform VoidAccess from stateless single-run to a system with memory and real crawling capability.

### 1A — Persistent Database

**Why first:** Every other feature depends on having a place to store data. You can't do change
detection, relationship mapping, or deduplication without persistence.

**What to build:**
- PostgreSQL database with SQLAlchemy ORM
- Schema:
  - `investigations` — metadata (query, timestamp, model used, run ID)
  - `sources` — every URL ever seen (onion address, first seen, last seen, status)
  - `pages` — every scraped page (URL FK, raw content hash, cleaned text, scrape timestamp)
  - `entities` — extracted structured data (type, value, page FK, confidence score)
  - `relationships` — entity-to-entity connections (entity A, entity B, relationship type, source page)
- Alembic for migrations (schema changes tracked in version control)
- Connection pool with proper cleanup

**Files to create:**
- `db/__init__.py`
- `db/models.py` — SQLAlchemy table definitions
- `db/session.py` — connection pool, session factory
- `db/migrations/` — Alembic migration scripts
- `db/queries.py` — common query helpers

**Integration point:** Modify `ui.py` to write investigation results to DB after each run.
JSON export stays, DB becomes the primary store.

---

### 1B — Async Scraping Engine

**Why:** The current `scrape.py` uses Python threads. Tor is slow (500ms–2s per request). Threads
block on I/O. `asyncio` + `aiohttp-socks` lets you fire off 50–100 requests simultaneously
without 50–100 threads. Real-world speedup: 5–10x on the scraping stage.

**What to build:**
- Rewrite `scrape.py` scraping core to use `asyncio` + `aiohttp-socks`
- Maintain backward compatibility — same function signatures, drop-in replacement
- Add exponential backoff on failed requests
- Smarter content extraction: strip HTML noise (navbars, scripts, footers) before passing to LLM.
  Use `trafilatura` or `newspaper3k` for main content extraction — this gets 3–4x more useful
  content into the same LLM context window.

**Files to modify:** `scrape.py`

---

### 1C — Recursive .onion Crawler

**Why:** The single biggest capability gap. This is what transforms VoidAccess from a search engine
client into an actual crawler.

**What to build:**
A spider that:
1. Accepts a seed URL (or list of seed URLs)
2. Fetches the page via Tor
3. Extracts all `.onion` links from the HTML
4. Scores each link for relevance to the current investigation query (using embedding similarity)
5. Adds high-relevance links to a priority queue (max depth configurable)
6. Respects per-domain rate limits and revisit intervals
7. Persists every URL it discovers (even unvisited) to the `sources` table
8. Archives content immediately on first scrape (dark web content disappears fast)

**Implementation notes:**
- Use `asyncio` queue for the crawl frontier
- Configurable: max depth (default 2), max pages per run (default 200), min relevance score (0.0–1.0)
- Deduplication: content hash before storing — don't store the same page twice
- Politeness: random delay between requests to same domain (2–8 seconds)
- Never follow links to clearnet (`.com`, `.org`, etc.) — `.onion` only

**Files to create:**
- `crawler/__init__.py`
- `crawler/spider.py` — main async crawler class
- `crawler/frontier.py` — priority queue with relevance scoring
- `crawler/dedup.py` — content hash deduplication
- `crawler/utils.py` — link extraction, domain parsing

---

### 1D — Expanded Source Coverage

**Why:** Ahmia indexes ~1–3% of dark web content. Adding more search engines and source types
multiplies coverage immediately with minimal new code.

**Sources to add:**
- Torch `.onion` search engine
- Haystack `.onion` search engine
- DarkSearch API (has a free tier with API key)
- OnionSearch aggregator
- Known high-value forum seed URL list (hardcoded, curated manually — start with 20–30 URLs)
- Paste site mirrors (PrivateBin `.onion` instances)

**Telegram integration (separate from Tor):**
- Telegram API (via `telethon`) for monitoring public channels/groups where threat actors operate
- This is clearnet but critically important — massive threat actor activity on Telegram
- Channels to monitor specified in config

**Files to modify/create:**
- `search.py` — add new search engines to `SEARCH_ENGINES` list
- `sources/telegram.py` — Telegram channel monitor via Telethon

**New env vars:**
```
DARKSEARCH_API_KEY=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
```

---

## Phase 2 — Intelligence: Entity Extraction Pipeline

**Goal:** Convert raw scraped text into structured, queryable intelligence records.

**Why this is transformational:** The difference between "a Bitcoin wallet was mentioned" and
"wallet `bc1qxy2k...` received 14.3 BTC on March 3rd, co-appeared with handle `DarkKnight99` on
Forum X" is the difference between a summary and intelligence.

### 2A — Regex-Based Extraction

Fast, cheap, high precision for known patterns. Run this first on every page.

**Patterns to extract:**

| Entity Type | Pattern | Example |
|---|---|---|
| Bitcoin address | `bc1[a-zA-HJ-NP-Z0-9]{25,62}` or legacy `1[a-km-zA-HJ-NP-Z1-9]{25,34}` | `bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh` |
| Ethereum address | `0x[a-fA-F0-9]{40}` | `0x742d35Cc...` |
| Monero address | `4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}` | XMR addresses |
| .onion URL | `[a-z2-7]{16,56}\.onion` | Links found in content |
| Email address | Standard RFC regex | `user@domain.tld` |
| PGP key block | `-----BEGIN PGP PUBLIC KEY BLOCK-----` | Full key extraction |
| CVE number | `CVE-\d{4}-\d{4,7}` | `CVE-2024-12345` |
| IP address | Standard IP regex (exclude RFC1918) | `185.220.xxx.xxx` |
| Phone number | E.164 + regional patterns | International formats |
| Paste URL | pastebin.com, rentry.co, etc. | Links to paste sites |

### 2B — NER-Based Extraction

For entities that don't have fixed patterns: threat actor names, malware family names, organization
names, location references. Use a local NER model (spaCy `en_core_web_trf` or a fine-tuned
security-domain model) so this runs offline without API calls.

**Custom entity types to fine-tune for:**
- Malware family names (match against a curated dictionary of known malware names)
- Ransomware group names (match against known RaaS group list)
- Hacker handles / aliases (contextual detection)
- Dark web market names

### 2C — LLM-Assisted Extraction (for ambiguous cases)

After regex + NER, pass remaining text chunks to LLM with a structured extraction prompt.
Ask for JSON output of any entities the regex/NER missed.

**Output schema per entity:**
```json
{
  "type": "crypto_wallet",
  "value": "bc1qxy2k...",
  "confidence": 0.97,
  "context": "surrounding 200 chars of text",
  "page_url": "http://example.onion/forum/thread/123",
  "first_seen": "2025-04-14T10:30:00Z"
}
```

### 2D — Entity Deduplication and Normalization

The same wallet address might appear in 50 pages. It gets one canonical record, with a list of
all pages where it appeared. Same for handles, email addresses, etc.

**Files to create:**
- `extractor/__init__.py`
- `extractor/regex_patterns.py` — all compiled regex patterns
- `extractor/ner.py` — spaCy NER pipeline
- `extractor/llm_extract.py` — LLM-based extraction for ambiguous cases
- `extractor/normalizer.py` — deduplication and canonical record merging
- `extractor/pipeline.py` — orchestrates regex → NER → LLM in sequence

**New dependencies:** `spacy`, `trafilatura`

---

## Phase 3 — Graph: Relationship Mapping

**Goal:** Connect extracted entities across sources and time. Make the invisible connections visible.

**Why:** The most valuable OSINT insight is relationships. When the same handle appears on three
forums, the same wallet appears on two markets, and the same PGP key appears on a paste site —
that's how you identify an actor and map their infrastructure.

### 3A — Graph Data Model

Use NetworkX for the graph engine (pure Python, no separate database server needed; can upgrade
to Neo4j later for scale).

**Node types:**
- `ThreatActor` (handle/alias)
- `CryptoWallet` (address + coin type)
- `OnionURL` (domain)
- `Forum` (site)
- `MalwareFamily` (name)
- `RansomwareGroup` (name)
- `PGPKey` (fingerprint)
- `EmailAddress`
- `CVE`
- `Paste` (paste site URL + content hash)

**Edge types:**
- `CO_APPEARED_ON` (two entities on same page)
- `POSTED_BY` (content attributed to handle)
- `LINKED_TO` (URL links to URL)
- `PAID_TO` (wallet received payment — if tx data available)
- `MEMBER_OF` (handle to group/forum)
- `USED` (actor used malware family)
- `CLAIMED` (group claimed attack)

**Edge properties:** source page URL, timestamp, confidence score

### 3B — Relationship Inference

Beyond explicit co-occurrence, infer likely relationships:
- Same handle on different forums → `LIKELY_SAME_ACTOR` edge (medium confidence)
- Same PGP key on two platforms → `CONFIRMED_SAME_ACTOR` edge (high confidence)
- Wallet funded by another wallet → `FUNDED_BY` edge (requires external blockchain lookup)
- Two posts with identical writing style → `POSSIBLE_SAME_AUTHOR` edge (Phase 6 stylometry)

### 3C — Graph Query Interface

Functions to ask the graph:
- "Give me everything connected to wallet X within 2 hops"
- "Find all handles that co-appeared with malware Y"
- "Show me the full network around forum Z"
- "What entities appeared for the first time this week?"

**Files to create:**
- `graph/__init__.py`
- `graph/model.py` — node and edge type definitions
- `graph/builder.py` — builds/updates graph from entity records in DB
- `graph/queries.py` — named graph query functions
- `graph/export.py` — export graph to Gephi, JSON, GraphML formats
- `graph/visualize.py` — renders interactive graph in Streamlit (via pyvis)

**New dependencies:** `networkx`, `pyvis`

---

## Phase 4 — Monitoring: Continuous Intelligence

**Goal:** VoidAccess stops being a tool you run manually. It watches, detects change, and tells you
what's new without being asked.

### 4A — Scheduled Job Runner

Use APScheduler (in-process) for simplicity, Celery for production scale.

**Job types:**
- `keyword_watch` — run a query every N hours, store new results, diff against last run
- `url_watch` — monitor specific `.onion` URLs for content changes
- `entity_alert` — trigger when a specific wallet/handle/CVE appears anywhere new
- `new_site_discovery` — crawler jobs that expand the known `.onion` graph

**Configuration:** YAML file `monitors.yaml` defining all active watches:
```yaml
watches:
  - name: "ransomware payments Q2"
    query: "ransomware payment escrow"
    interval_hours: 6
    alert_on: new_results
    webhook: https://hooks.slack.com/...

  - name: "track actor darkking99"
    entity_type: threat_actor_handle
    entity_value: "darkking99"
    alert_on: any_appearance
```

### 4B — Change Detection

For URL watches: store content hash on each scrape. When the hash changes, diff the content
(using `difflib`) and report only what changed. Crucial because dark web content is edited
frequently — you want to know *what* changed, not just *that* it changed.

For keyword watches: compare entity lists from current run vs. previous run. Report:
- New entities not seen before (globally, not just this run)
- Entities seen before that now appear in a new context
- Entities that have disappeared (page taken down)

### 4C — Alert Delivery

- Webhook (Slack/Discord/generic HTTP POST)
- Telegram bot message
- Email (SMTP)
- File drop (append to a monitored log file)

Alert payload includes: what triggered, entity/content summary, source URL, timestamp, link to
full investigation in UI.

### 4D — Vector Database for Semantic Memory

Use ChromaDB (runs locally, no server needed).

Every scraped page gets embedded using a local embedding model (`sentence-transformers/all-MiniLM-L6-v2`).

This enables:
- **Deduplication:** Don't report content you've already seen, even if it's on a new URL
- **Semantic search:** "Find me everything similar to this threat report I uploaded"
- **Cross-run memory:** Findings from 3 months ago can surface as related to today's query
- **Near-duplicate detection:** Slightly modified reposts of the same content are flagged

**Files to create:**
- `monitor/__init__.py`
- `monitor/scheduler.py` — APScheduler job management
- `monitor/jobs.py` — job type implementations
- `monitor/diff.py` — content change detection
- `monitor/alerts.py` — alert delivery (webhook, Telegram, email)
- `monitor/config.py` — loads `monitors.yaml`
- `vector/__init__.py`
- `vector/store.py` — ChromaDB interface
- `vector/embedder.py` — sentence-transformer embedding pipeline
- `vector/search.py` — semantic similarity search

**New dependencies:** `apscheduler`, `chromadb`, `sentence-transformers`

**New env vars:**
```
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
ALERT_EMAIL=
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=
```

---

## Phase 5 — Output: Industry-Standard Intelligence Exports

**Goal:** Make VoidAccess's output consumable by professional security tooling without any manual reformatting.

### 5A — STIX 2.1 Export

STIX (Structured Threat Information eXpression) is the universal standard for threat intelligence
sharing. Security teams feed STIX into their SIEMs, threat intel platforms, and firewall rules automatically.

**STIX objects to generate from VoidAccess's entities:**
- `Indicator` — crypto wallets, IPs, URLs, hashes (with STIX pattern syntax)
- `ThreatActor` — actor profiles with aliases, sophistication level
- `Malware` — malware family records with capabilities
- `Campaign` — if multiple events link to a coordinated campaign
- `Relationship` — connects the above objects
- `Report` — wraps a full investigation as a STIX bundle

**Files to create:**
- `export/__init__.py`
- `export/stix.py` — converts VoidAccess entities → STIX 2.1 objects using `stix2` library
- `export/taxii.py` — optional TAXII server for push/pull sharing

### 5B — MISP Export

MISP (Malware Information Sharing Platform) is used by national CERTs and large enterprises.
VoidAccess should be able to export an investigation as a MISP event JSON.

**Files to create:**
- `export/misp.py` — MISP event format generator

### 5C — Sigma Rule Generation

Sigma rules are SIEM-agnostic detection rules. When VoidAccess identifies a new malware C2 URL, a
new threat actor TTP, or a new exploit being discussed — it should auto-generate a draft Sigma
rule for detection.

**Files to create:**
- `export/sigma.py` — LLM-assisted Sigma rule drafting from entity + context data

### 5D — REST API

Streamlit is great for humans. Programmatic access needs a REST API.

Use FastAPI to expose:
- `POST /investigate` — trigger an investigation, returns run ID
- `GET /investigation/{run_id}` — get investigation results
- `GET /entities` — query entities by type, value, date range
- `GET /graph/neighbors/{entity_id}` — get graph neighbors
- `POST /monitor` — create a watch
- `GET /export/{run_id}/stix` — STIX bundle for an investigation
- `GET /export/{run_id}/misp` — MISP event for an investigation

**Files to create:**
- `api/__init__.py`
- `api/main.py` — FastAPI app
- `api/routes/` — route handlers per resource

**New dependencies:** `stix2`, `fastapi`, `uvicorn`

---

## Phase 6 — Advanced: Capabilities Beyond Commercial Tools

**Goal:** Build capabilities that even Recorded Future and DarkOwl don't offer cleanly.

### 6A — Writing Style Fingerprinting (Stylometry)

**What it does:** Identifies when the same person is posting on different forums under different
names, based on writing patterns — not content, but *how* they write.

**Features analyzed:**
- Average word length, sentence length
- Vocabulary richness (type-token ratio)
- Function word frequency (the, a, and, but — these are nearly impossible to change consciously)
- Punctuation patterns
- Common typos and misspellings
- N-gram character patterns

**Implementation:**
- Extract style vectors from all posts attributed to known handles
- When a new post appears from an unknown handle, compute its style vector
- Find nearest-neighbor handles in style space
- If similarity exceeds threshold: `POSSIBLE_SAME_AUTHOR` edge in graph with confidence score

**Files to create:**
- `fingerprint/__init__.py`
- `fingerprint/stylometry.py` — feature extraction and similarity computation
- `fingerprint/profiler.py` — builds and updates actor style profiles

### 6B — Temporal Behavioral Analysis

**What it does:** Learns the behavioral patterns of forums and actors over time, and predicts
anomalies before they manifest.

**Examples:**
- "This marketplace's posting volume dropped 40% in the last 72 hours — historically this happens
  before exit scams" → alert fires
- "This actor's posting frequency has tripled this week — historically precedes a major release"
- "This forum's admin account has been silent for 14 days — historically indicates law enforcement action"

**Implementation:**
- Time-series data from DB: posting counts, entity appearance rates, URL availability
- Anomaly detection using statistical methods (z-score, isolation forest)
- Pattern library built from historical observations

**Files to create:**
- `analysis/__init__.py`
- `analysis/temporal.py` — time-series feature extraction and anomaly detection
- `analysis/patterns.py` — pattern library and matching

### 6C — OPSEC Failure Detection

**What it does:** Automatically flags when threat actors make operational security mistakes in
their observed communications.

**OPSEC failures to detect:**
- **Timezone leak:** Post timestamps cluster around specific hours → reveals actor's timezone
- **Language switch:** Actor normally writes in Russian, one post has English idioms → possible native language reveal
- **Clearnet URL slip:** Actor posts a clearnet URL (YouTube, Reddit, personal site) in dark web context
- **PGP key reuse:** Same PGP key on clearnet and dark web → linkage attack
- **Username reuse:** Handle appears on clearnet platforms (search Google, Breach databases)
- **Consistent writing times:** Posts only appear Mon–Fri 9am–5pm UTC+3 → office worker pattern

**Files to create:**
- `analysis/opsec.py` — OPSEC failure detection rules

### 6D — Multilingual Intelligence

**What it does:** Breaks the English-only barrier. Russian, Chinese, and Arabic dark web communities
contain high-value intelligence that is almost entirely ignored by English-centric tools.

**Implementation:**
- Language detection on every scraped page (`langdetect` library)
- Translation via local model (Facebook NLLB-200) or DeepL API (fallback)
- Query expansion: when user searches "ransomware payment," also search in Russian (`выкупной платёж`),
  Chinese (`勒索软件`), etc.
- Cross-language entity matching: same wallet address appears on Russian forum and English forum →
  linked in graph regardless of page language

**Files to create:**
- `i18n/__init__.py`
- `i18n/detect.py` — language detection
- `i18n/translate.py` — translation pipeline (local model + API fallback)
- `i18n/query_expand.py` — multilingual query generation

**New env vars:**
```
DEEPL_API_KEY=           # optional, NLLB local model used if not set
NLLB_MODEL_PATH=         # path to local NLLB model weights
```

---

## Phase Summary Table

| Phase | Name | Key Deliverable | Unlocks |
|---|---|---|---|
| 0 | Baseline | Existing VoidAccess | — |
| 1 | Foundation | Persistent DB + async scraper + recursive crawler + more sources | Everything below |
| 2 | Intelligence | Structured entity extraction (wallets, handles, CVEs, etc.) | Phases 3–6 |
| 3 | Graph | Relationship mapping, actor network visualization | Phase 6A, 6B |
| 4 | Monitoring | Continuous watch jobs, change detection, vector memory | — |
| 5 | Output | STIX/TAXII, MISP, Sigma, REST API | Enterprise integration |
| 6 | Advanced | Stylometry, temporal prediction, OPSEC detection, multilingual | Beyond-commercial |

---

## Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.11+ | Already the codebase |
| Web framework | Streamlit (UI) + FastAPI (API) | Streamlit for humans, FastAPI for machines |
| Async I/O | asyncio + aiohttp-socks | Tor-compatible async HTTP |
| Database | PostgreSQL + SQLAlchemy + Alembic | Reliable, queryable, schema-versioned |
| Graph | NetworkX → Neo4j (at scale) | NetworkX = zero setup; Neo4j = production scale |
| Vector DB | ChromaDB | Fully local, no external service |
| Embeddings | sentence-transformers (local) | No API cost, runs offline |
| NER | spaCy | Fast, local, fine-tuneable |
| Browser automation | Playwright (Firefox) | JavaScript execution for bot-detection bypass |
| Scheduling | APScheduler | In-process, simple; Celery at production scale |
| Threat intel export | stix2 (Python library) | STIX 2.1 compliance |
| Telegram | Telethon | Full Telegram API access |
| Translation | NLLB-200 local / DeepL API | Offline-first, API fallback |
| Containers | Docker + docker-compose | Multi-service orchestration (app + DB + scheduler) |

---

## File Structure (End State)

```
voidaccess/
├── CLAUDE.md               ← AI coding assistant instructions
├── concept.md              ← This file
├── requirements.txt        ← Updated per phase
├── .env.example            ← Updated per phase
├── monitors.yaml           ← Watch configuration (Phase 4)
│
├── ui.py                   ← Streamlit UI (extended per phase)
├── main.py                 ← CLI entry point
├── config.py               ← Env var loading
├── health.py               ← Health checks
│
├── llm.py                  ← LLM chains (extended)
├── llm_utils.py            ← Model registry
├── search.py               ← Search engines (extended)
├── scrape.py               ← Async scraper (rewritten Phase 1B)
│
├── db/                     ← Phase 1A
│   ├── models.py
│   ├── session.py
│   ├── queries.py
│   └── migrations/
│
├── crawler/                ← Phase 1C
│   ├── spider.py
│   ├── frontier.py
│   ├── dedup.py
│   └── utils.py
│
├── sources/                ← Phase 1D
│   └── telegram.py
│
├── extractor/              ← Phase 2
│   ├── regex_patterns.py
│   ├── ner.py
│   ├── llm_extract.py
│   ├── normalizer.py
│   └── pipeline.py
│
├── graph/                  ← Phase 3
│   ├── model.py
│   ├── builder.py
│   ├── queries.py
│   ├── export.py
│   └── visualize.py
│
├── monitor/                ← Phase 4
│   ├── scheduler.py
│   ├── jobs.py
│   ├── diff.py
│   └── alerts.py
│
├── vector/                 ← Phase 4
│   ├── store.py
│   ├── embedder.py
│   └── search.py
│
├── export/                 ← Phase 5
│   ├── stix.py
│   ├── taxii.py
│   ├── misp.py
│   └── sigma.py
│
├── api/                    ← Phase 5
│   ├── main.py
│   └── routes/
│
├── fingerprint/            ← Phase 6
│   ├── stylometry.py
│   └── profiler.py
│
├── analysis/               ← Phase 6
│   ├── temporal.py
│   ├── patterns.py
│   └── opsec.py
│
├── i18n/                   ← Phase 6
│   ├── detect.py
│   ├── translate.py
│   └── query_expand.py
│
├── investigations/         ← JSON persistence (existing)
├── tests/                  ← One test file per module
└── docker-compose.yml      ← Multi-service orchestration
```

---

## What "Done" Looks Like

A security analyst opens the platform. They type "LockBit 4.0 affiliate recruitment." The system:

1. Expands the query into 6 languages, searches 12 dark web search engines simultaneously
2. Discovers 3 new `.onion` forums not in any search engine index via recursive crawling
3. Extracts 47 crypto wallet addresses, 12 threat actor handles, 3 PGP keys, 2 CVEs
4. Identifies that handle `lk_recruiter` has appeared on 4 forums and shares stylometric
   patterns with a handle from 2022 that was linked to a known actor
5. Flags an OPSEC failure: `lk_recruiter` posted at consistent times suggesting UTC+3 timezone
6. Exports a STIX bundle the analyst can feed directly into their SIEM
7. Sets up a continuous watch that will Slack-alert within 1 hour if any new content matches

That's the destination. `concept.md` is the map.
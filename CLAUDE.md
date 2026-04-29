# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.
Always refer to `concept.md` for the full vision, phased roadmap, and architectural decisions.

---

## What This Project Is (And Where It's Going)

VoidAccess started as an AI-powered dark web OSINT tool — a clean prototype that takes a user query, refines it via LLM, fans out to 16 Tor-based search engines, filters results, scrapes top pages over Tor, and generates a threat-intel summary.

**We are taking it significantly further.**

The goal is to evolve VoidAccess from a single-run investigation assistant into a persistent, autonomous, multi-source dark web intelligence platform — capable of continuous monitoring, structured entity extraction, graph-based relationship mapping, and threat intelligence outputs that comply with industry standards (STIX/TAXII, MISP). When complete, it should functionally match or exceed commercial platforms like Recorded Future, DarkOwl, and Flare — at open-source cost.

All new development follows the phased plan in `concept.md`. Before writing any new code, check which phase is active and which layer is being worked on. Do not skip phases or build out of order — each layer depends on the one before it.

---

## Running the App (Current State)

**Prerequisites:** Tor must be running. Python 3.10+.

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit UI
streamlit run ui.py
```

Navigate to `http://localhost:8501`.

**Docker (recommended for isolation):**
```bash
docker run --rm \
  -v "$(pwd)/.env:/app/.env" \
  --add-host=host.docker.internal:host-gateway \
  -p 8501:8501 \
  voidaccess/voidaccess:latest
```

---

## Configuration

Copy `.env.example` to `.env` and fill in only the keys you want to use. The app auto-detects which models are available based on which keys are present.

```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLAMA_CPP_BASE_URL=http://127.0.0.1:8080
```

As new phases are added, new env vars will appear here (database URLs, webhook endpoints, API keys for translation services, etc.). They will always be documented in this file and in `concept.md`.

---

## Current Architecture (Phase 0 — Baseline)

The existing pipeline runs in six sequential stages driven by `ui.py`:

1. **LLM init** — `llm.get_llm(model)` instantiates a LangChain chat model via `llm_utils.resolve_model_config`
2. **Query refinement** — `llm.refine_query` trims user input to ≤5 words optimized for dark web search
3. **Search** — `search.get_search_results` fans out to all 16 `.onion` search engines concurrently via Tor SOCKS5 on `127.0.0.1:9050`
4. **LLM filter** — `llm.filter_results` picks the top ≤20 relevant results by index
5. **Scrape** — `scrape.scrape_multiple` concurrently fetches and extracts text from filtered `.onion` URLs via Tor (1 MB cap, 50K char extraction, 2K chars returned per page)
6. **Summarize** — `llm.generate_summary` runs one of four preset system prompts with optional custom instructions

### Key Files (Baseline)

| File | Role |
|---|---|
| `ui.py` | Streamlit app — all pipeline orchestration and session state |
| `llm.py` | LangChain chains: `refine_query`, `filter_results`, `generate_summary`; preset prompts in `PRESET_PROMPTS` |
| `llm_utils.py` | Model registry, `get_model_choices`, `BufferedStreamingHandler` |
| `search.py` | `SEARCH_ENGINES` list, Tor session creation, concurrent result fetching |
| `scrape.py` | Thread-local Tor sessions, `scrape_single`, `scrape_multiple` |
| `config.py` | Loads and sanitizes all env vars |
| `health.py` | Sidebar health checks for Tor, LLM, search engines |

### New Files (Added Per Phase — see concept.md)

| File/Dir | Phase | Role |
|---|---|---|
| `db/` | Phase 1 | Database models, migrations, connection pool |
| `crawler/` | Phase 1 | Recursive .onion spider |
| `extractor/` | Phase 2 | Entity extraction pipeline |
| `graph/` | Phase 3 | Graph database interface and relationship engine |
| `monitor/` | Phase 4 | Scheduled jobs, change detection, alerting |
| `vector/` | Phase 4 | Embedding storage and semantic search |
| `export/` | Phase 5 | STIX/TAXII, MISP, Sigma rule generation |
| `fingerprint/` | Phase 6 | Stylometry, actor profiling, OPSEC analysis |

---

## Development Rules

- **Never break the existing pipeline.** New features are added as parallel modules, not replacements. The original 6-stage flow must always remain functional.
- **Always check `concept.md` before starting work.** It defines what to build, in what order, and why.
- **Every new module gets its own directory** with an `__init__.py` and a `README.md` explaining what it does.
- **Tests go in `tests/`** — one test file per module, named `test_<module>.py`.
- **Never hardcode credentials.** All secrets via `.env` / `config.py`.
- **Tor safety always.** All outbound requests to `.onion` addresses must go through the Tor SOCKS5 proxy. Never make clearnet requests to dark web targets.

---

## Adding a New LLM

Add an entry to `_llm_config_map` in `llm_utils.py`. The key is the display name (lowercased), the value specifies the LangChain class and constructor params. Cloud models are gated behind the corresponding API key check in `get_model_choices`.

## Adding a New Search Engine (Baseline)

Append to the `SEARCH_ENGINES` list in `search.py` with `name` and `url` (using `{query}` as placeholder). Phase 1 introduces a more powerful multi-source engine that supersedes this simple list.

## Investigation Persistence

Completed investigations are saved as JSON under `investigations/`. The sidebar "Past Investigations" panel loads them. Phase 1 moves this to a proper database while keeping JSON export as an option.
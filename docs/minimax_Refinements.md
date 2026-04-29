# VoidAccess Performance & Refinement Changes

This document details all performance optimizations and code refinements made to the VoidAccess dark web intelligence gathering tool.

---

## 1. Search Module: Blocking → Async Conversion

### What Changed
**File:** `voidaccess/search.py`

- Replaced `ThreadPoolExecutor + requests` with `asyncio + aiohttp`
- Implemented async engine fetching with concurrent execution
- Added retry logic with exponential backoff per engine

### Why
The original implementation used Python's `ThreadPoolExecutor` with blocking `requests` library. This had several problems:

1. **Thread Memory Overhead**: Each thread consumes ~1MB of memory. With 10 workers, that's 10MB just for waiting on I/O.

2. **Blocking I/O**: Threads block while waiting for Tor network responses. They can't do useful work while waiting.

3. **Sequential Thinking**: While threads run concurrently, the GIL and blocking nature meant poor utilization.

The new async implementation:
- Uses ~100 bytes per "task" instead of ~1MB per thread
- Can run 16+ concurrent engine queries with minimal memory
- Properly awaits I/O instead of blocking threads

### Code Pattern

```python
# Before (blocking)
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch, engine, query) for engine in engines]
    results = [f.result() for f in futures]

# After (async)
async def run_engine(engine):
    async with aiohttp.ClientSession() as session:
        return await _fetch_engine(engine, query, session)

results = await asyncio.gather(*[run_engine(e) for e in engines])
```

---

## 2. Scrape Module: Connection Pooling

### What Changed
**File:** `voidaccess/scrape.py`

- Added module-level cached sessions: `_tor_session`, `_direct_session`
- Created `get_tor_session_cached()` and `get_direct_session_cached()`
- Removed per-batch session creation in `_gather_all()`
- Added `close_cached_sessions()` for proper cleanup

### Why
The original code created a new `aiohttp.ClientSession` for every batch of URLs:

```python
# Before: Created fresh session per batch
async with aiohttp.ClientSession(connector=tor_connector) as tor_session:
    tasks = [_fetch_one(tor_session, item) for item in onion_urls]
    rows = await asyncio.gather(*tasks)
```

Problems:
1. **TCP Connection Overhead**: Each session creates new TCP connections. TCP handshake + TLS handshake adds ~100-300ms per connection.

2. **Tor Circuit Reuse**: New Tor circuits are created per session. Reusing sessions means reusing established circuits (more stable).

3. **Resource Waste**: Creating/destroying sessions frequently causes memory churn.

The new implementation:
- Reuses connections across requests (connection pooling)
- Sets explicit limits: 20 total, 10 per host
- Maintains circuit stability for Tor

### Code Pattern

```python
# Before
async def run_batch():
    async with aiohttp.ClientSession() as session:
        return await fetch_all(session, urls)

# After
_tor_session = None

def get_tor_session_cached():
    global _tor_session
    if _tor_session is None or _tor_session.closed:
        _tor_session = aiohttp.ClientSession(
            connector=tor_connector,
            limits=aiohttp.Limit(total=20, per_host=10),
        )
    return _tor_session

async def run_batch():
    session = get_tor_session_cached()
    return await fetch_all(session, urls)
```

---

## 3. Monitor Jobs: Lazy Imports

### What Changed
**File:** `voidaccess/monitor/jobs.py`

- Moved heavy module imports inside functions instead of module level
- Only lightweight imports (`logging`, `datetime`, `typing`) remain at module level

### Why
The original code imported heavy modules at module load time:

```python
# Before (module level)
import graph
import scrape
import search
import vector
from extractor import extract_entities_from_page
```

Problems:
1. **Slow Startup**: These modules have their own dependencies (aiohttp, BeautifulSoup, trafilatura, sentence-transformers). Importing them all takes 2-5 seconds.

2. **Memory Always Allocated**: Even if you never run monitors, these modules stay in memory.

3. **Circular Import Risk**: Heavy imports at module level increase circular dependency chances.

The new approach:
- Imports happen only when job actually runs
- If no monitors run, no heavy imports occur
- Faster `uvicorn` / FastAPI startup

### Code Pattern

```python
# Before
import scrape
import search
import vector

async def run_keyword_watch(watch, llm):
    raw_results = search.get_search_results(query)  # uses pre-imported search
    scraped = await scrape.scrape_multiple(urls_data)

# After
async def run_keyword_watch(watch, llm):
    # Imports only happen when this function is called
    import scrape
    import search
    
    raw_results = search.get_search_results(query)
    scraped = await scrape.scrape_multiple(urls_data)
```

---

## 4. API Endpoints: Pagination Support

### What Changed
**Files:**
- `voidaccess/api/routes/search.py`
- `voidaccess/vector/store.py`

- Added `offset` and `limit` parameters to search endpoints
- Semantic search now returns `{items, total, offset, n_results}`
- Entity search now returns `{items[], total, offset, limit}`
- Added `count_pages()` to vector store

### Why
Original endpoints had no pagination:

```python
# Before
entities = q.order_by(...).limit(200).all()
return entities  # No way to get next page
```

Problems:
1. **No Cursor Support**: Clients couldn't paginate through large result sets.

2. **Fixed Limit**: Hardcoded 200 limit, no flexibility.

3. **Missing Metadata**: No way to know total results without separate count query.

The new implementation:
- Client-controlled pagination via offset/limit
- Returns total count for UI (e.g., "Page 1 of 50")
- More efficient: single query with count

### Response Format

```json
// GET /search/semantic
{
  "items": [...],
  "total": 1500,
  "offset": 0,
  "n_results": 10
}

// GET /search/entities
{
  "items": [...],
  "total": 842,
  "offset": 50,
  "limit": 25
}
```

---

## 5. URL Normalization: Consolidation

### What Changed
**File:** `voidaccess/scrape.py`

- Added `normalize_url()` function that delegates to `crawler.utils.normalize_url`
- Ensures consistent URL handling across scrape and crawl modules

### Why
URL normalization was duplicated across modules:

1. `crawler/utils.py`: `normalize_url()` - used by crawler
2. `scrape.py`: Internal logic scattered, no centralized function

Problems:
1. **Inconsistent Behavior**: Different normalization rules could cause the same URL to be treated differently.

2. **Maintenance Burden**: Fixing normalization bugs requires changes in multiple places.

3. **Dedup Failures**: If normalization differs, deduplication fails and you get duplicate entries.

The fix:
- Single `normalize_url()` in scrape.py that imports from crawler/utils
- Consistent dedup across all modules

---

## Performance Impact Summary

| Change | Estimated Improvement | Metric |
|--------|----------------------|--------|
| Async search | 3-5x faster | 16 engines run concurrently |
| Connection pooling | 100-300ms saved | Per-request TCP/TLS handshake |
| Lazy imports | ~2-5s saved | Module import time at startup |
| Pagination | N/A | Enables handling large datasets |
| URL consolidation | N/A | Consistency improvement |

---

## Testing Recommendations

1. **Search Performance**: Time a search query before/after
   ```python
   import time
   start = time.monotonic()
   results = get_search_results("ransomware")
   print(f"Took {(time.monotonic() - start)*1000:.0f}ms")
   ```

2. **Memory Usage**: Monitor memory during batch scraping
   ```python
   import tracemalloc
   tracemalloc.start()
   # ... run scrape ...
   current, peak = tracemalloc.get_traced_memory()
   print(f"Peak: {peak/1024/1024:.1f}MB")
   ```

3. **Connection Reuse**: Check that sessions are reused
   ```python
   # In scrape.py, add debug logging
   print(f"Session closed: {_tor_session.closed}")
   ```

---

## Future Optimization Opportunities

1. **Embedding Model Caching**: The sentence-transformers model is loaded per-request in some paths. Could preload.

2. **Database Connection Pooling**: Add explicit SQLAlchemy pool size configuration.

3. **Circuit Breaker**: Add failure tracking for search engines - skip dead engines after N failures.

4. **Request Batching**: Group multiple small requests into batches for efficiency.

5. **Result Caching**: Cache search results for N seconds to reduce redundant Tor queries.

---

*Generated for VoidAccess v1.x Performance Audit*

# Project Context — Research Agent Interview Improvements

## What this project is
LangGraph-based multi-source research agent with a Chainlit UI.
Stack: Groq (llama-3.3-70b-versatile) + DuckDuckGo + BeautifulSoup + SQLite + Chainlit.

Pipeline: Planner → Web Search → Reconciler → Report Writer → Reflection (with retry loop)

Extra features already built: auth (bcrypt), voice STT/TTS (Groq Whisper/PlayAI),
PDF/MD export, follow-up detection, intent routing, streaming LLM responses.

---

## Changes Implemented

### 1. Structured Output with Pydantic ✅
**Files changed:** `agent/nodes.py`, `agent/prompts.py`

**What:** Replaced `_extract_json()` (regex-based JSON extraction) with LangChain's
`.with_structured_output()` backed by Pydantic models.

**Models added:**
- `PlannerOutput(sub_questions: list[str])` — used in `planner_node`
- `ReflectionOutput(complete: bool, missing: list[str])` — used in `reflection_node`

**Why it matters:** `with_structured_output` uses Groq's native tool-calling API — the
model is forced to conform to the schema rather than just asked nicely via a prompt string.
Eliminates the fragile regex fallback. This is the industry standard pattern.

---

### 2. Concurrent Async Web Scraping ✅

**Files changed:** `tools/web_search.py`, `agent/nodes.py`, `app.py`

**What:** Replaced sequential scraping with `time.sleep(1)` between each URL with
`asyncio.gather` — all URLs are fetched concurrently using a single shared
`httpx.AsyncClient`. DuckDuckGo searches for all sub-questions also run concurrently
via `asyncio.to_thread`.

**Before:** 10 sources × ~2s each = ~20s total scraping time
**After:** All 10 sources scraped in parallel = ~2-3s total

`web_search_node` is now `async def`, called directly with `await` in `app.py`
instead of wrapped in `asyncio.to_thread`.

---

## Changes Planned (Not Yet Implemented)

### 3. Unit Tests with pytest
**Files to create:** `tests/test_nodes.py`, `tests/test_web_search.py`
**What:** 10 unit tests covering:
- `PlannerOutput` / `ReflectionOutput` Pydantic validation
- `clean_text` truncation logic
- `safe_filename` edge cases
- Intent classifier output parsing
- Report prompt formatting
Use `unittest.mock` to mock the LLM — no real API calls in tests.

### 4. Dockerfile + docker-compose.yml
**Files to create:** `Dockerfile`, `docker-compose.yml`
**What:** Single-command deployment. `docker compose up` runs the app.
Shows you can ship it, not just run it locally.

### 5. LangSmith Tracing — Properly Enabled
**Files to change:** `app.py`
**What:** Set `LANGCHAIN_TRACING_V2=true` in `.env.example` and document the
LangSmith dashboard. Every research session gets a trace with token counts, latency
per node, and retry loops visible. Free tier is sufficient.

### 6. Startup Environment Validation
**Files to change:** `app.py`
**What:** Check all required env vars at startup and exit with a clear message if any
are missing. Fail fast instead of failing mid-request.
```python
required = ["GROQ_API_KEY"]
missing = [k for k in required if not os.getenv(k)]
if missing:
    sys.exit(f"Missing required env vars: {', '.join(missing)}")
```

### 7. Proper Logging (replace silent except blocks)
**Files to change:** `tools/web_search.py`
**What:** Replace `except Exception: return []` with `logging.warning(...)`.
Silent failures hide bugs. Structured logs make debugging possible in production.

### 8. PDF/Document RAG with ChromaDB (biggest feature)
**Files to create:** `tools/rag.py`, update `app.py`
**What:** Allow users to upload PDFs. Chunk them, embed with a free local model
(e.g. `sentence-transformers`), store in ChromaDB (local, free). Retrieved chunks
are injected into the report writer context alongside web results.
This is the #1 skill listed in AI engineer JDs.
**Dependencies to add:** `chromadb`, `langchain-community`, `sentence-transformers`

### 9. Evaluation Harness
**Files to create:** `scripts/eval.py`
**What:** Run 3 hardcoded research queries and score each report automatically:
- Has citations `[Source N]`?
- Has all required markdown headers?
- Is overall confidence stated?
Shows you think about LLM output quality — rare and highly valued in interviews.

### 10. .env.example
**File to create:** `.env.example`
README mentions `cp .env.example .env` but the file doesn't exist.
```
GROQ_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key_here
LANGCHAIN_PROJECT=research-agent
```

---

## Interview Talking Points

| Skill | Where in code |
|---|---|
| Agentic pipelines (LangGraph) | `agent/graph.py`, `agent/nodes.py` |
| Structured LLM output (Pydantic) | `PlannerOutput`, `ReflectionOutput` in `nodes.py` |
| Async/concurrent I/O | `tools/web_search.py` — `asyncio.gather` scraping |
| Streaming responses | `_stream_message()` in `app.py` |
| Custom data persistence | `db/database.py` — full Chainlit `BaseDataLayer` impl |
| Auth (bcrypt) | `db/database.py`, `app.py` |
| Voice (STT + TTS) | `utils/voice.py` |
| Reflection / self-correction loop | `reflection_node` in `nodes.py` |
| Conflict reconciliation | `reconciler_node` in `nodes.py` |
| PDF export | `utils/export.py` |

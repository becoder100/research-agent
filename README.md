# Multi-Source Research Agent

A LangGraph-powered research agent with a Chainlit UI. Give it a topic and it searches the web, reconciles conflicting sources, and writes a structured report with citations. Upload a PDF and it automatically decides whether to answer from the document, the web, or both.

## Features

- **Multi-source web research** — DuckDuckGo search + concurrent async scraping (no API key needed)
- **PDF / document RAG** — upload PDFs or text files; the agent indexes them and retrieves relevant chunks using local embeddings (no OpenAI needed)
- **Smart source routing** — LLM automatically decides: answer from document only, web only, or both
- **Persistent document memory** — uploaded documents survive session restarts, tied to your user account
- **Conflict reconciliation** — identifies contradicting claims across sources
- **Reflection loop** — checks its own report for gaps and retries if sub-questions are unanswered
- **Streaming responses** — report is streamed token-by-token
- **Voice input / output** — speech-to-text (Groq Whisper) and text-to-speech (PlayAI)
- **Follow-up detection** — recognises follow-up questions and answers from the previous report without re-searching
- **PDF + Markdown export** — download every report as `.pdf` or `.md`
- **Auth** — username/password login with bcrypt hashing
- **Chat history** — full conversation persistence via SQLite

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in your keys
chainlit run app.py
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Get free at console.groq.com — powers LLM + Whisper STT |
| `PLAY_AI_API_KEY` | Optional | PlayAI text-to-speech for voice summaries |
| `PLAY_AI_USER_ID` | Optional | PlayAI user ID |
| `LANGCHAIN_TRACING_V2` | Optional | Set `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | Optional | LangSmith API key |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |

## Architecture

```
User Query
    │
    ├── [Intent Classifier]     → CHAT or RESEARCH
    │
    ├── [Follow-up Classifier]  → FOLLOWUP or NEW (uses previous report if follow-up)
    │
    ├── [Source Router]         → DOC_ONLY / HYBRID / WEB_ONLY (when documents uploaded)
    │
    ▼
[Planner]           → Decomposes query into 3–5 sub-questions
    │
    ├── [Web Search]            → Concurrent DuckDuckGo + async scraping (skipped for DOC_ONLY)
    │
    ├── [Reconciler]            → Identifies conflicting claims (skipped for DOC_ONLY)
    │
    ├── [Document Retrieval]    → Semantic search over uploaded PDFs via ChromaDB (skipped for WEB_ONLY)
    │
    ▼
[Report Writer]     → Synthesizes markdown report with citations from all sources
    │
    ▼
[Reflection]        → Checks completeness, triggers retry if gaps found
    │
    ▼
Final Report  →  PDF export  →  Voice summary
```

## Stack

| Layer | Technology |
|---|---|
| LLM | Groq — `llama-3.3-70b-versatile` |
| Agent framework | LangGraph |
| UI | Chainlit |
| Web search | DuckDuckGo (ddgs) |
| Scraping | httpx + BeautifulSoup (async, concurrent) |
| Vector DB | ChromaDB (local, persistent) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (local, free) |
| PDF parsing | pypdf |
| Auth + history | SQLite + bcrypt |
| STT | Groq Whisper |
| TTS | PlayAI |
| PDF export | fpdf2 |

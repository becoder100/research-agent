# Multi-Source Research Agent

A Chainlit research assistant that uses LangChain's `ChatGroq` integration to call Groq models. Ask about a topic to get a structured, cited report based on web sources. Upload documents and the assistant can answer from those documents, the web, or both.

## Features

- **Multi-source web research** — DuckDuckGo search + concurrent async scraping (no API key needed)
- **PDF / document RAG** — upload PDF, TXT, or Markdown files; the agent indexes them and retrieves relevant chunks using local embeddings (no OpenAI needed)
- **Smart source routing** — LLM automatically decides: answer from document only, web only, or both
- **Persistent document memory** — uploaded documents survive app restarts and are stored in a per-user ChromaDB collection
- **Conflict reconciliation** — identifies contradicting claims across sources
- **Report quality check** — checks whether the report addresses its planned sub-questions; web/hybrid research can do one follow-up search and rewrite if gaps remain
- **Streaming responses** — report is streamed token-by-token
- **Voice input / output** — browser microphone input is transcribed with Groq Whisper; a Groq PlayAI TTS summary is generated after voice-initiated research when enabled
- **Follow-up detection** — recognises follow-up questions and answers from the previous report without re-searching
- **PDF + Markdown export** — download completed research reports as `.pdf` or `.md`
- **Accounts** — register with an email, username, and password; passwords are bcrypt-hashed
- **Chat history** — full conversation persistence via SQLite
- **Adjustable chat settings** — choose the maximum web sources (5–20), show/hide the reasoning trace, and enable/disable voice summaries

## Setup

```bash
# Use Python 3.11.9 (the version specified by .python-version)
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt

# Create a .env file in the project root and add at least GROQ_API_KEY.
chainlit run app.py
```

Example `.env` (there is no tracked `.env.example` file):

```env
GROQ_API_KEY=your_groq_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key_here
LANGCHAIN_PROJECT=research-agent
```

Open the local URL printed by Chainlit. Create an account from the registration page, then sign in. Allow microphone access in the browser to use voice input.

On first document upload, the local `all-MiniLM-L6-v2` embedding model is downloaded automatically; the initial download can take a while. Chat history and account data are stored in `chat_history.db`, and document vectors are stored in `chroma_db/`, relative to the directory where the app is started. Keep these paths persistent if you want to retain the data.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key used for the `ChatGroq` LLM, Whisper transcription, and PlayAI text-to-speech |
| `LANGCHAIN_TRACING_V2` | Optional | Set `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | Optional | LangSmith API key |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |

## Research workflow

```
User Query
    │
    ├── [Follow-up Classifier]  → answer from previous report if follow-up
    ├── [Intent Classifier]     → CHAT reply or RESEARCH
    ├── [Source Router]         → DOC_ONLY / HYBRID / WEB_ONLY (only if documents exist)
    │
    ▼
[Planner]           → Decomposes research query into 3–5 sub-questions
    │
    ├── [Web Search + Scraping] → DuckDuckGo searches and concurrent page scraping (skipped for DOC_ONLY)
    ├── [Reconciler]            → Checks web sources for conflicts (skipped for DOC_ONLY)
    ├── [Document Retrieval]    → Retrieves relevant uploaded-file chunks (skipped for WEB_ONLY)
    │
    ▼
[Report Writer]     → Streams a markdown report with citations and confidence levels
    ├── [Quality Check]         → For WEB_ONLY / HYBRID, can trigger one follow-up search and rewrite
    │
    ▼
Final Report  →  Markdown + PDF downloads  →  Optional voice summary for voice input
```

Document uploads are indexed for the signed-in account and reused in later sessions. The app accepts `.pdf`, `.txt`, and `.md` files; scanned PDFs without extractable text may not produce searchable chunks.

The Chainlit message handler currently calls the research nodes directly. The repository also includes a LangGraph `StateGraph` builder in `agent/graph.py`.

## Stack

| Layer | Technology |
|---|---|
| LLM client / provider | LangChain `ChatGroq` / Groq |
| LLM model | `openai/gpt-oss-120b` |
| Workflow | Chainlit orchestration and LangGraph `StateGraph` builder |
| UI | Chainlit |
| Web search | DuckDuckGo (ddgs) |
| Scraping | httpx + BeautifulSoup (async, concurrent) |
| Vector DB | ChromaDB (local, persistent) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (local, free) |
| PDF parsing | pypdf |
| Auth + history | SQLite + bcrypt |
| STT | Groq Whisper — `whisper-large-v3-turbo` |
| TTS | Groq PlayAI TTS — `playai-tts` |
| PDF export | fpdf2 |

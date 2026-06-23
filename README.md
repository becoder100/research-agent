# Multi-Source Research Agent

A LangGraph-powered research agent with a Chainlit UI that:
1. Decomposes your query into sub-questions (Groq LLM)
2. Searches the web via DuckDuckGo (no API key needed)
3. Scrapes and reads source pages (BeautifulSoup + httpx)
4. Reconciles conflicting information across sources
5. Writes a structured markdown report with citations
6. Reflects and retries if sub-questions are unanswered

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your GROQ_API_KEY in .env
chainlit run app.py
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | Get free at https://console.groq.com |
| `LANGCHAIN_TRACING_V2` | Optional | Set `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | Optional | Your LangSmith API key |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |

## Architecture

```
User Query
    │
    ▼
[Planner Node]        → Decomposes query into 3-5 sub-questions
    │
    ▼
[Web Search Node]     → DuckDuckGo search + BeautifulSoup scraping
    │
    ▼
[Reconciler Node]     → Identifies conflicting claims across sources
    │
    ▼
[Report Writer Node]  → Synthesizes markdown report with citations
    │
    ▼
[Reflection Node]     → Checks completeness, retries if needed
    │
    ▼
Final Report (Chainlit UI)
```

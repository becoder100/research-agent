
import json
import os
import re

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from agent.prompts import (
    CONVERSATIONAL_PROMPT,
    FOLLOWUP_ANSWER_PROMPT,
    FOLLOWUP_CLASSIFIER_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    PLANNER_PROMPT,
    RECONCILER_PROMPT,
    REFLECTION_PROMPT,
    REPORT_WRITER_PROMPT,
)
from agent.state import AgentState
from tools.web_search import search_and_scrape

load_dotenv()


def get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=os.getenv("GROQ_API_KEY"),
    )


def _extract_json(text: str):
    """Extract JSON from LLM response that may have surrounding text."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON array or object with regex
    match = re.search(r"(\[.*?\]|\{.*?\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def classify_intent(message: str) -> str:
    """Returns 'RESEARCH' or 'CHAT'."""
    llm = get_llm()
    prompt = INTENT_CLASSIFIER_PROMPT.format(message=message)
    response = llm.invoke(prompt)
    result = response.content.strip().upper()
    return "RESEARCH" if "RESEARCH" in result else "CHAT"


def conversational_node(message: str) -> str:
    """Generate a friendly conversational reply without web search."""
    llm = get_llm()
    prompt = CONVERSATIONAL_PROMPT.format(message=message)
    response = llm.invoke(prompt)
    return response.content.strip()


def classify_followup(message: str, last_query: str) -> str:
    """Returns 'FOLLOWUP' or 'NEW'."""
    llm = get_llm()
    prompt = FOLLOWUP_CLASSIFIER_PROMPT.format(last_query=last_query, message=message)
    result = llm.invoke(prompt).content.strip().upper()
    return "FOLLOWUP" if "FOLLOWUP" in result else "NEW"


def answer_followup(message: str, last_query: str, last_report: str) -> str:
    """Generate a focused answer to a follow-up question using the previous report as context."""
    llm = get_llm()
    prompt = FOLLOWUP_ANSWER_PROMPT.format(
        last_query=last_query,
        last_report=last_report,
        message=message,
    )
    return llm.invoke(prompt).content.strip()


def planner_node(state: AgentState) -> dict:
    llm = get_llm()
    prompt = PLANNER_PROMPT.format(query=state["query"])
    response = llm.invoke(prompt)
    content = response.content.strip()

    sub_questions = _extract_json(content)
    if not isinstance(sub_questions, list):
        # Fallback: split by newlines if JSON parse fails
        sub_questions = [
            line.strip().lstrip("-•123456789. ")
            for line in content.splitlines()
            if line.strip()
        ][:5]

    trace = list(state.get("reasoning_trace", []))
    trace.append(f"Planned sub-questions: {sub_questions}")

    return {"sub_questions": sub_questions, "reasoning_trace": trace}


def web_search_node(state: AgentState) -> dict:
    results = search_and_scrape(
        state["sub_questions"],
        max_sources=state.get("max_sources", 10),
    )

    trace = list(state.get("reasoning_trace", []))
    urls = [r["url"] for r in results]
    trace.append(f"Searched web, found {len(results)} sources: {urls}")

    return {"web_results": results, "reasoning_trace": trace}


def reconciler_node(state: AgentState) -> dict:
    web_results = state.get("web_results", [])

    sources_context = "\n\n".join(
        f"Source {i+1} ({r['url']}):\n{r['content'][:800]}"
        for i, r in enumerate(web_results)
    )

    llm = get_llm()
    prompt = RECONCILER_PROMPT.format(sources_context=sources_context)
    response = llm.invoke(prompt)
    content = response.content.strip()

    if content.lower() == "no conflicts found":
        conflicts = []
    else:
        conflicts = [line.strip() for line in content.splitlines() if line.strip()]

    trace = list(state.get("reasoning_trace", []))
    trace.append(f"Reconciliation complete, found {len(conflicts)} conflicts")

    return {"conflicts": conflicts, "reasoning_trace": trace}


def report_writer_node(state: AgentState) -> dict:
    web_results = state.get("web_results", [])
    conflicts = state.get("conflicts", [])

    sources_context = "\n\n".join(
        f"Source {i+1}. {r['title']} ({r['url']}):\n{r['content'][:1000]}"
        for i, r in enumerate(web_results)
    )

    conflicts_text = (
        "\n".join(conflicts) if conflicts else "No conflicts found"
    )

    llm = get_llm()
    prompt = REPORT_WRITER_PROMPT.format(
        query=state["query"],
        sources_context=sources_context,
        conflicts=conflicts_text,
    )
    response = llm.invoke(prompt)
    report = response.content.strip()

    trace = list(state.get("reasoning_trace", []))
    trace.append("Report written")

    return {"report": report, "status": "complete", "reasoning_trace": trace}


def reflection_node(state: AgentState) -> dict:
    iteration_count = state.get("iteration_count", 0)

    # Hard cap at 2 retries to avoid infinite loops
    if iteration_count >= 2:
        return {"status": "complete"}

    sub_questions = state.get("sub_questions", [])
    report = state.get("report", "")

    llm = get_llm()
    prompt = REFLECTION_PROMPT.format(
        sub_questions="\n".join(f"- {q}" for q in sub_questions),
        report=report,
    )
    response = llm.invoke(prompt)
    content = response.content.strip()

    result = _extract_json(content)

    if not isinstance(result, dict):
        return {"status": "complete"}

    if result.get("complete", True):
        return {"status": "complete"}

    missing = result.get("missing") or state.get("sub_questions", [])
    return {
        "status": "retry",
        "iteration_count": iteration_count + 1,
        "sub_questions": missing,
    }

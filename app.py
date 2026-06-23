import asyncio
import re
from typing import Optional

import chainlit as cl
import chainlit.data as cl_data
from chainlit.server import app as chainlit_app
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse

from agent.nodes import (
    answer_followup,
    classify_followup,
    classify_intent,
    get_llm,
    planner_node,
    reconciler_node,
    reflection_node,
    web_search_node,
)
from agent.prompts import (
    ACKNOWLEDGMENT_PROMPT,
    CONVERSATIONAL_PROMPT,
    FOLLOWUP_ANSWER_PROMPT,
    REPORT_WRITER_PROMPT,
)
from db.database import SQLiteDataLayer, init_db
from utils.export import safe_filename, to_markdown_bytes, to_pdf_bytes

load_dotenv()

# Register the SQLite data layer at module level
cl_data._data_layer = SQLiteDataLayer()

WELCOME_MESSAGE = "Hii I am your multisource research agent"


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_report_prompt(state: dict) -> str:
    web_results = state.get("web_results", [])
    conflicts = state.get("conflicts", [])
    sources_context = "\n\n".join(
        f"Source {i+1}. {r['title']} ({r['url']}):\n{r['content'][:1000]}"
        for i, r in enumerate(web_results)
    )
    conflicts_text = "\n".join(conflicts) if conflicts else "No conflicts found"
    return REPORT_WRITER_PROMPT.format(
        query=state["query"],
        sources_context=sources_context,
        conflicts=conflicts_text,
    )


async def _stream_message(prompt: str) -> str:
    """Stream any LLM prompt token-by-token. Returns the full content."""
    llm = get_llm()
    msg = cl.Message(content="")
    content = ""
    async for chunk in llm.astream(prompt):
        token = chunk.content
        content += token
        await msg.stream_token(token)
    await msg.send()
    return content


async def _name_thread(name: str) -> None:
    thread_id = cl.context.session.thread_id
    if thread_id and cl_data.get_data_layer():
        label = name[:60] + ("..." if len(name) > 60 else "")
        await cl_data.get_data_layer().update_thread(thread_id=thread_id, name=label)


async def _send_exports(report: str, query: str) -> None:
    """Attach downloadable MD and PDF versions of the report."""
    stem = safe_filename(query)
    try:
        md_bytes = to_markdown_bytes(report)
        pdf_bytes = to_pdf_bytes(report, query)
        await cl.Message(
            content="📥 **Download your report:**",
            elements=[
                cl.File(name=f"{stem}.md", content=md_bytes, mime="text/markdown"),
                cl.File(name=f"{stem}.pdf", content=pdf_bytes, mime="application/pdf"),
            ],
        ).send()
    except Exception as e:
        await cl.Message(content=f"⚠️ Export failed: {e}").send()


# ── Registration endpoint (called by /public/register.html) ────────────────

@chainlit_app.post("/api/register")
async def register_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request body"}, status_code=400)

    email    = (body.get("email")    or "").strip()
    username = (body.get("username") or "").strip()
    password =  body.get("password") or ""

    if not email or not username or not password:
        return JSONResponse({"error": "All fields are required"}, status_code=400)
    if len(username) < 3:
        return JSONResponse({"error": "Username must be at least 3 characters"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    await init_db()
    data_layer: SQLiteDataLayer = cl_data.get_data_layer()

    if await data_layer.get_user(username):
        return JSONResponse({"error": "Username already taken — choose a different one"}, status_code=400)

    user = await data_layer.get_or_register_user(username, password, email=email)
    if user:
        return JSONResponse({"success": True})
    return JSONResponse({"error": "Registration failed, please try again"}, status_code=500)


# ── Auth (login only — new users register via /public/register.html) ────────

@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> Optional[cl.User]:
    await init_db()
    data_layer: SQLiteDataLayer = cl_data.get_data_layer()

    existing = await data_layer.get_user(username)
    if not existing:
        return None  # Unknown user — direct them to register

    verified = await data_layer.verify_user(username, password)
    return cl.User(identifier=username, metadata={}) if verified else None


# ── Lifecycle ──────────────────────────────────────────────────────────────

@cl.on_chat_start
async def on_chat_start():
    await init_db()
    await cl.Message(content=WELCOME_MESSAGE).send()

    settings = await cl.ChatSettings(
        [
            cl.input_widget.Slider(
                id="Max Sources",
                label="Max Sources",
                initial=10,
                min=5,
                max=20,
                step=1,
                description="Maximum number of web sources to scrape",
            ),
            cl.input_widget.Switch(
                id="Show Reasoning Trace",
                label="Show Reasoning Trace",
                initial=True,
                description="Show the agent's internal reasoning steps",
            ),
        ]
    ).send()

    cl.user_session.set("settings", {"Max Sources": 10, "Show Reasoning Trace": True})
    cl.user_session.set("thread_named", False)
    cl.user_session.set("last_query", None)
    cl.user_session.set("last_report", None)


@cl.on_chat_resume
async def on_chat_resume(thread: cl.types.ThreadDict):
    saved = (thread.get("metadata") or {}).get("settings", {})
    cl.user_session.set("settings", {
        "Max Sources": saved.get("Max Sources", 10),
        "Show Reasoning Trace": saved.get("Show Reasoning Trace", True),
    })
    cl.user_session.set("thread_named", True)
    cl.user_session.set("last_query", None)
    cl.user_session.set("last_report", None)


@cl.on_settings_update
async def on_settings_update(settings):
    cl.user_session.set("settings", settings)
    thread_id = cl.context.session.thread_id
    if thread_id and cl_data.get_data_layer():
        await cl_data.get_data_layer().update_thread(
            thread_id=thread_id, metadata={"settings": settings}
        )


# ── Message handler ────────────────────────────────────────────────────────

@cl.on_message
async def on_message(message: cl.Message):
    query = message.content.strip()
    if not query:
        await cl.Message(content="Say something — I'm listening!").send()
        return

    settings = cl.user_session.get("settings") or {}
    max_sources = int(settings.get("Max Sources", 10))
    show_trace = settings.get("Show Reasoning Trace", True)

    # Name the thread on first message of the session
    if not cl.user_session.get("thread_named"):
        cl.user_session.set("thread_named", True)
        await _name_thread(query)

    try:
        last_query = cl.user_session.get("last_query")
        last_report = cl.user_session.get("last_report")

        # ── Feature 2: Follow-up detection ────────────────────────────────
        if last_query and last_report:
            followup_type = await asyncio.to_thread(classify_followup, query, last_query)
            if followup_type == "FOLLOWUP":
                await _stream_message(
                    FOLLOWUP_ANSWER_PROMPT.format(
                        last_query=last_query,
                        last_report=last_report,
                        message=query,
                    )
                )
                return

        # ── Intent: chat vs research ───────────────────────────────────────
        intent = await asyncio.to_thread(classify_intent, query)

        if intent == "CHAT":
            await _stream_message(CONVERSATIONAL_PROMPT.format(message=query))
            return

        # ── Research pipeline ──────────────────────────────────────────────
        await _stream_message(ACKNOWLEDGMENT_PROMPT.format(query=query))

        state = {
            "query": query,
            "sub_questions": [],
            "web_results": [],
            "conflicts": [],
            "report": "",
            "reasoning_trace": [],
            "iteration_count": 0,
            "status": "in_progress",
            "max_sources": max_sources,
        }

        # ── Step 1: Planner ────────────────────────────────────────────────
        async with cl.Step(name="🧠 Breaking this down...", type="run") as step:
            step.input = query
            state.update(await asyncio.to_thread(planner_node, state))
            n = len(state["sub_questions"])
            sub_q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(state["sub_questions"]))
            step.output = f"Got it! I'll tackle this from {n} angle{'s' if n != 1 else ''}:\n{sub_q_list}"

        # ── Step 2: Web Search ─────────────────────────────────────────────
        async with cl.Step(name="🌐 Scouring the web...", type="tool") as step:
            step.input = f"Searching {len(state['sub_questions'])} sub-questions across up to {max_sources} sources"
            state.update(await asyncio.to_thread(web_search_node, state))

            n = len(state["web_results"])
            if n == 0:
                step.output = "Hmm, couldn't find anything — might need a different angle."
                await cl.Message(
                    content=(
                        "Hmm, I came up empty on that one. It might be a very niche topic, "
                        "or there could be a connectivity hiccup on my end.\n\n"
                        "A few things to try:\n"
                        "- Rephrase the question with different keywords\n"
                        "- Make it a bit more specific or a bit more general\n"
                        "- Check your internet connection and try again"
                    )
                ).send()
                return

            url_list = "\n".join(
                f"- [{r['title'] or r['url']}]({r['url']})" for r in state["web_results"]
            )
            step.output = f"Nice! Pulled in {n} solid source{'s' if n != 1 else ''} 📚\n{url_list}"

        # ── Step 3: Reconciler ─────────────────────────────────────────────
        async with cl.Step(name="⚖️ Cross-checking sources...", type="run") as step:
            step.input = f"Comparing {len(state['web_results'])} sources for contradictions"
            state.update(await asyncio.to_thread(reconciler_node, state))

            conflicts = state.get("conflicts", [])
            if conflicts:
                conflict_text = "\n".join(f"- {c}" for c in conflicts)
                step.output = f"Heads up — found {len(conflicts)} conflict{'s' if len(conflicts) != 1 else ''} worth noting:\n{conflict_text}"
            else:
                step.output = "All sources line up — no contradictions found ✅"

        # ── Step 4: Report Writer (streamed) ───────────────────────────────
        async with cl.Step(name="✍️ Writing your report...", type="run") as step:
            step.input = "Synthesizing everything into a structured report"
            report_content = await _stream_message(_build_report_prompt(state))
            state["report"] = report_content
            state["status"] = "complete"
            trace = list(state.get("reasoning_trace", []))
            trace.append("Report written")
            state["reasoning_trace"] = trace
            step.output = "Done! Report's above 👆"

        # ── Step 5: Reflection (optional retry) ───────────────────────────
        async with cl.Step(name="🔍 Making sure nothing's missing...", type="run") as step:
            state.update(await asyncio.to_thread(reflection_node, state))
            if state.get("status") == "retry":
                step.output = "Spotted some gaps — doing a quick follow-up search..."
                async with cl.Step(name="🌐 Digging deeper...", type="tool") as step2:
                    state.update(await asyncio.to_thread(web_search_node, state))
                    step2.output = f"Found {len(state['web_results'])} sources total — filling in the gaps"
                async with cl.Step(name="✍️ Updating the report...", type="run") as step3:
                    state.update(await asyncio.to_thread(reconciler_node, state))
                    report_content = await _stream_message(_build_report_prompt(state))
                    state["report"] = report_content
                    state["status"] = "complete"
                    trace = list(state.get("reasoning_trace", []))
                    trace.append("Report updated after retry")
                    state["reasoning_trace"] = trace
                    step3.output = "Updated report's above 👆"
            else:
                step.output = "All angles covered — report is complete ✅"

        # ── Reasoning Trace ────────────────────────────────────────────────
        if show_trace and state.get("reasoning_trace"):
            async with cl.Step(name="🔬 Full Reasoning Trace", type="run") as step:
                step.output = "\n".join(
                    f"{i+1}. {entry}" for i, entry in enumerate(state["reasoning_trace"])
                )

        # ── Feature 3: Export report ───────────────────────────────────────
        await _send_exports(state["report"], state["query"])

        # ── Feature 2: Save context for follow-up detection ────────────────
        cl.user_session.set("last_query", state["query"])
        cl.user_session.set("last_report", state["report"])

    except Exception as e:
        await cl.Message(
            content=(
                f"Oof, something went wrong on my end: `{str(e)}`\n\n"
                "Try rephrasing your question, or give it another shot in a moment!"
            )
        ).send()
        raise

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite
import bcrypt
from chainlit.data import BaseDataLayer
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

DB_PATH = "chat_history.db"

# user_identifier is stored directly so Chainlit's auth check
# (thread["userIdentifier"] == user.identifier) never needs a JOIN.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    identifier    TEXT UNIQUE NOT NULL,
    email         TEXT,
    metadata      TEXT NOT NULL DEFAULT '{}',
    password_hash TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS threads (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    user_id         TEXT REFERENCES users(id),
    user_identifier TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}',
    tags            TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS steps (
    id              TEXT PRIMARY KEY,
    thread_id       TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    parent_id       TEXT,
    name            TEXT,
    type            TEXT,
    input           TEXT,
    output          TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}',
    tags            TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT,
    start_time      TEXT,
    end_time        TEXT,
    is_error        INTEGER NOT NULL DEFAULT 0,
    show_input      TEXT,
    language        TEXT,
    indent          INTEGER NOT NULL DEFAULT 0,
    streaming       INTEGER NOT NULL DEFAULT 0,
    wait_for_answer INTEGER NOT NULL DEFAULT 0,
    default_open    INTEGER NOT NULL DEFAULT 0,
    auto_collapse   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id          TEXT PRIMARY KEY,
    for_id      TEXT NOT NULL,
    thread_id   TEXT,
    value       INTEGER NOT NULL,
    comment     TEXT,
    created_at  TEXT NOT NULL
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)

        # Migration: add user_identifier column if an old DB exists without it
        try:
            await db.execute("ALTER TABLE threads ADD COLUMN user_identifier TEXT")
            await db.execute("""
                UPDATE threads
                SET user_identifier = (
                    SELECT identifier FROM users WHERE users.id = threads.user_id
                )
                WHERE user_identifier IS NULL AND user_id IS NOT NULL
            """)
        except Exception:
            pass  # Column already exists

        # Migration: add password_hash column if missing
        try:
            await db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        except Exception:
            pass  # Column already exists

        # Migration: add email column if missing
        try:
            await db.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except Exception:
            pass  # Column already exists

        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteDataLayer(BaseDataLayer):

    # ── Users ──────────────────────────────────────────────────────────────

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE identifier = ?", (identifier,)
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        return PersistedUser(
            id=row["id"],
            identifier=row["identifier"],
            metadata=json.loads(row["metadata"]),
            createdAt=row["created_at"],
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        uid = str(uuid.uuid4())
        now = _now()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, identifier, metadata, created_at) VALUES (?,?,?,?)",
                (uid, user.identifier, json.dumps(user.metadata or {}), now),
            )
            await db.commit()
        return await self.get_user(user.identifier)

    async def get_or_register_user(
        self, username: str, password: str, email: str = ""
    ) -> Optional[PersistedUser]:
        """Create a brand-new account. Caller must confirm the username doesn't exist."""
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        uid = str(uuid.uuid4())
        now = _now()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, identifier, email, metadata, password_hash, created_at) VALUES (?,?,?,?,?,?)",
                (uid, username, email or None, json.dumps({}), hashed, now),
            )
            await db.commit()
        return await self.get_user(username)

    async def verify_user(self, username: str, password: str) -> bool:
        """Return True if username exists and password matches its hash."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT password_hash FROM users WHERE identifier = ?", (username,)
            ) as cur:
                row = await cur.fetchone()
        if not row or not row["password_hash"]:
            return False
        return bcrypt.checkpw(password.encode(), row["password_hash"].encode())

    # ── Feedback ───────────────────────────────────────────────────────────

    async def upsert_feedback(self, feedback: Feedback) -> str:
        fid = feedback.id or str(uuid.uuid4())
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO feedbacks (id, for_id, thread_id, value, comment, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (fid, feedback.forId, feedback.threadId, feedback.value, feedback.comment, _now()),
            )
            await db.commit()
        return fid

    async def delete_feedback(self, feedback_id: str) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM feedbacks WHERE id = ?", (feedback_id,))
            await db.commit()
        return True

    # ── Elements (stub — not used by this agent) ───────────────────────────

    async def create_element(self, element: Any) -> None:
        pass

    async def get_element(self, thread_id: str, element_id: str) -> Optional[Dict]:
        return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None) -> None:
        pass

    # ── Steps ──────────────────────────────────────────────────────────────

    async def create_step(self, step_dict: Dict) -> None:
        sid = step_dict.get("id") or str(uuid.uuid4())
        show_input = step_dict.get("showInput")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO steps
                   (id, thread_id, parent_id, name, type, input, output, metadata, tags,
                    created_at, start_time, end_time, is_error, show_input, language,
                    indent, streaming, wait_for_answer, default_open, auto_collapse)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    step_dict.get("threadId", ""),
                    step_dict.get("parentId"),
                    step_dict.get("name", ""),
                    step_dict.get("type", ""),
                    step_dict.get("input", ""),
                    step_dict.get("output", ""),
                    json.dumps(step_dict.get("metadata") or {}),
                    json.dumps(step_dict.get("tags") or []),
                    step_dict.get("createdAt", _now()),
                    step_dict.get("start"),
                    step_dict.get("end"),
                    1 if step_dict.get("isError") else 0,
                    str(show_input) if show_input is not None else None,
                    step_dict.get("language"),
                    step_dict.get("indent", 0),
                    1 if step_dict.get("streaming") else 0,
                    1 if step_dict.get("waitForAnswer") else 0,
                    1 if step_dict.get("defaultOpen") else 0,
                    1 if step_dict.get("autoCollapse") else 0,
                ),
            )
            await db.commit()

    async def update_step(self, step_dict: Dict) -> None:
        await self.create_step(step_dict)

    async def delete_step(self, step_id: str) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM steps WHERE id = ?", (step_id,))
            await db.commit()
        return True

    async def get_favorite_steps(self, user_id: str) -> List[Dict]:
        return []

    # ── Threads ────────────────────────────────────────────────────────────

    async def get_thread_author(self, thread_id: str) -> str:
        """Returns the user's identifier (username) — used as a fallback by some Chainlit paths."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT user_identifier FROM threads WHERE id = ?", (thread_id,)
            ) as cur:
                row = await cur.fetchone()
        return (row["user_identifier"] or "") if row else ""

    async def delete_thread(self, thread_id: str) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
            await db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            await db.commit()

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        user_id = filters.userId if filters else None
        cursor = pagination.cursor
        limit = pagination.first

        where_parts: List[str] = []
        params: List[Any] = []

        if user_id:
            where_parts.append("user_id = ?")
            params.append(user_id)
        if cursor:
            where_parts.append("updated_at < ?")
            params.append(cursor)

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        params.append(limit + 1)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT * FROM threads {where_sql} ORDER BY updated_at DESC LIMIT ?",
                params,
            ) as cur:
                rows = await cur.fetchall()

        has_next = len(rows) > limit
        rows = rows[:limit]

        data: List[ThreadDict] = [
            ThreadDict(
                id=r["id"],
                createdAt=r["created_at"],
                name=r["name"] or "New Conversation",
                userId=r["user_id"],
                userIdentifier=r["user_identifier"],  # ← Chainlit auth checks this
                tags=json.loads(r["tags"]),
                metadata=json.loads(r["metadata"]),
                steps=[],
                elements=[],
            )
            for r in rows
        ]

        return PaginatedResponse(
            data=data,
            pageInfo=PageInfo(
                hasNextPage=has_next,
                startCursor=data[0]["createdAt"] if data else None,
                endCursor=rows[-1]["updated_at"] if rows else None,
            ),
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM threads WHERE id = ?", (thread_id,)
            ) as cur:
                t = await cur.fetchone()
            if not t:
                return None
            async with db.execute(
                "SELECT * FROM steps WHERE thread_id = ? ORDER BY created_at ASC",
                (thread_id,),
            ) as cur:
                step_rows = await cur.fetchall()

        steps = [
            {
                "id": s["id"],
                "threadId": s["thread_id"],
                "parentId": s["parent_id"],
                "name": s["name"],
                "type": s["type"],
                "input": s["input"] or "",
                "output": s["output"] or "",
                "metadata": json.loads(s["metadata"]),
                "tags": json.loads(s["tags"]),
                "createdAt": s["created_at"],
                "start": s["start_time"],
                "end": s["end_time"],
                "isError": bool(s["is_error"]),
                "showInput": s["show_input"],
                "language": s["language"],
                "indent": s["indent"],
                "streaming": bool(s["streaming"]),
                "waitForAnswer": bool(s["wait_for_answer"]),
                "defaultOpen": bool(s["default_open"]),
                "autoCollapse": bool(s["auto_collapse"]),
            }
            for s in step_rows
        ]

        return ThreadDict(
            id=t["id"],
            createdAt=t["created_at"],
            name=t["name"] or "New Conversation",
            userId=t["user_id"],
            userIdentifier=t["user_identifier"],  # ← Chainlit auth checks this
            tags=json.loads(t["tags"]),
            metadata=json.loads(t["metadata"]),
            steps=steps,
            elements=[],
        )

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        now = _now()

        # Resolve user_identifier from user_id so Chainlit's auth check works
        user_identifier: Optional[str] = None
        if user_id:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT identifier FROM users WHERE id = ?", (user_id,)
                ) as cur:
                    u = await cur.fetchone()
            if u:
                user_identifier = u["identifier"]

        async with aiosqlite.connect(DB_PATH) as db:
            # INSERT OR IGNORE guarantees the row exists and is safe under concurrent
            # calls (second caller silently skips instead of hitting UNIQUE error).
            # We always use safe column defaults here; the UPDATE below applies only
            # the fields the caller actually passed, so partial updates stay correct.
            await db.execute(
                """INSERT OR IGNORE INTO threads
                   (id, name, user_id, user_identifier, metadata, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    name,
                    user_id,
                    user_identifier,
                    json.dumps(metadata or {}),
                    json.dumps(tags or []),
                    now,
                    now,
                ),
            )
            # Update only the fields that were explicitly provided by the caller.
            updates: Dict[str, Any] = {"updated_at": now}
            if name is not None:
                updates["name"] = name
            if user_id is not None:
                updates["user_id"] = user_id
            if user_identifier is not None:
                updates["user_identifier"] = user_identifier
            if metadata is not None:
                updates["metadata"] = json.dumps(metadata)
            if tags is not None:
                updates["tags"] = json.dumps(tags)
            set_sql = ", ".join(f"{k} = ?" for k in updates)
            await db.execute(
                f"UPDATE threads SET {set_sql} WHERE id = ?",
                list(updates.values()) + [thread_id],
            )
            await db.commit()

    # ── Misc ───────────────────────────────────────────────────────────────

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        pass

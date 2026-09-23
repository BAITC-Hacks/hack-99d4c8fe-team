"""Small shared SQLite store for drafts, tasks and team proposals."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def database_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    return (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[1] / "data" / "iskra.db"
    )


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=15) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "CREATE TABLE IF NOT EXISTS drafts "
            "(id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS tasks "
            "(id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS responses "
            "(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE, "
            "data TEXT NOT NULL)"
        )
        yield db


def save_draft(draft_id: str, owner: str, draft: dict[str, Any]) -> None:
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO drafts VALUES (?, ?, ?)",
            (draft_id, owner, json.dumps(draft, ensure_ascii=False)),
        )


def get_draft(draft_id: str) -> tuple[str, dict[str, Any]] | None:
    with connection() as db:
        row = db.execute("SELECT owner, data FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    return (row[0], json.loads(row[1])) if row else None


def delete_draft(draft_id: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))


def save_task(task_id: str, owner: str, task: dict[str, Any]) -> None:
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO tasks VALUES (?, ?, ?)",
            (task_id, owner, json.dumps(task, ensure_ascii=False)),
        )


def get_task(task_id: str) -> tuple[str, dict[str, Any]] | None:
    with connection() as db:
        row = db.execute("SELECT owner, data FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return (row[0], json.loads(row[1])) if row else None


def list_tasks() -> list[tuple[str, dict[str, Any]]]:
    with connection() as db:
        rows = db.execute("SELECT owner, data FROM tasks ORDER BY rowid DESC").fetchall()
    return [(owner, json.loads(data)) for owner, data in rows]


def delete_task(task_id: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def add_response(response: dict[str, Any], task_id: str) -> None:
    with connection() as db:
        db.execute(
            "INSERT INTO responses VALUES (?, ?, ?)",
            (response["id"], task_id, json.dumps(response, ensure_ascii=False)),
        )


def list_responses(task_id: str) -> list[dict[str, Any]]:
    with connection() as db:
        rows = db.execute(
            "SELECT data FROM responses WHERE task_id = ? ORDER BY rowid DESC", (task_id,)
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def update_response(task_id: str, response_id: str, status: str) -> dict[str, Any] | None:
    with connection() as db:
        row = db.execute(
            "SELECT data FROM responses WHERE id = ? AND task_id = ?", (response_id, task_id)
        ).fetchone()
        if not row:
            return None
        response = json.loads(row[0])
        response["status"] = status
        db.execute(
            "UPDATE responses SET data = ? WHERE id = ?",
            (json.dumps(response, ensure_ascii=False), response_id),
        )
    return response

"""F migration acceptance: populated E data survives additive project-memory tables."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _upgrade(path: Path, revision: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_populated_e_upgrade_preserves_conversation_and_adds_memory_tables(tmp_path: Path) -> None:
    path = tmp_path / "populated-e.db"
    _upgrade(path, "e3a6f7b8c9d0")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO projects "
            "(id,name,description,entity_count,relation_count,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("p", "项目", "", 0, 0, "2026-09-18", "2026-09-18"),
        )
        connection.execute(
            "INSERT INTO conversations "
            "(id,project_id,title,summary,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            ("c", "p", "会话", "旧摘要", "2026-09-18", "2026-09-18"),
        )
        connection.execute(
            "INSERT INTO messages (id,conversation_id,role,context_key,content,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("m", "c", "user", "author", "保留原文", "2026-09-18"),
        )
        connection.commit()

    _upgrade(path, "head")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT title,summary FROM conversations WHERE id='c'"
        ).fetchone() == ("会话", "旧摘要")
        assert connection.execute("SELECT content FROM messages WHERE id='m'").fetchone() == (
            "保留原文",
        )
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "agent_project_memories",
            "agent_project_memory_sources",
            "agent_project_memory_tombstones",
        } <= tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "f4b7c8d9e0a1",
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

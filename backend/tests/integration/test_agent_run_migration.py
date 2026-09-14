"""D migration acceptance: populated C data survives additive durable-run tables."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


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


def test_populated_c_upgrade_preserves_messages_and_adds_run_constraints(tmp_path: Path) -> None:
    path = tmp_path / "populated-c.db"
    _upgrade(path, "c184d5e6f7a8")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO projects "
            "(id,name,description,entity_count,relation_count,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("p", "项目", "", 0, 0, "2026-09-14 00:00:00", "2026-09-14 00:00:00"),
        )
        connection.execute(
            "INSERT INTO conversations "
            "(id,project_id,title,summary,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            ("c", "p", "会话", "", "2026-09-14 00:00:00", "2026-09-14 00:00:00"),
        )
        connection.execute(
            "INSERT INTO messages (id,conversation_id,role,context_key,content,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("m", "c", "user", "author", "保留原文", "2026-09-14 00:00:00"),
        )
        connection.commit()

    _upgrade(path, "d295e6f7a8b9")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT content,run_id FROM messages WHERE id='m'"
        ).fetchone() == ("保留原文", None)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"agent_runs", "agent_run_events"} <= tables
        connection.execute(
            "INSERT INTO agent_runs "
            "(id,conversation_id,project_id,request_id,user_message_id,perspective,character_id,"
            "status,cancel_requested,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("r1", "c", "p", "req-1", "m", "author", "", "running", 0, "2026-09-14"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO agent_runs "
                "(id,conversation_id,project_id,request_id,user_message_id,perspective,character_id,"
                "status,cancel_requested,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("r2", "c", "p", "req-2", "m", "author", "", "queued", 0, "2026-09-14"),
            )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_fresh_d_migration_has_one_head(tmp_path: Path) -> None:
    path = tmp_path / "fresh-d.db"
    _upgrade(path, "head")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "d295e6f7a8b9",
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

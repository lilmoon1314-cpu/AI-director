"""R2 migration acceptance: an inhabited R1 database upgrades without data loss."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
R1_HEAD = "a8f3c1d6e2b4"
R2_HEAD = "4da706c0d824"
R2_TABLES = {
    "artifacts",
    "artifact_blocks",
    "artifact_revisions",
    "artifact_block_revisions",
    "artifact_dependencies",
}


def _upgrade(database_path: Path, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Alembic upgrade to {revision} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def test_r1_data_survives_upgrade_to_r2(tmp_path: Path) -> None:
    database_path = tmp_path / "r1-to-r2.db"
    _upgrade(database_path, R1_HEAD)

    timestamp = "2026-09-11 00:00:00+00:00"
    with sqlite3.connect(database_path) as connection:
        pre_r2_tables = _table_names(connection)
        assert {
            "projects",
            "conversations",
            "messages",
            "memory_docs",
            "memory_doc_sections",
            "agent_pending_writes",
        }.issubset(pre_r2_tables)
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("project-r2-upgrade", "Upgrade fixture", "pre-R2", 0, 0, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "conv-r2-upgrade",
                "project-r2-upgrade",
                "Existing conversation",
                "Existing summary",
                None,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """INSERT INTO messages
               (id, conversation_id, role, content, created_at, reasoning,
                prompt_tokens, completion_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "msg-r2-upgrade",
                "conv-r2-upgrade",
                "user",
                "Existing message",
                timestamp,
                "Existing reasoning",
                7,
                11,
            ),
        )
        connection.execute(
            "INSERT INTO memory_docs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "doc-r2-upgrade",
                "project-r2-upgrade",
                "guide",
                "Existing guide",
                1,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO memory_doc_sections VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "section-r2-upgrade",
                "doc-r2-upgrade",
                0,
                "Existing section",
                "Existing memory",
                "user",
                1,
                timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO agent_pending_writes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "pending-r2-upgrade",
                "conv-r2-upgrade",
                "project-r2-upgrade",
                "write_doc_section",
                "{}",
                "{}",
                "pending",
                timestamp,
            ),
        )
        connection.commit()

    _upgrade(database_path, "head")

    with sqlite3.connect(database_path) as connection:
        post_r2_tables = _table_names(connection)
        assert pre_r2_tables.issubset(post_r2_tables), (
            f"R2 upgrade removed pre-R2 tables: {sorted(pre_r2_tables - post_r2_tables)}"
        )
        assert R2_TABLES.issubset(post_r2_tables), (
            f"R2 upgrade did not create tables: {sorted(R2_TABLES - post_r2_tables)}"
        )
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R2_HEAD,
        )
        assert connection.execute(
            "SELECT name, description FROM projects WHERE id = ?", ("project-r2-upgrade",)
        ).fetchone() == ("Upgrade fixture", "pre-R2")
        assert connection.execute(
            "SELECT title, summary FROM conversations WHERE id = ?", ("conv-r2-upgrade",)
        ).fetchone() == ("Existing conversation", "Existing summary")
        assert connection.execute(
            "SELECT content, reasoning, prompt_tokens, completion_tokens "
            "FROM messages WHERE id = ?",
            ("msg-r2-upgrade",),
        ).fetchone() == ("Existing message", "Existing reasoning", 7, 11)
        assert connection.execute(
            "SELECT title, version FROM memory_docs WHERE id = ?", ("doc-r2-upgrade",)
        ).fetchone() == ("Existing guide", 1)
        assert connection.execute(
            "SELECT content, version FROM memory_doc_sections WHERE id = ?",
            ("section-r2-upgrade",),
        ).fetchone() == ("Existing memory", 1)
        assert connection.execute(
            "SELECT kind, status FROM agent_pending_writes WHERE id = ?",
            ("pending-r2-upgrade",),
        ).fetchone() == ("write_doc_section", "pending")

"""Upgrade a populated R6 database copy, preserving every preexisting column and row."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def upgrade(path, revision):
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


def test_populated_partition_upgrade_preserves_all_existing_data(tmp_path):
    source = tmp_path / "r6.db"
    target = tmp_path / "upgrade-copy.db"
    upgrade(source, "f63c8db205a9")
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA foreign_keys=ON")

        def insert(table, **overrides):
            values = {}
            for _, name, datatype, required, default, primary in connection.execute(
                f'PRAGMA table_info("{table}")'
            ):
                if name in overrides:
                    values[name] = overrides[name]
                elif default is not None or (not required and not primary):
                    continue
                elif "INT" in datatype or "BOOL" in datatype:
                    values[name] = 1
                elif "DATE" in datatype:
                    values[name] = "2026-09-13 00:00:00"
                elif "JSON" in datatype:
                    values[name] = "{}"
                else:
                    values[name] = f"保留原文-{table}-{name}"
            placeholders = ",".join("?" for _ in values)
            connection.execute(
                f'INSERT INTO "{table}" ({",".join(values)}) VALUES ({placeholders})',
                tuple(values.values()),
            )

        insert("projects", id="p")
        insert(
            "conversations", id="c", project_id="p", summary="作者秘密摘要", summary_until_id="m"
        )
        insert("messages", id="m", conversation_id="c", role="user", content="作者秘密原文")
        insert("memory_docs", id="d", project_id="p", kind="style", version=7)
        insert("memory_doc_sections", id="s", doc_id="d", version=9)
        insert(
            "agent_pending_writes",
            id="pending",
            project_id="p",
            conversation_id="c",
            kind="write_doc_section",
            payload_json='{"doc_id":"d"}',
            baseline_json='{"section_id":"s","expected_version":9}',
            status="pending",
        )
        insert("artifacts", id="a", project_id="p")
        insert("artifact_revisions", id="rev", artifact_id="a", revision_no=1)
        insert("execution_runs", id="run", project_id="p")
        insert("skill_candidates", id="candidate", project_id="p", run_id="run", status="pending")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        connection.commit()
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'"
            )
        ]
        snapshot = {
            table: (
                [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')],
                connection.execute(f'SELECT * FROM "{table}"').fetchall(),
            )
            for table in tables
        }
        with sqlite3.connect(target) as copy:
            connection.backup(copy)
    upgrade(target, "b071c2d3e4f5")
    with sqlite3.connect(target) as connection:
        for table, (columns, rows) in snapshot.items():
            actual = connection.execute(f'SELECT {",".join(columns)} FROM "{table}"').fetchall()
            assert actual == rows, table
        assert connection.execute("SELECT context_key FROM messages").fetchall() == [("author",)]
        assert connection.execute("SELECT * FROM agent_conversation_partitions").fetchall() == []
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    # The source backup also remains unchanged at the R6 schema.
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "f63c8db205a9",
        )


def test_fresh_partition_migration(tmp_path):
    path = tmp_path / "fresh.db"
    upgrade(path, "b071c2d3e4f5")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "b071c2d3e4f5",
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

"""C migration acceptance: fresh and populated B databases remain intact."""

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


def test_populated_b_upgrade_adds_safe_confirmation_defaults(tmp_path: Path) -> None:
    path = tmp_path / "populated.db"
    _upgrade(path, "b071c2d3e4f5")
    with sqlite3.connect(path) as connection:

        def insert(table: str, **overrides: object) -> None:
            values: dict[str, object] = {}
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
                    values[name] = "2026-09-14 00:00:00"
                elif "JSON" in datatype:
                    values[name] = "{}"
                else:
                    values[name] = f"保留-{table}-{name}"
            placeholders = ",".join("?" for _ in values)
            connection.execute(
                f'INSERT INTO "{table}" ({",".join(values)}) VALUES ({placeholders})',
                tuple(values.values()),
            )

        insert("projects", id="p", name="项目")
        insert("entities", id="e", type="character", project_id="p", name="角色")
        insert("conversations", id="c", project_id="p", title="会话")
        insert(
            "agent_pending_writes",
            id="pw",
            conversation_id="c",
            project_id="p",
            kind="create_entity",
            payload_json="{}",
            status="pending",
        )
        insert("execution_runs", id="run", project_id="p", status="completed")
        insert(
            "skill_candidates",
            id="cand",
            project_id="p",
            run_id="run",
            status="pending",
        )
        connection.commit()

    _upgrade(path, "c184d5e6f7a8")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM entities WHERE id='e'").fetchone() == (1,)
        assert connection.execute(
            "SELECT result_json FROM agent_pending_writes WHERE id='pw'"
        ).fetchone() == (None,)
        assert connection.execute(
            "SELECT base_revision_id FROM skill_candidates WHERE id='cand'"
        ).fetchone() == (None,)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_fresh_c_migration_has_one_head(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    _upgrade(path, "c184d5e6f7a8")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "c184d5e6f7a8",
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

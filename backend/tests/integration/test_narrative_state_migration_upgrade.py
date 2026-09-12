"""R3 migration acceptance for fresh and populated R2 databases."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
R2_HEAD = "4da706c0d824"
R3_HEAD = "7c91e2ab4f30"
R3_TABLES = {
    "narrative_timepoints",
    "state_events",
    "state_current",
    "state_snapshots",
    "claims",
    "knowledge_states",
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


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def test_populated_r2_upgrade_preserves_data_and_backfills_selected_state(tmp_path: Path) -> None:
    database_path = tmp_path / "r2-to-r3.db"
    _upgrade(database_path, R2_HEAD)
    timestamp = "2026-09-12 00:00:00+00:00"
    with sqlite3.connect(database_path) as connection:
        pre_r3_tables = _tables(connection)
        connection.execute(
            """INSERT INTO projects
               (id, name, description, entity_count, relation_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("project-r3-upgrade", "R3 upgrade", "inhabited", 2, 2, timestamp, timestamp),
        )
        for entity_id, name in (("char-r3-a", "A"), ("char-r3-b", "B")):
            connection.execute(
                """INSERT INTO entities
                   (id, type, project_id, name, aliases, description, audience_known,
                    properties, created_at, updated_at)
                   VALUES (?, 'character', ?, ?, '[]', '', 0, '{}', ?, ?)""",
                (entity_id, "project-r3-upgrade", name, timestamp, timestamp),
            )
        connection.execute(
            """INSERT INTO relationships
               (id, project_id, source, target, type, trust, resentment, known_by,
                audience_known, properties, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, '[]', 0, '{}', ?, ?)""",
            (
                "rel-r3-valued",
                "project-r3-upgrade",
                "char-r3-a",
                "char-r3-b",
                "ally",
                0.7,
                0.2,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """INSERT INTO relationships
               (id, project_id, source, target, type, known_by, audience_known,
                properties, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, '[]', 0, '{}', ?, ?)""",
            (
                "rel-r3-empty",
                "project-r3-upgrade",
                "char-r3-b",
                "char-r3-a",
                "rival",
                timestamp,
                timestamp,
            ),
        )
        connection.commit()

    _upgrade(database_path, "head")

    with sqlite3.connect(database_path) as connection:
        assert pre_r3_tables.issubset(_tables(connection))
        assert R3_TABLES.issubset(_tables(connection))
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R3_HEAD,
        )
        assert connection.execute(
            "SELECT trust, resentment FROM relationships WHERE id='rel-r3-valued'"
        ).fetchone() == (0.7, 0.2)
        assert connection.execute(
            """SELECT attribute_key, after_json, cause_type, cause_ref
               FROM state_events ORDER BY attribute_key"""
        ).fetchall() == [
            ("resentment", 0.2, "migration", "r3_relationship_state_baseline"),
            ("trust", 0.7, "migration", "r3_relationship_state_baseline"),
        ]
        assert connection.execute(
            """SELECT attribute_key, value_json, version
               FROM state_current ORDER BY attribute_key"""
        ).fetchall() == [("resentment", 0.2, 1), ("trust", 0.7, 1)]
        assert connection.execute("SELECT count(*) FROM narrative_timepoints").fetchone() == (1,)


def test_fresh_database_reaches_r3_head(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh-r3.db"
    _upgrade(database_path, "head")
    with sqlite3.connect(database_path) as connection:
        assert R3_TABLES.issubset(_tables(connection))
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R3_HEAD,
        )

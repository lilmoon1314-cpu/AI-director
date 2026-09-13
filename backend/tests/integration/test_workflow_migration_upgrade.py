"""R4 migration acceptance for fresh and populated R3 databases."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

R3_HEAD = "7c91e2ab4f30"
R4_HEAD = "d8410ca2e6b7"
R4_TABLES = {
    "requirement_specs",
    "workflow_series",
    "episodes",
    "scene_plans",
    "workflow_gates",
    "execution_runs",
    "execution_steps",
}
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _upgrade(path: Path, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def test_populated_r3_upgrade_preserves_existing_rows(tmp_path: Path) -> None:
    path = tmp_path / "r3-to-r4.db"
    _upgrade(path, R3_HEAD)
    stamp = "2026-09-12 00:00:00+00:00"
    with sqlite3.connect(path) as connection:
        before = _tables(connection)
        connection.execute(
            "INSERT INTO projects "
            "(id,name,description,entity_count,relation_count,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("project-r4", "R4", "preserve", 0, 0, stamp, stamp),
        )
        connection.commit()
    _upgrade(path, R4_HEAD)
    with sqlite3.connect(path) as connection:
        assert before.issubset(_tables(connection))
        assert R4_TABLES.issubset(_tables(connection))
        assert connection.execute(
            "SELECT name,description FROM projects WHERE id='project-r4'"
        ).fetchone() == ("R4", "preserve")
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R4_HEAD,
        )


def test_fresh_database_reaches_r4_head(tmp_path: Path) -> None:
    path = tmp_path / "fresh-r4.db"
    _upgrade(path, R4_HEAD)
    with sqlite3.connect(path) as connection:
        assert R4_TABLES.issubset(_tables(connection))
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R4_HEAD,
        )

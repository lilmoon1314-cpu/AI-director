"""R6 fresh/populated R5 migration acceptance."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
R5_HEAD = "e52b7a91f4c8"
R6_HEAD = "f63c8db205a9"


def _upgrade(path: Path, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_populated_r5_upgrade_preserves_production_data(tmp_path: Path) -> None:
    path = tmp_path / "r5-r6.db"
    _upgrade(path, R5_HEAD)
    stamp = "2026-09-12 00:00:00+00:00"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?,?)", ("p", "P", "", 0, 0, stamp, stamp)
        )
        connection.commit()
    _upgrade(path, R6_HEAD)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name FROM projects WHERE id='p'").fetchone() == ("P",)
        assert "skill_candidates" in {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R6_HEAD,
        )


def test_fresh_database_reaches_r6_head(tmp_path: Path) -> None:
    path = tmp_path / "fresh-r6.db"
    _upgrade(path, R6_HEAD)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R6_HEAD,
        )

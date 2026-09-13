"""R5 fresh/populated R4 migration acceptance."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
R4_HEAD = "d8410ca2e6b7"
R5_HEAD = "e52b7a91f4c8"


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


def test_populated_r4_upgrade_preserves_artifact_content(tmp_path: Path) -> None:
    path = tmp_path / "r4-r5.db"
    _upgrade(path, R4_HEAD)
    stamp = "2026-09-12 00:00:00+00:00"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?,?)", ("p", "P", "", 0, 0, stamp, stamp)
        )
        connection.execute(
            "INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?)",
            ("a", "p", "screenplay", "A", "draft", 1, stamp, stamp),
        )
        connection.execute(
            "INSERT INTO artifact_blocks VALUES (?,?,?,?)", ("b", "a", "action", stamp)
        )
        connection.execute("INSERT INTO artifact_revisions VALUES (?,?,?,?)", ("r", "a", 1, stamp))
        connection.execute(
            "INSERT INTO artifact_block_revisions VALUES (?,?,?,?,?)", ("br", "r", "b", 0, "keep")
        )
        connection.commit()
    _upgrade(path, R5_HEAD)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT content,semantic_json FROM artifact_block_revisions"
        ).fetchone() == ("keep", None)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R5_HEAD,
        )


def test_fresh_r5_has_production_table(tmp_path: Path) -> None:
    path = tmp_path / "fresh-r5.db"
    _upgrade(path, R5_HEAD)
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "production_documents" in tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            R5_HEAD,
        )

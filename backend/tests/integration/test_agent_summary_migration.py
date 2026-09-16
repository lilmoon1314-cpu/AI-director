"""E migration acceptance: populated D data survives additive summary metadata."""

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


def test_populated_d_upgrade_preserves_original_messages_and_adds_summary_audit(tmp_path: Path):
    path = tmp_path / "populated-d.db"
    _upgrade(path, "d295e6f7a8b9")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO projects "
            "(id,name,description,entity_count,relation_count,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("p", "项目", "", 0, 0, "2026-09-14", "2026-09-14"),
        )
        connection.execute(
            "INSERT INTO conversations "
            "(id,project_id,title,summary,summary_until_id,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("c", "p", "会话", "旧摘要", "m", "2026-09-14", "2026-09-14"),
        )
        connection.execute(
            "INSERT INTO messages (id,conversation_id,role,context_key,content,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("m", "c", "user", "author", "不可删除的原文", "2026-09-14"),
        )
        connection.commit()

    _upgrade(path, "head")
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT summary,summary_until_id,summary_version_id FROM conversations WHERE id='c'"
        ).fetchone() == ("旧摘要", "m", None)
        assert connection.execute("SELECT content FROM messages WHERE id='m'").fetchone() == (
            "不可删除的原文",
        )
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "e3a6f7b8c9d0",
        )
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

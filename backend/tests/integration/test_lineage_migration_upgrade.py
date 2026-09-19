"""Inhabited V4-R1 → R2 upgrade preserves snapshots, legacy facts, and unrelated tables."""

import sqlite3

from tests.integration.test_artifact_migration_upgrade import _table_names, _upgrade


def test_populated_lineage_upgrade_preserves_history(tmp_path):
    database = tmp_path / "inhabited.db"
    _upgrade(database, "f4b7c8d9e0a1")
    stamp = "2026-09-19 09:00:00"
    with sqlite3.connect(database) as db:
        before = _table_names(db)
        db.execute(
            "INSERT INTO projects "
            "(id,name,description,entity_count,relation_count,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("p", "Existing project", "Preserve", 0, 0, stamp, stamp),
        )
        for aid, status in [("source", "draft"), ("dependent", "stale"), ("unrelated", "draft")]:
            db.execute(
                "INSERT INTO artifacts "
                "(id,project_id,type,title,status,current_revision_no,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (aid, "p", "screenplay", aid, status, 1, stamp, stamp),
            )
            db.execute(
                "INSERT INTO artifact_blocks (id,artifact_id,block_type,created_at) "
                "VALUES (?,?,?,?)",
                (aid + "-block", aid, "action", stamp),
            )
            db.execute(
                "INSERT INTO artifact_revisions (id,artifact_id,revision_no,created_at) "
                "VALUES (?,?,?,?)",
                (aid + "-rev", aid, 1, stamp),
            )
            db.execute(
                "INSERT INTO artifact_block_revisions "
                "(id,revision_id,block_id,position,content,semantic_json) VALUES (?,?,?,?,?,?)",
                (
                    aid + "-snapshot",
                    aid + "-rev",
                    aid + "-block",
                    0,
                    "Original " + aid,
                    '{"duration_ms":1000}',
                ),
            )
        for aid, stale in [("dependent", 1), ("unrelated", 0)]:
            db.execute(
                "INSERT INTO artifact_dependencies VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "dep-" + aid,
                    "p",
                    "source",
                    "source-block",
                    "source-rev",
                    aid,
                    "derived_from",
                    stale,
                    stamp,
                    stamp,
                ),
            )
        # Source has advanced since the dependency baseline; preserve both snapshots.
        db.execute('UPDATE artifacts SET current_revision_no=2 WHERE id="source"')
        db.execute(
            "INSERT INTO artifact_revisions VALUES (?,?,?,?)", ("source-rev2", "source", 2, stamp)
        )
        db.execute(
            "INSERT INTO artifact_block_revisions VALUES (?,?,?,?,?,?)",
            ("source-snapshot2", "source-rev2", "source-block", 0, "Changed source", "{}"),
        )
        preserved = {
            table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in (
                "artifact_dependencies",
                "artifact_revisions",
                "artifact_block_revisions",
                "projects",
            )
        }
        db.commit()
    _upgrade(database, "a5557d421f40")
    _upgrade(database, "head")  # repeated upgrade is a no-op
    with sqlite3.connect(database) as db:
        assert before <= _table_names(db)
        for table, records in preserved.items():
            assert db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() == records
        assert db.execute(
            "SELECT id,approval_status,status,current_revision_no FROM artifacts ORDER BY id"
        ).fetchall() == [
            ("dependent", "draft", "stale", 1),
            ("source", "draft", "draft", 2),
            ("unrelated", "draft", "draft", 1),
        ]
        assert db.execute(
            "SELECT id,upstream_revision_ref,downstream_revision_ref,state,stale_cause_ref "
            "FROM lineage_edges ORDER BY id"
        ).fetchall() == [
            ("dep-dependent", "source-rev", "dependent-rev", "stale", "source-rev"),
            ("dep-unrelated", "source-rev", "unrelated-rev", "active", None),
        ]
        assert not db.execute("PRAGMA foreign_key_check").fetchall()

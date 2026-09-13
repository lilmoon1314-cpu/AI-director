"""R6 Atomic Skill registry contract checks."""

import json
from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.skills.registry import SkillRegistry


def _package(root: Path, name: str, skill_id: str, validator: str = "output_schema") -> None:
    directory = root / name
    (directory / "examples").mkdir(parents=True)
    (directory / "skill.yaml").write_text(
        json.dumps(
            {
                "id": skill_id,
                "scope": "project",
                "context": {"required": [], "optional": []},
                "writes": [],
                "forbidden": [],
                "validators": [validator],
                "commit_action": "none",
            }
        ),
        encoding="utf-8",
    )
    for filename in ("input.schema.json", "output.schema.json"):
        (directory / filename).write_text('{"type":"object","properties":{}}', encoding="utf-8")
    (directory / "prompt.md").write_text("bounded", encoding="utf-8")
    (directory / "validators.py").write_text("VALIDATORS=()", encoding="utf-8")
    (directory / "examples" / "example.json").write_text("{}", encoding="utf-8")


def test_registry_rejects_missing_files_duplicate_ids_and_unknown_validator(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    missing.mkdir()
    (missing / "skill.yaml").write_text('{"id":"bad"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        SkillRegistry(tmp_path)

    duplicate_root = tmp_path / "duplicates"
    _package(duplicate_root, "a", "same")
    _package(duplicate_root, "b", "same")
    with pytest.raises(ValidationError):
        SkillRegistry(duplicate_root)

    unknown_root = tmp_path / "unknown"
    _package(unknown_root, "a", "unknown", "does_not_exist")
    with pytest.raises(ValidationError):
        SkillRegistry(unknown_root)

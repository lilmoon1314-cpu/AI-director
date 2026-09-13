"""Filesystem-backed Atomic Skill contract registry."""

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import ValidationError

KNOWN_VALIDATORS = {"output_schema", "facts_preserved", "protected_spans_unchanged"}
KNOWN_ACTIONS = {"none", "edit_block", "create_production_document"}
REQUIRED_FILES = {
    "skill.yaml",
    "prompt.md",
    "input.schema.json",
    "output.schema.json",
    "validators.py",
    "examples/example.json",
}


@dataclass(frozen=True)
class SkillContract:
    id: str
    scope: str
    required_context: tuple[str, ...]
    optional_context: tuple[str, ...]
    denied_context: tuple[str, ...]
    writes: tuple[str, ...]
    forbidden: tuple[str, ...]
    validators: tuple[str, ...]
    commit_action: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]


class SkillRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[3] / "skills"
        self._contracts = self._load()

    def _error(self, cause: str) -> ValidationError:
        return ValidationError(
            problem="Atomic Skill contract 无效",
            cause=cause,
            fix="修正对应 skill 目录的 manifest/schema/files",
        )

    def _load(self) -> dict[str, SkillContract]:
        contracts: dict[str, SkillContract] = {}
        for manifest_path in sorted(self.root.glob("**/skill.yaml")):
            directory = manifest_path.parent
            missing = [name for name in REQUIRED_FILES if not (directory / name).exists()]
            if missing:
                raise self._error(f"{directory} 缺少 {missing}")
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            skill_id = str(raw.get("id", ""))
            if not skill_id or skill_id in contracts:
                raise self._error(f"skill id 为空或重复: {skill_id!r}")
            validators = tuple(str(item) for item in raw.get("validators", []))
            unknown = set(validators) - KNOWN_VALIDATORS
            action = str(raw.get("commit_action", "none"))
            if unknown or action not in KNOWN_ACTIONS:
                raise self._error(
                    f"{skill_id} unknown validators={sorted(unknown)} action={action}"
                )
            contracts[skill_id] = SkillContract(
                id=skill_id,
                scope=str(raw["scope"]),
                required_context=tuple(raw.get("context", {}).get("required", [])),
                optional_context=tuple(raw.get("context", {}).get("optional", [])),
                denied_context=tuple(raw.get("context", {}).get("denied", [])),
                writes=tuple(raw.get("writes", [])),
                forbidden=tuple(raw.get("forbidden", [])),
                validators=validators,
                commit_action=action,
                input_schema=json.loads(
                    (directory / "input.schema.json").read_text(encoding="utf-8")
                ),
                output_schema=json.loads(
                    (directory / "output.schema.json").read_text(encoding="utf-8")
                ),
            )
        if not contracts:
            raise self._error(f"{self.root} 未发现 skill.yaml")
        return contracts

    def get(self, skill_id: str) -> SkillContract:
        try:
            return self._contracts[skill_id]
        except KeyError as exc:
            raise ValidationError(
                problem="Atomic Skill 未注册",
                cause=f"unknown id '{skill_id}'",
                fix="先读取 GET /api/skills",
            ) from exc

    def list(self) -> list[SkillContract]:
        return [self._contracts[key] for key in sorted(self._contracts)]


registry = SkillRegistry()

"""Architecture checks for the repository Harness ownership model."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.architecture


def _legacy_markdown_paths() -> list[Path]:
    """Return the bounded set of compatibility routes retained after R0."""
    legacy = [
        ROOT / "CONSTRAINTS.md",
        ROOT / "DESIGN.md",
        ROOT / "docs" / "INIT.md",
        ROOT / "docs" / "features.md",
        ROOT / "docs" / "testing.md",
        ROOT / "docs" / "architecture_checks.md",
        ROOT / "docs" / "lessons.md",
        ROOT / "docs" / "data_struct_define.md",
        ROOT / "backend" / "ARCHITECTURE.md",
        ROOT / "backend" / "CONSTRAINTS.md",
        ROOT / "frontend" / "ARCHITECTURE.md",
        ROOT / "frontend" / "CONSTRAINTS.md",
    ]
    legacy.extend((ROOT / "backend" / "app").glob("*/ARCHITECTURE.md"))
    legacy.extend((ROOT / "backend" / "app").glob("*/CONSTRAINTS.md"))
    legacy.extend((ROOT / "docs" / "tests").glob("F*.md"))
    return legacy


def test_agents_is_a_bounded_constitution_without_session_rituals() -> None:
    """The always-on constitution stays bounded and does not restore retired default fan-out."""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(agents.encode("utf-8")) <= 7000, (
        "AGENTS.md must remain a bounded repository constitution and routing map"
    )
    retired_defaults = (
        r"每次会话",
        r"read .*PROGRESS\.md",
        r"read .*DECISIONS\.md",
        r"session (?:start|end).*make check",
        r"per-feature mandatory",
    )
    for pattern in retired_defaults:
        assert re.search(pattern, agents, flags=re.IGNORECASE) is None, (
            f"AGENTS.md restored a retired default: {pattern}"
        )


def test_repository_has_no_nested_agent_instructions() -> None:
    """Only the repository-root AGENTS.md may be auto-discovered as project instructions."""
    found: list[Path] = []
    ignored_directories = {".git", ".venv", "node_modules", ".pnpm-store"}
    for directory, children, files in os.walk(ROOT):
        children[:] = [child for child in children if child not in ignored_directories]
        for name in ("AGENTS.md", "AGENTS.override.md"):
            if name in files:
                found.append(Path(directory) / name)
    assert found == [ROOT / "AGENTS.md"], f"nested repository instructions found: {found}"


def test_feature_state_routes_resolve() -> None:
    """Every feature has valid state and any product-spec route points to a real owner."""
    data = json.loads((ROOT / "feature_list.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert "acceptance evidence only" in data["status_semantics"]
    assert "task execution" in data["status_semantics"]
    ids = [feature["id"] for feature in data["features"]]
    assert len(ids) == len(set(ids)), "feature IDs must be unique"
    for feature in data["features"]:
        assert feature["status"] in {"not_started", "passing", "failing"}
        assert feature["verification"]["commands"], f"{feature['id']} lacks acceptance commands"
        product_spec = feature.get("product_spec")
        if product_spec:
            assert (ROOT / product_spec).is_file(), f"missing product owner: {product_spec}"


def test_legacy_markdown_files_are_routes_not_duplicate_owners() -> None:
    """Compatibility routes stay small and point directly to existing final owners."""
    legacy = _legacy_markdown_paths()
    legacy_relative = {path.relative_to(ROOT).as_posix() for path in legacy}
    route_pattern = re.compile(
        r"`((?:AGENTS|ARCHITECTURE|README)\.md|feature_list\.json|"
        r"(?:backend|docs|frontend|scripts)/[^`\s]+)`"
    )
    for path in legacy:
        content = path.read_text(encoding="utf-8")
        assert len(content.encode("utf-8")) <= 600, f"legacy owner regrew: {path.relative_to(ROOT)}"
        assert content.startswith("# Retired"), f"legacy route is not marked retired: {path}"
        targets = route_pattern.findall(content)
        assert targets, f"legacy page has no explicit final-owner route: {path.relative_to(ROOT)}"
        for target in targets:
            normalized = target.rstrip("/")
            assert (ROOT / normalized).exists(), (
                f"missing migration target from {path.relative_to(ROOT)}: {target}"
            )
            assert normalized not in legacy_relative, (
                f"compatibility route chains through another retired page: "
                f"{path.relative_to(ROOT)} -> {target}"
            )

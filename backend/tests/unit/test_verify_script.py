"""Machine-readable feature-state validation tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_feature as vf  # noqa: E402

pytestmark = pytest.mark.unit


def _state(*features: dict[str, object]) -> dict[str, object]:
    """Build the smallest valid feature-state document used by unit tests."""
    return {
        "schema_version": 1,
        "status_semantics": "recorded evidence",
        "features": list(features),
    }


def _feature(feature_id: str, status: str = "not_started") -> dict[str, object]:
    """Build one valid feature entry with a harmless verification command."""
    return {
        "id": feature_id,
        "title": feature_id,
        "category": "test",
        "acceptance_intent": "test intent",
        "status": status,
        "verification": {"commands": ["pytest tests/unit/test_smoke.py"]},
    }


@pytest.fixture()
def feature_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect feature-state writes to a temporary JSON file."""
    path = tmp_path / "feature_list.json"
    path.write_text(json.dumps(_state(_feature("F01"))), encoding="utf-8")
    monkeypatch.setattr(vf, "FEATURE_LIST_FILE", path)
    return path


def test_load_and_find_feature(feature_file: Path) -> None:
    """A valid document loads and exposes its feature by stable ID."""
    data = vf._load_feature_list()
    assert vf._find_feature(data, "F01")["status"] == "not_started"


def test_update_state_writes_valid_json(feature_file: Path) -> None:
    """State updates preserve the document and write valid UTF-8 JSON."""
    vf._update_state("F01", "passing")
    content = json.loads(feature_file.read_text(encoding="utf-8"))
    assert content["features"][0]["status"] == "passing"


@pytest.mark.parametrize(
    "document",
    [
        _state(_feature("F01", "unknown")),
        _state(_feature("F01", "blocked")),
        _state(_feature("F01"), _feature("F01")),
    ],
    ids=["unknown-status", "retired-blocked-status", "duplicate-id"],
)
def test_invalid_feature_state_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, document: dict[str, object]
) -> None:
    """Invalid acceptance states and duplicate IDs fail closed."""
    path = tmp_path / "feature_list.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(vf, "FEATURE_LIST_FILE", path)
    with pytest.raises(SystemExit):
        vf._load_feature_list()


def test_features_hold_independent_acceptance_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feature state has no repository-wide task-execution exclusivity rule."""
    path = tmp_path / "feature_list.json"
    path.write_text(
        json.dumps(_state(_feature("F01", "passing"), _feature("F02", "failing"))),
        encoding="utf-8",
    )
    monkeypatch.setattr(vf, "FEATURE_LIST_FILE", path)
    data = vf._load_feature_list()
    assert [item["status"] for item in data["features"]] == ["passing", "failing"]


def test_list_features_filters_status_and_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Progressive discovery can query only the requested status and category."""
    first = _feature("F01", "passing")
    second = _feature("F02")
    second["category"] = "agent"
    path = tmp_path / "feature_list.json"
    path.write_text(json.dumps(_state(first, second)), encoding="utf-8")
    monkeypatch.setattr(vf, "FEATURE_LIST_FILE", path)
    vf._list_features(["--status", "not_started", "--category", "agent"])
    assert capsys.readouterr().out == "F02\tnot_started\tagent\tF02\n"


@pytest.mark.parametrize(
    ("raw", "cwd_name", "prefix"),
    [
        ("pytest tests/unit/test_smoke.py", "backend", ["uv", "run", "pytest"]),
        ("pnpm test:unit", "frontend", ["pnpm", "test:unit"]),
    ],
)
def test_adapt_command_uses_owned_command_entries(
    raw: str, cwd_name: str, prefix: list[str]
) -> None:
    """Recorded pytest and pnpm commands resolve to the correct workspace."""
    command, cwd = vf._adapt_command(raw)
    assert command[: len(prefix)] == prefix
    assert cwd.name == cwd_name

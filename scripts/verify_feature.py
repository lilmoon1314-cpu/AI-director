"""Validate features and update the machine-readable acceptance state.

Usage:
    python scripts/verify_feature.py F01
    python scripts/verify_feature.py --list [--status passing] [--category agent]
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task import _resolve_executable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEATURE_LIST_FILE = ROOT / "feature_list.json"
TASK_SCRIPT = ROOT / "scripts" / "task.py"
VALID_STATES = ("not_started", "passing", "failing")


def _fail(problem: str, cause: str, fix: str) -> None:
    """Exit with a concise problem, cause, and repair action."""
    print(f"[问题] {problem}\n[原因] {cause}\n[修复] {fix}", file=sys.stderr)
    raise SystemExit(1)


def _load_feature_list() -> dict[str, Any]:
    """Load and validate the feature-state document without changing it."""
    try:
        data = json.loads(FEATURE_LIST_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(
            f"无法读取 {FEATURE_LIST_FILE.name}",
            f"文件不存在、不可读或不是合法 JSON: {exc}",
            "恢复合法的 feature_list.json 后重试",
        )
    features = data.get("features")
    if data.get("schema_version") != 1 or not isinstance(features, list):
        _fail(
            "feature state 结构无效",
            "schema_version 必须为 1 且 features 必须是数组",
            "对照仓库 feature_list.json 的 schema 修复字段",
        )

    seen: set[str] = set()
    for item in features:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            _fail("feature 条目无效", "条目不是对象或缺少字符串 id", "补齐合法 feature id")
        feature_id = item["id"]
        if feature_id in seen:
            _fail(f"feature id 重复: {feature_id}", "ID 必须全局唯一", "删除或合并重复条目")
        seen.add(feature_id)
        if item.get("status") not in VALID_STATES:
            _fail(
                f"{feature_id} 状态无效: {item.get('status')}",
                f"合法状态为 {VALID_STATES}",
                "改为能够描述验收证据的合法状态",
            )
        commands = item.get("verification", {}).get("commands")
        if not isinstance(commands, list) or not all(
            isinstance(command, str) for command in commands
        ):
            _fail(
                f"{feature_id} verification.commands 无效",
                "验证命令必须是字符串数组",
                "在 feature_list.json 中登记明确的命令数组",
            )
    return data


def _find_feature(data: dict[str, Any], feature_id: str) -> dict[str, Any]:
    """Return one feature entry or fail with a repairable message."""
    for item in data["features"]:
        if item["id"] == feature_id:
            return item
    _fail(
        f"功能清单中未找到 {feature_id}",
        "feature_list.json 中没有该 ID",
        "确认 ID 拼写，或先登记该产品能力",
    )
    raise AssertionError("unreachable")


def _write_feature_list(data: dict[str, Any]) -> None:
    """Atomically persist validated feature state as stable UTF-8 JSON."""
    FEATURE_LIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = FEATURE_LIST_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, FEATURE_LIST_FILE)


def _update_state(feature_id: str, new_state: str) -> None:
    """Update one feature's acceptance state while enforcing valid state values."""
    if new_state not in VALID_STATES:
        _fail(f"非法状态值: {new_state}", f"合法值: {VALID_STATES}", "检查调用参数")
    data = _load_feature_list()
    target = _find_feature(data, feature_id)
    target["status"] = new_state
    _write_feature_list(data)


def _adapt_command(raw: str) -> tuple[list[str], Path]:
    """Resolve one portable verification command and its working directory."""
    parts = shlex.split(raw, posix=False)
    if not parts:
        _fail("验证命令为空", "feature 未登记有效命令", "补充 verification.commands")
    head, rest = parts[0], parts[1:]
    if head == "make":
        return [sys.executable, str(TASK_SCRIPT), *rest], ROOT
    if head == "pytest":
        return ["uv", "run", "pytest", *rest], ROOT / "backend"
    if head == "pnpm":
        return ["pnpm", *rest], ROOT / "frontend"
    _fail(
        f"无法适配的验证命令: {raw}",
        "只允许 make、pytest 或 pnpm 命令入口",
        "把执行逻辑收口到 scripts/task.py 或 package scripts 后再引用",
    )
    raise AssertionError("unreachable")


def _list_features(argv: list[str]) -> None:
    """Print a compact, filterable feature-state view for progressive discovery."""
    status: str | None = None
    category: str | None = None
    for index, arg in enumerate(argv):
        if arg == "--status" and index + 1 < len(argv):
            status = argv[index + 1]
        if arg == "--category" and index + 1 < len(argv):
            category = argv[index + 1]
    if status is not None and status not in VALID_STATES:
        _fail(f"未知状态过滤值: {status}", f"合法值: {VALID_STATES}", "修正 --status 参数")
    data = _load_feature_list()
    for item in data["features"]:
        if status is not None and item["status"] != status:
            continue
        if category is not None and item["category"] != category:
            continue
        print(f"{item['id']}\t{item['status']}\t{item['category']}\t{item['title']}")


def main(argv: list[str]) -> None:
    """List features or run one feature's recorded acceptance commands."""
    if not argv:
        _fail(
            "缺少参数",
            "未指定 feature ID 或 --list",
            "用法: python scripts/verify_feature.py F01 或 --list",
        )
    if argv[0] == "--list":
        _list_features(argv[1:])
        return

    feature_id = argv[0]
    data = _load_feature_list()
    feature = _find_feature(data, feature_id)
    current = feature["status"]
    if argv[1:]:
        _fail(
            f"未知参数: {argv[1:]}",
            "feature 状态只记录验收证据，不承担当前任务执行状态",
            "移除额外参数；任务进度写入对应 active ExecPlan",
        )

    commands = feature["verification"]["commands"]
    if not commands:
        _fail(
            f"{feature_id} 未登记验证命令",
            "verification.commands 为空",
            "登记与 acceptance intent 匹配的最小充分验证",
        )

    print(f"=== 验证 {feature_id}（当前状态: {current}）===")
    failed: list[str] = []
    for raw in commands:
        command, cwd = _adapt_command(raw)
        resolved = _resolve_executable(command[0])
        print(f"\n==> {' '.join(command)}   [cwd: {cwd.relative_to(ROOT)}]")
        result = subprocess.run([*resolved, *command[1:]], cwd=cwd)
        if result.returncode != 0:
            failed.append(raw)

    new_state = "passing" if not failed else "failing"
    _update_state(feature_id, new_state)
    print(f"\n=== {feature_id}: {current} -> {new_state} ===")
    if failed:
        _fail(
            f"{feature_id} 验证未通过，状态已置为 failing",
            f"失败命令: {failed}",
            "修复对应行为后重新运行该 feature 的验证",
        )


if __name__ == "__main__":
    main(sys.argv[1:])

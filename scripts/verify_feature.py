"""功能清单状态自动验证与更新（docs/features.md 的唯一合法写入口）。

作用:
    按功能清单中登记的验证命令逐条执行，全部通过则把该功能状态更新为
    passing，任一失败则更新为 blocked —— 实现 AGENTS.md「状态由验证脚本
    自动更新，禁止手工修改」的规则，杜绝虚报完成。

用法:
    python scripts/verify_feature.py F01              # 运行验证并写入终态
    python scripts/verify_feature.py F01 --activate   # 仅置为 active（开工时）
"""

import re
import subprocess
import sys
from pathlib import Path

# 复用命令面板的 Windows 兼容层（.cmd 工具解析，如 pnpm）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from task import _resolve_executable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEATURES_FILE = ROOT / "docs" / "features.md"
TASK_SCRIPT = ROOT / "scripts" / "task.py"

# 状态机合法取值（docs/features.md 表头约定）
VALID_STATES = ("not_started", "active", "passing", "blocked")


def _fail(problem: str, cause: str, fix: str) -> None:
    """输出三要素错误消息并终止。

    作用: 统一错误出口（docs/lessons.md 错误消息三要素规范）。
    参数: problem/cause/fix — 三要素文本。返回值: 无。异常: SystemExit(1)。依赖: 无。
    """
    print(f"[问题] {problem}\n[原因] {cause}\n[修复] {fix}", file=sys.stderr)
    sys.exit(1)


def _parse_feature_row(feature_id: str) -> tuple[int, str, str]:
    """从 docs/features.md 解析指定功能行。

    作用:
        定位功能项所在行，提取验证命令（反引号内文本）与当前状态。
    参数:
        feature_id — 功能项 ID（如 F01）。
    返回值:
        (行号, 验证命令原文, 当前状态)；验证命令可能为空串（未登记）。
    异常:
        功能 ID 不存在或表格列数不符时经 _fail 终止。
    依赖: re / pathlib。
    """
    lines = FEATURES_FILE.read_text(encoding="utf-8").splitlines()
    row_re = re.compile(rf"^\|\s*{re.escape(feature_id)}\s*\|")
    for line_no, line in enumerate(lines):
        if not row_re.match(line):
            continue
        cells = [c.strip() for c in line.split("|")]
        # cells: [''] + 6 列（ID/功能/描述/跨组件/验证命令/状态）+ ['']（首尾管道产生的空段）
        if len(cells) != 8:
            _fail(f"功能 {feature_id} 行列数异常", "表格被破坏或列分隔符缺失", "对照表头修复该行")
        verify_cmds = " && ".join(re.findall(r"`([^`]+)`", cells[5]))
        # 状态列剥离转义反斜杠（IDE markdown 格式化器会把 not_started 转义为 not\_started，E02）
        return line_no, verify_cmds, cells[6].replace("\\", "")
    _fail(
        f"功能清单中未找到 {feature_id}",
        f"docs/features.md 表格内无该 ID 的行",
        "确认 ID 拼写，或在清单中登记该功能项",
    )
    raise AssertionError("unreachable")  # pragma: no cover


def _adapt_command(raw: str) -> tuple[list[str], Path]:
    """把清单中的验证命令适配为跨平台可执行形式。

    作用:
        make X → python scripts/task.py X；pytest → backend 下 uv run pytest；pnpm → frontend 下执行。
    参数:
        raw — 单条命令原文（如 "make test" 或 "pytest tests/unit/test_x.py"）。
    返回值:
        (命令及参数列表, 工作目录)。
    异常:
        无法适配的命令前缀经 _fail 终止。
    依赖: 无。
    """
    parts = raw.split()
    if not parts:
        _fail("验证命令为空", "功能清单该列未登记命令", f"在 docs/features.md 为该功能补充验证命令")
    head, rest = parts[0], parts[1:]
    if head == "make":
        return [sys.executable, str(TASK_SCRIPT), *rest], ROOT
    if head == "pytest":
        return ["uv", "run", "pytest", *rest], ROOT / "backend"
    if head == "pnpm":
        return ["pnpm", *rest], ROOT / "frontend"
    _fail(
        f"无法适配的验证命令: {raw}",
        "verify_feature.py 仅支持 make / pytest / pnpm 三种前缀",
        "在 scripts/verify_feature.py 的 _adapt_command 中登记该前缀",
    )
    raise AssertionError("unreachable")  # pragma: no cover


def _update_state(feature_id: str, new_state: str) -> None:
    """把指定功能行的状态列更新为 new_state（唯一合法的状态写入途径）。

    作用:
        原地重写 docs/features.md 对应行的最后一列；其余内容逐字节保留。
    参数:
        feature_id — 功能项 ID；new_state — 目标状态（VALID_STATES 之一）。
    返回值: 无。
    异常: 状态值非法或行缺失时经 _fail 终止。
    依赖: re / pathlib。
    """
    if new_state not in VALID_STATES:
        _fail(f"非法状态值: {new_state}", f"合法值: {VALID_STATES}", "检查调用参数")
    lines = FEATURES_FILE.read_text(encoding="utf-8").splitlines()
    # 状态单元格宽容匹配（[^\s|]+）：兼容格式化器的列对齐与下划线转义（not\_started，E02）
    row_re = re.compile(rf"^(\|\s*{re.escape(feature_id)}\s*\|.*)\|\s*[^\s|]+\s*\|\s*$")
    for idx, line in enumerate(lines):
        if row_re.match(line):
            lines[idx] = row_re.sub(rf"\1| {new_state} |", line)
            FEATURES_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    _fail(f"未找到 {feature_id} 行", "解析逻辑与表格格式不一致", "检查 _parse_feature_row 的列匹配规则")


def main(argv: list[str]) -> None:
    """主流程：解析参数 → （--activate 则仅置 active）→ 否则逐条执行验证命令并写终态。

    作用:
        verify FXX 的完整链路；全部命令退出码 0 → passing，否则 blocked。
    参数:
        argv — [功能ID] 与可选 --activate。
    返回值: 无。
    异常:
        验证失败时退出码 1（状态已写为 blocked）。
    依赖: _parse_feature_row / _adapt_command / _update_state / subprocess。
    """
    if not argv:
        _fail("缺少功能项 ID", "未传入命令行参数", "用法: python scripts/verify_feature.py F01 [--activate]")
    feature_id = argv[0]
    line_no, verify_cmds, current = _parse_feature_row(feature_id)

    if "--activate" in argv[1:]:
        _update_state(feature_id, "active")
        print(f"{feature_id}: {current} -> active")
        return

    if not verify_cmds:
        _fail(f"{feature_id} 未登记验证命令", "功能清单验证命令列为空", f"在 docs/features.md 第 {line_no + 1} 行补充反引号包裹的命令")

    print(f"=== 验证 {feature_id}（当前状态: {current}）===")
    failed: list[str] = []
    for segment in verify_cmds.split("&&"):
        cmd, cwd = _adapt_command(segment.strip())
        resolved = _resolve_executable(cmd[0])
        print(f"\n==> {' '.join(cmd)}   [cwd: {cwd.relative_to(ROOT)}]")
        result = subprocess.run([*resolved, *cmd[1:]], cwd=cwd)
        if result.returncode != 0:
            failed.append(segment.strip())

    new_state = "passing" if not failed else "blocked"
    _update_state(feature_id, new_state)
    print(f"\n=== {feature_id}: {current} -> {new_state} ===")
    if failed:
        print(
            "[问题] 验证未通过，状态已置为 blocked\n"
            f"[原因] 以下命令失败: {failed}\n"
            "[修复] 修复失败命令对应的功能代码后重新执行本验证",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

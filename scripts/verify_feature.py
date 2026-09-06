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
import sqlite3
import subprocess
import sys
from pathlib import Path

# 复用命令面板的 Windows 兼容层（.cmd 工具解析，如 pnpm）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from task import _resolve_executable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEATURES_FILE = ROOT / "docs" / "features.md"
TASK_SCRIPT = ROOT / "scripts" / "task.py"
BACKEND_DIR = ROOT / "backend"
MUTATION_CACHE = BACKEND_DIR / ".mutmut-cache"

# 状态机合法取值（docs/features.md 表头约定）
VALID_STATES = ("not_started", "active", "passing", "blocked")

# ---- 变异证据门禁（docs/testing.md §9；E12 流程风险的机器化防控）----
# 变异测试工具随 F04 落地，门禁自 F04 起的功能生效
MUTATION_ENFORCE_SINCE_F = 4
# kill rate 门槛与 DoD 一致（docs/testing.md §2/§9）
MUTATION_KILL_RATE_THRESHOLD = 0.85


def _mutation_modules(verify_cmds: str) -> list[str]:
    """从验证命令提取被测模块名（L1 文件名约定 test_<module>_service.py）。

    作用: 变异证据门禁的模块定位——features.md 的 L1 单测路径即变异 scope
        约定（如 F11 的 test_projects_service.py → projects）。
    参数: verify_cmds — 功能行的验证命令原文。
    返回值: list[str]（去重排序的模块名；纯前端功能返回空列表）。
    异常: 无。依赖: re。
    """
    return sorted(set(re.findall(r"tests/unit/test_([a-z_]+)_service\.py", verify_cmds)))


def _module_last_commit_epoch(module: str) -> int:
    """被测模块目录最后一次提交的 epoch 秒（无提交历史返回 0）。

    作用: 变异缓存新鲜度的比对基准——模块代码在变异运行后被改动（提交）
        即视为证据过期（E12：判杀基线与代码不一致导致 kill rate 失真）。
    参数: module — 模块名（app/ 下目录名）。
    返回值: int（epoch 秒；无历史=0）。异常: 无。依赖: git。
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", f"backend/app/{module}/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    out = result.stdout.strip()
    return int(out) if out.isdigit() else 0


def _mutation_gate(module: str) -> tuple[bool, str]:
    """校验模块的变异测试证据（缓存存在 / 含该模块 / kill rate 达标 / 晚于模块最后提交）。

    作用:
        DoD 第 5 条的机器化防控（E12 流程风险）——verify 写 passing 前强制
        确认「测试强化后重跑了变异、且结果反映最终代码」，防止跳过变异或
        用陈旧结果宣称完成。
    参数: module — 被测模块名。
    返回值: (是否通过, (问题, 原因, 修复))；通过时消息为空元组。
    异常: 无（缓存缺失/损坏均归并为未通过）。
    依赖: sqlite3（只读连接 mutmut 缓存）、_module_last_commit_epoch。
    """
    if not MUTATION_CACHE.is_file():
        return False, (
            f"模块 {module} 缺少变异测试证据（{MUTATION_CACHE.name} 不存在）",
            "变异测试从未对该模块运行，或运行后被清缓存，DoD 第 5 条无法确认",
            f"先提交该模块全部改动，再运行: python scripts/task.py mutate {module} "
            "tests/unit/test_<module>_service.py tests/integration/<该功能集成测试>",
        )
    try:
        conn = sqlite3.connect(f"file:{MUTATION_CACHE.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT m.status FROM Mutant m "
                "JOIN Line l ON m.line = l.id "
                "JOIN SourceFile s ON l.sourcefile = s.id "
                "WHERE s.filename LIKE ?",
                (f"app/{module}/%",),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return False, (
            f"模块 {module} 的变异缓存不可读（{MUTATION_CACHE.name} 损坏）",
            "缓存文件存在但无法按 mutmut 2.x 表结构查询",
            "删除缓存后重跑: python scripts/task.py mutate <module> ...",
        )
    total = len(rows)
    if total == 0:
        return False, (
            f"变异缓存不含模块 {module} 的变异体",
            "缓存来自其他模块的运行（task.py mutate 每次清缓存，仅保留最近一次）",
            f"对 {module} 重跑: python scripts/task.py mutate {module} ...",
        )
    killed = sum(1 for (status,) in rows if status == "ok_killed")
    if killed / total < MUTATION_KILL_RATE_THRESHOLD:
        return False, (
            f"模块 {module} 变异测试未达标（kill rate {killed}/{total} = "
            f"{killed / total:.1%} < {MUTATION_KILL_RATE_THRESHOLD:.0%}）",
            "存在未被测试集杀灭的变异体，测试有效性不足（docs/testing.md §9）",
            "按存活变异体逐一分析：补判杀用例或登记等价性后重跑 mutate",
        )
    last_commit = _module_last_commit_epoch(module)
    if MUTATION_CACHE.stat().st_mtime < last_commit:
        return False, (
            f"模块 {module} 的变异证据过期（缓存早于该模块最后一次提交）",
            "变异运行后模块代码又被改动，kill rate 不再反映最终代码（E12）",
            f"提交全部改动后重跑: python scripts/task.py mutate {module} ...",
        )
    return True, ()


def _mutation_gate_for_feature(feature_id: str, verify_cmds: str) -> list[str]:
    """对功能执行变异证据门禁，返回未通过项的三要素消息列表。

    作用: main 的接入口——仅对 F04 起、且 L1 命令约定的模块（目录含 .py）
        生效；纯前端功能与空壳模块（如 agent 尚无代码）自动跳过。
    参数: feature_id — 功能 ID；verify_cmds — 验证命令原文。
    返回值: list[str]（失败消息；空列表=通过）。异常: 无。依赖: _mutation_* 系列。
    """
    match = re.fullmatch(r"F(\d+)", feature_id)
    if not match or int(match.group(1)) < MUTATION_ENFORCE_SINCE_F:
        return []
    failures: list[str] = []
    for module in _mutation_modules(verify_cmds):
        if not any((BACKEND_DIR / "app" / module).glob("*.py")):
            continue  # 模块尚无 Python 代码（如 agent 在 F10 前）——无变异对象
        ok, message = _mutation_gate(module)
        if not ok:
            problem, cause, fix = message
            failures.append(
                f"{feature_id} 变异证据门禁未过（模块 {module}）: "
                f"{problem}；{cause}；{fix}"
            )
    return failures


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

    # 变异证据门禁（E12 防控）：命令全过也必须在写 passing 前确认变异测试
    # 对最终代码达标（docs/testing.md §9/§2 DoD 第 5 条）
    if not failed:
        for gate_failure in _mutation_gate_for_feature(feature_id, verify_cmds):
            print(f"\n[问题] {gate_failure}", file=sys.stderr)
            failed.append("变异证据门禁未通过")

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

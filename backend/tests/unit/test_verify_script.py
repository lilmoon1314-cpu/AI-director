r"""verify_feature.py 解析鲁棒性单元测试（L1，错误模式 E02 回归）。

覆盖场景:
    IDE markdown 格式化器重排 features.md 表格（列宽变化）并对非代码区
    下划线做转义（not_started 转义为 not\_started）后，验证脚本仍能
    正确定位功能行、读取状态、写回状态。
"""

import sys
from pathlib import Path

import pytest

# 仓库根 = backend/tests/unit/ 向上三级；脚本目录加入模块搜索路径
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_feature as vf  # noqa: E402

pytestmark = pytest.mark.unit

# 模拟被 IDE 格式化器改写过的清单（含状态列下划线转义；列宽与真实文件不同以覆盖重排场景）
ESCAPED_ROW = (
    "| F02 | 实体 CRUD API | properties 校验、删除校验关系引用 | 否 |"
    " `pytest tests/unit/test_entities_service.py` | not\\_started |"
)
ESCAPED_TABLE = (
    "# 功能清单（测试样例）\n\n"
    "| ID | 功能 | 行为描述 | 跨组件 | 验证命令 | 状态 |\n"
    "| --- | --- | --- | --- | --- | --- |\n" + ESCAPED_ROW + "\n"
)


@pytest.fixture()
def features_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把脚本指向临时清单文件，隔离真实 docs/features.md。

    返回值: 临时清单文件路径（已写入转义表格样例）。
    """
    path = tmp_path / "features.md"
    path.write_text(ESCAPED_TABLE, encoding="utf-8")
    monkeypatch.setattr(vf, "FEATURES_FILE", path)
    return path


def test_parse_row_with_escaped_state(features_file: Path) -> None:
    r"""转义状态（not\_started）可被正确读回为 not_started，验证命令不受影响。

    失败含义:
        【问题】格式化后的清单状态/命令解析失败
        【原因】_parse_feature_row 未剥离转义反斜杠（错误模式 E02 回归）
        【修复】恢复 verify_feature.py 状态列的 replace("\\", "") 处理
    """
    _, cmds, state = vf._parse_feature_row("F02")
    assert state == "not_started"
    assert cmds == "pytest tests/unit/test_entities_service.py"


def test_update_state_on_formatted_row(features_file: Path) -> None:
    r"""格式化后的行上状态写回成功，且其余列内容不被破坏。

    失败含义:
        【问题】在转义/对齐过的行上写状态失败（verify 报"未找到 F02 行"）
        【原因】_update_state 行正则不匹配转义状态（错误模式 E02 回归）
        【修复】恢复 verify_feature.py 状态单元格的宽容正则
    """
    vf._update_state("F02", "active")
    content = features_file.read_text(encoding="utf-8")
    assert "| active |" in content
    # 其余列（验证命令）原样保留
    assert "pytest tests/unit/test_entities_service.py" in content


# ---------------- 变异证据门禁（E12 防控，docs/testing.md §9）----------------


def _make_cache(path: Path, module: str, killed: int, survived: int) -> None:
    """构造含指定模块变异体统计的 mutmut 2.x 缓存文件。

    作用: 门禁单测的缓存桩——SourceFile/Line/Mutant 三表按真实 schema 装配。
    参数: path — 缓存文件路径；module — 模块名；killed/survived — 状态计数。
    返回值: 无。异常: 无。依赖: sqlite3。
    """
    import sqlite3

    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE SourceFile (id INTEGER PRIMARY KEY, filename TEXT, hash TEXT);"
        "CREATE TABLE Line (id INTEGER PRIMARY KEY, sourcefile INTEGER, line TEXT,"
        " line_number INTEGER);"
        'CREATE TABLE Mutant (id INTEGER PRIMARY KEY, line INTEGER, "index" INTEGER,'
        " tested_against_hash TEXT, status TEXT);"
    )
    conn.execute("INSERT INTO SourceFile VALUES (1, ?, 'h')", (f"app/{module}/service.py",))
    for i in range(killed + survived):
        status = "ok_killed" if i < killed else "bad_survived"
        conn.execute("INSERT INTO Line VALUES (?, 1, 'x', 1)", (i,))
        conn.execute("INSERT INTO Mutant VALUES (?, ?, 0, 'h', ?)", (i, i, status))
    conn.commit()
    conn.close()


@pytest.fixture()
def gate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把门禁指向临时缓存并屏蔽 git 时间（默认模块无提交历史=0）。"""
    cache = tmp_path / ".mutmut-cache"
    monkeypatch.setattr(vf, "MUTATION_CACHE", cache)
    monkeypatch.setattr(vf, "_module_last_commit_epoch", lambda _module: 0)
    return cache


def test_mutation_modules_extracted_from_cmds() -> None:
    r"""验证命令中的 L1 文件名约定可提取变异模块；纯前端命令返回空。

    失败含义:
        【问题】门禁定位不到被测模块
        【原因】_mutation_modules 的 test_<module>_service.py 约定解析失效
        【修复】恢复正则与 features.md L1 命令约定的匹配
    """
    cmds = (
        "pytest tests/unit/test_projects_service.py；"
        "L2: pytest tests/integration/test_projects_api.py；前端: pnpm test:unit"
    )
    assert vf._mutation_modules(cmds) == ["projects"]
    assert vf._mutation_modules("pnpm test:unit && pnpm test:e2e") == []


def test_mutation_gate_passes_with_fresh_evidence(gate_env: Path) -> None:
    r"""缓存存在、含模块、kill rate 达标、晚于最后提交 → 通过。

    失败含义:
        【问题】证据齐全仍被门禁拦截
        【原因】_mutation_gate 的达标判定或缓存查询回归
        【修复】对照 docs/testing.md §9 检查门禁实现
    """
    _make_cache(gate_env, "projects", killed=100, survived=0)
    ok, message = vf._mutation_gate("projects")
    assert ok and message == ()


def test_mutation_gate_fails_on_missing_cache(gate_env: Path) -> None:
    r"""缓存不存在 → 拒绝（等价类—从未运行/缓存被清）。

    失败含义:
        【问题】缺证据仍放行（DoD 第 5 条被架空）
        【原因】缺失分支未拦截
        【修复】恢复 MUTATION_CACHE.is_file 前置校验
    """
    ok, message = vf._mutation_gate("projects")
    assert not ok and "缺少变异测试证据" in message[0]


def test_mutation_gate_fails_on_low_kill_rate(gate_env: Path) -> None:
    r"""kill rate < 85% → 拒绝（边界值—门槛两侧）。

    失败含义:
        【问题】未达标仍放行
        【原因】门槛比较失效
        【修复】恢复 MUTATION_KILL_RATE_THRESHOLD 判定
    """
    _make_cache(gate_env, "projects", killed=84, survived=16)  # 84% < 85%
    ok, message = vf._mutation_gate("projects")
    assert not ok and "kill rate" in message[0]


def test_mutation_gate_fails_on_foreign_module_cache(gate_env: Path) -> None:
    r"""缓存来自其他模块（不含本模块变异体）→ 拒绝（等价类—证据错位）。

    失败含义:
        【问题】以他模块证据冒充本模块达标
        【原因】未按 SourceFile.filename 过滤
        【修复】恢复 JOIN SourceFile 的 LIKE 过滤
    """
    _make_cache(gate_env, "assets", killed=100, survived=0)
    ok, _message = vf._mutation_gate("projects")
    assert not ok


def test_mutation_gate_fails_on_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r"""缓存早于模块最后一次提交 → 拒绝（E12—证据过期）。

    失败含义:
        【问题】陈旧证据仍放行
        【原因】未做 mtime 与最后提交时间比对
        【修复】恢复 _module_last_commit_epoch 新鲜度校验
    """
    import os
    import time

    cache = tmp_path / ".mutmut-cache"
    _make_cache(cache, "projects", killed=100, survived=0)
    # 模块最后提交 = 现在；缓存 mtime 固定为一小时前
    monkeypatch.setattr(vf, "MUTATION_CACHE", cache)
    monkeypatch.setattr(vf, "_module_last_commit_epoch", lambda _module: int(time.time()))
    stale = time.time() - 3600
    os.utime(cache, (stale, stale))
    ok, message = vf._mutation_gate("projects")
    assert not ok and "过期" in message[0]


def test_mutation_gate_for_feature_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    r"""门禁范围：F03（工具落地前）与纯前端功能跳过；F11 生效。

    失败含义:
        【问题】门禁误伤历史功能或漏管新功能
        【原因】MUTATION_ENFORCE_SINCE_F 或模块提取逻辑回归
        【修复】恢复生效范围判定（F04 起 + L1 文件名约定）
    """
    # F03 在工具落地前 → 跳过（即使命令含 L1 路径）
    assert vf._mutation_gate_for_feature("F03", "pytest tests/unit/test_entities_service.py") == []
    # 纯前端功能（无 L1 pytest 命令）→ 无模块可查，跳过
    assert vf._mutation_gate_for_feature("F12", "pnpm test:unit && pnpm test:e2e") == []
    # F11 且模块存在代码 → 调用真实门禁（此处以缺失缓存断言其被真正执行）
    monkeypatch.setattr(vf, "MUTATION_CACHE", Path("nonexistent-mutmut-cache"))
    failures = vf._mutation_gate_for_feature("F11", "pytest tests/unit/test_projects_service.py")
    assert len(failures) == 1 and "缺少变异测试证据" in failures[0]

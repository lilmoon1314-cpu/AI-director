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

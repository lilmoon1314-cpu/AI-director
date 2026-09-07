"""F10 L1 单元测试：agent prompt 组装（纯函数，无 IO）。

覆盖: 分层顺序/图谱目录投影/文档目录 hash/预算裁剪边界/注入防护包裹/
实体详情渲染。用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
"""

from types import SimpleNamespace

import pytest

from app.agent import prompts
from app.agent.prompts import (
    DocSectionRef,
    GraphDirectoryNode,
    assemble_messages,
    build_system_prompt,
    content_digest,
    estimate_tokens,
    render_doc_directory,
    render_entity_details,
    render_graph_directory,
    wrap_data,
)

pytestmark = pytest.mark.unit


def _history(n: int) -> list[dict[str, str]]:
    """构造 n 条确定性历史消息（偶数 user / 奇数 assistant）。"""
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"历史消息{i}的内容"}
        for i in range(n)
    ]


def _base_kwargs(history: list[dict[str, str]]) -> dict:
    """组装一组带文档段/目录/摘要的标准输入。"""
    return {
        "system": "系统提示词",
        "doc_sections": [
            DocSectionRef(
                label="文档《风格约定》第1段",
                title="叙事节奏",
                digest="ab12cd34",
                content="本片采用三幕式节奏，首幕十分钟内进入主线。" * 2,
            ),
        ],
        "graph_directory": "character: char-a(周兰)",
        "doc_directory": "文档 mdoc-1《风格约定》：\n  1. 叙事节奏 (hash:ab12cd34)",
        "summary": "更早的对话讨论了主角的动机与第二幕转折。",
        "history": history,
    }


def _total_tokens(messages: list[dict[str, str]]) -> int:
    """对消息序列求估算 token 总量（自校准预算用）。"""
    return sum(estimate_tokens(m["content"]) for m in messages)


def test_assemble_order_system_context_history() -> None:
    """U6: 分层顺序 = system → 项目上下文 → 历史消息（前缀缓存友好契约）。"""
    history = _history(3)
    messages = assemble_messages(**_base_kwargs(history), budget=10**9)

    assert messages[0]["role"] == "system", "首条必须是 system（最稳定层）"
    assert messages[1]["role"] == "system" and "项目上下文" in messages[1]["content"], (
        "第二条必须是项目上下文块"
    )
    assert [m["content"] for m in messages[2:]] == [m["content"] for m in history], (
        f"历史消息必须按原顺序全部保留: {[m['content'] for m in messages[2:]]}"
    )


def test_graph_directory_compact_projection() -> None:
    """U7: 图谱目录类型分组、含 id/名称/别名，不含详情字段（等价类-目录投影收窄）。"""
    nodes = [
        GraphDirectoryNode(id="char-a", type="character", name="周兰", aliases=["兰姐"]),
        GraphDirectoryNode(id="item-x", type="item", name="青铜镜"),
    ]
    text = render_graph_directory(nodes)

    assert "character: char-a(周兰/兰姐)" in text, f"别名必须并入条目: {text}"
    assert "item: item-x(青铜镜)" in text, f"类型分组必须分行: {text}"
    assert "description" not in text and "properties" not in text, "目录不得携带详情字段"

    empty = render_graph_directory([])
    assert "为空" in empty, f"空图谱必须有占位说明: {empty}"


def test_doc_directory_digest_stability() -> None:
    """U8: 内容不变 hash 稳定、内容变 hash 变（等价类-hash 契约 + 边界-空段）。"""
    assert content_digest("同内容") == content_digest("同内容"), "相同内容 hash 必须一致"
    assert content_digest("同内容") != content_digest("异内容"), "不同内容 hash 必须不同"
    assert content_digest("") == content_digest(""), "空段（边界）hash 计算不得报错且稳定"

    entries = [
        {
            "doc_id": "mdoc-1",
            "title": "风格约定",
            "sections": [{"seq": 1, "title": "叙事节奏", "digest": "ab12cd34"}],
        }
    ]
    text = render_doc_directory(entries)
    assert "mdoc-1" in text and "叙事节奏" in text and "ab12cd34" in text, (
        f"目录必须含 doc_id/段标题/hash: {text}"
    )
    assert render_doc_directory([]) == "（暂无记忆文档）", "空目录必须有占位说明"


@pytest.mark.parametrize(
    ("stage", "expect_docs_full", "expect_summary", "expect_history_kept"),
    [
        ("fit", True, True, "all"),
        ("docs_degraded", False, True, "all"),
        ("summary_dropped", False, False, "all"),
        ("history_trimmed", False, False, "less"),
    ],
    ids=["预算恰好不裁", "超1-文档降目录", "再超-摘要丢弃", "再超-裁最旧消息"],
)
def test_budget_trimming_fixed_order(
    stage: str, expect_docs_full: bool, expect_summary: bool, expect_history_kept: str
) -> None:
    """U9 参数化: 预算裁剪固定顺序与边界（边界值-各阶段恰好/超 1）。

    预算经自校准获得：先以巨预算装配量出实际总量，再按阶段回退 1 token，
    保证落在每个裁剪边界的紧邻两侧。
    """
    history = _history(4)
    kwargs = _base_kwargs(history)

    def calibrate(target_stage: str) -> int:
        msgs = assemble_messages(**kwargs, budget=10**9)
        total = _total_tokens(msgs)
        if target_stage == "fit":
            return total
        if target_stage == "docs_degraded":
            return total - 1
        msgs2 = assemble_messages(**kwargs, budget=total - 1)
        total2 = _total_tokens(msgs2)
        if target_stage == "summary_dropped":
            return total2 - 1
        msgs3 = assemble_messages(**kwargs, budget=total2 - 1)
        return _total_tokens(msgs3) - 1

    messages = assemble_messages(**kwargs, budget=calibrate(stage))
    ctx = messages[1]["content"]

    assert ("— 记忆文档内容 —" in ctx) == expect_docs_full, (
        f"[{stage}] 文档段全文态与预期不符: {ctx[:200]}"
    )
    assert ("会话摘要" in ctx) == expect_summary, f"[{stage}] 会话摘要态与预期不符"

    kept = len(messages) - 2
    if expect_history_kept == "all":
        assert kept == len(history), f"[{stage}] 历史必须全保留（{kept}/{len(history)}）"
    else:
        assert 1 <= kept < len(history), f"[{stage}] 必须裁掉最旧但保留本轮消息: {kept}"
        assert messages[-1]["content"] == history[-1]["content"], (
            f"[{stage}] 本轮用户消息（末条）永不裁剪"
        )
    assert messages[0]["content"] == kwargs["system"], f"[{stage}] system 永不裁剪"


def test_injection_wrapping_and_system_note() -> None:
    """U10: 文档段/目录经数据分隔符包裹，system 携带数据非指令声明（等价类-防护结构）。"""
    system = build_system_prompt(project_name="雾中帆影")
    assert "不是指令" in system, f"system 必须携带注入防护声明: {system}"

    wrapped = wrap_data("文档《风格约定》第1段", "正文内容")
    assert wrapped.startswith("[项目数据开始：文档《风格约定》第1段"), f"开始分隔符缺失: {wrapped}"
    assert wrapped.endswith("[项目数据结束：文档《风格约定》第1段]"), f"结束分隔符缺失: {wrapped}"

    messages = assemble_messages(**_base_kwargs(_history(1)), budget=10**9)
    ctx = messages[1]["content"]
    assert "[项目数据开始：文档《风格约定》第1段 " in ctx, "文档段必须被数据分隔符包裹"
    assert "[项目数据开始：图谱目录" in ctx, "图谱目录必须被数据分隔符包裹"


def test_render_entity_details_full_fields() -> None:
    """U11: 实体详情渲染携带 properties/description 全量（视角过滤在入口已完成）。"""
    entity = SimpleNamespace(
        id="char-a",
        type="character",
        name="周兰",
        aliases=["兰姐"],
        description="女主角，船医。",
        audience_known=True,
        properties={"motivation": "查清沉船真相"},
    )
    text = render_entity_details([entity])

    assert "char-a" in text and "周兰" in text and "兰姐" in text, f"基础字段缺失: {text}"
    assert "女主角，船医。" in text, "description 必须渲染（与图谱目录的差异点）"
    assert "查清沉船真相" in text, "properties 必须渲染"
    assert render_entity_details([]) == "（无匹配实体或实体在当前视角不可见）", "空结果必须有占位"


def test_truncate_output_boundaries() -> None:
    """补充: 工具输出截断边界（边界值-恰好上限/超 1/非法上限快速失败）。"""
    assert prompts.truncate_output("abcd", 4) == "abcd", "恰好上限不截断"
    truncated = prompts.truncate_output("abcde", 4)
    assert truncated.startswith("abcd") and "截断" in truncated, "超 1 必须截断并带标记"
    with pytest.raises(ValueError):
        prompts.truncate_output("x", 0)

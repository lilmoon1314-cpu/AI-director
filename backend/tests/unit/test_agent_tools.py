"""F10 L1 单元测试：agent 检索工具（perspectives/entities 与文档仓储全 mock）。

覆盖: 四工具的有效/无效等价类、seq 边界、跨项目拒绝、未知工具与坏参数
折叠。用例设计（等价类/边界值标注）见 docs/tests/F10_agent_chat.md。
"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import repository
from app.agent.tools import ToolContext, execute_tool
from app.entities import service as entities_service
from app.perspectives import service as perspectives_service
from app.perspectives.schemas import GraphData

pytestmark = pytest.mark.unit

_SESSION: Any = SimpleNamespace()  # 工具层不触会话方法，桩即可


def _ctx(perspective: str = "author") -> ToolContext:
    """构造工具执行上下文桩。"""
    return ToolContext(
        session=_SESSION, project_id="proj-1", perspective=perspective, character_id=""
    )


@pytest.fixture
def graph_world(monkeypatch: pytest.MonkeyPatch) -> None:
    """注入标准图世界：3 可见节点 + 2 边 + 1 可检实体详情。"""
    graph = GraphData.model_validate(
        {
            "nodes": [
                {"id": "char-a", "type": "character", "name": "周兰", "aliases": ["兰姐"]},
                {"id": "char-b", "type": "character", "name": "沈墨", "aliases": []},
                {"id": "loc-l", "type": "location", "name": "青云山", "aliases": []},
            ],
            "edges": [
                {"id": "rel-1", "source": "char-a", "target": "char-b", "type": "ALLIES"},
                {"id": "rel-2", "source": "char-a", "target": "loc-l", "type": "LIVES"},
            ],
        }
    )

    async def fake_get_graph(_session: Any, **_: Any) -> GraphData:
        return graph

    async def fake_filter(_session: Any, **kwargs: Any) -> list[SimpleNamespace]:
        ids = kwargs.get("entity_ids")
        by_id = {n.id: n for n in graph.nodes}
        wanted = ids if ids is not None else list(by_id)
        return [
            SimpleNamespace(
                id=i,
                type=by_id[i].type,
                name=by_id[i].name,
                aliases=list(by_id[i].aliases),
                description="测试简介",
                audience_known=False,
                properties={"k": "v"},
            )
            for i in wanted
            if i in by_id
        ]

    async def fake_search(_session: Any, q: str = "", **_: Any) -> list[SimpleNamespace]:
        hits = [n.id for n in graph.nodes if q and (q in n.name or any(q in a for a in n.aliases))]
        return [SimpleNamespace(id=i) for i in hits]

    monkeypatch.setattr(perspectives_service, "get_graph", fake_get_graph)
    monkeypatch.setattr(perspectives_service, "filter_entities_for_agent", fake_filter)
    monkeypatch.setattr(entities_service, "search", fake_search)


async def test_get_entity_detail_visible_and_invisible(graph_world: None) -> None:
    """U12: 可见 id → 完整详情；不可见 id → 占位说明（等价类-有效/无效-视角不可见）。"""
    visible = await execute_tool("get_entity_detail", '{"entity_id": "char-a"}', _ctx())
    assert "char-a" in visible and "周兰" in visible and "测试简介" in visible, (
        f"可见实体必须返回完整详情: {visible}"
    )
    invisible = await execute_tool("get_entity_detail", '{"entity_id": "ghost"}', _ctx())
    assert "不可见" in invisible, f"不可见实体必须返回占位说明: {invisible}"


async def test_neighborhood_visible_edges_only(graph_world: None) -> None:
    """U13: 一度关系只含可见边且名称可读（等价类-邻域投影）。"""
    text = await execute_tool("get_neighborhood", '{"entity_id": "char-a"}', _ctx())
    assert "周兰 -[ALLIES]-> 沈墨" in text, f"一度关系必须可读渲染: {text}"
    assert "周兰 -[LIVES]-> 青云山" in text, f"两条一度关系都要出现: {text}"

    ghost = await execute_tool("get_neighborhood", '{"entity_id": "ghost"}', _ctx())
    assert "不可见" in ghost, f"不可见实体的邻域查询必须给可读错误: {ghost}"


@pytest.mark.parametrize(
    ("q", "expect_ids"),
    [("周兰", ["char-a"]), ("兰姐", ["char-a"]), ("不存在", [])],
    ids=["命中名称", "命中别名", "空结果"],
)
async def test_search_entities_hit_paths(graph_world: None, q: str, expect_ids: list[str]) -> None:
    """U14 参数化: 检索命中名称/别名/空结果（等价类-检索命中三分支）。"""
    text = await execute_tool("search_entities", f'{{"q": "{q}"}}', _ctx())
    for entity_id in expect_ids:
        assert entity_id in text, f"[{q}] 命中实体必须出现在结果中: {text}"
    if not expect_ids:
        assert "无匹配" in text, f"[{q}] 空结果必须给占位说明: {text}"


@pytest.fixture
def doc_world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """注入文档世界：1 文档 2 段（repository mock 成内存结构）。"""
    docs = {
        "mdoc-1": SimpleNamespace(id="mdoc-1", project_id="proj-1", kind="style", title="风格约定"),
    }
    sections = {
        "msec-1": SimpleNamespace(
            id="msec-1", doc_id="mdoc-1", seq=1, title="叙事视角", content="第一人称。", version=1
        ),
        "msec-2": SimpleNamespace(
            id="msec-2", doc_id="mdoc-1", seq=2, title="影像风格", content="冷色调。", version=1
        ),
    }

    async def fake_get_doc(_s: Any, doc_id: str) -> Any:
        return docs.get(doc_id)

    async def fake_list_sections(_s: Any, doc_id: str) -> list[Any]:
        return [s for s in sections.values() if s.doc_id == doc_id]

    monkeypatch.setattr(repository, "get_doc", fake_get_doc)
    monkeypatch.setattr(repository, "list_sections", fake_list_sections)
    return {"docs": docs, "sections": sections}


@pytest.mark.parametrize(
    ("seq_json", "expect"),
    [
        ("1", "第一人称。"),
        ("2", "冷色调。"),
        ("0", "不存在第 0 段"),
        ("3", "不存在第 3 段"),
        ('"abc"', "seq 非法"),
        ("null", "seq 非法"),
    ],
    ids=["有效段1", "有效段2", "越界-0", "越界-上限+1", "seq非整数", "seq缺省null"],
)
async def test_read_doc_section_boundaries(
    doc_world: dict[str, Any], seq_json: str, expect: str
) -> None:
    """U15 参数化: 段读取有效/越界/参数非法（边界值-序号两侧邻界；等价类-无效-参数类型）。

    设计依据: seq 非整数与缺省走 int 解析失败分支，折叠为三要素文本（不抛异常）。
    """
    text = await execute_tool(
        "read_doc_section", f'{{"doc_id": "mdoc-1", "seq": {seq_json}}}', _ctx()
    )
    assert expect in text, f"[seq={seq_json}] 结果不符: {text}"


async def test_read_doc_section_rejects_cross_project(doc_world: dict[str, Any]) -> None:
    """U15 补充: 跨项目文档读取被拒（等价类-无效-越权归属）。"""
    doc_world["docs"]["mdoc-2"] = SimpleNamespace(
        id="mdoc-2", project_id="proj-OTHER", kind="style", title="别家的文档"
    )
    text = await execute_tool("read_doc_section", '{"doc_id": "mdoc-2", "seq": 1}', _ctx())
    assert "工具执行失败" in text, f"跨项目读取必须被拒: {text}"


@pytest.mark.parametrize(
    ("name", "args"),
    [("no_such_tool", "{}"), ("search_entities", "not-json"), ("search_entities", "[1,2]")],
    ids=["未知工具", "参数非JSON", "参数非对象"],
)
async def test_execute_tool_failures_fold_to_text(name: str, args: str) -> None:
    """补充: 未知工具/坏参数折叠为三要素文本，不抛异常（等价类-无效-调用失当）。"""
    text = await execute_tool(name, args, _ctx())
    assert "工具执行失败" in text and "修复" in text, f"失败必须折叠为可读文本: {text}"

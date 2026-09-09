"""agent 工具 L1 单元测试：检索（F10）与写入登记（F14，全 mock 内存执行）。

覆盖: 检索四工具的有效/无效等价类、seq 边界、跨项目拒绝；写入五工具的
白名单登记/目标校验/名称解析/CAS 基线/轮内上限。用例设计（等价类/边界值
标注）见 docs/tests/F10_agent_chat.md 与 docs/tests/F14_agent_write_tools.md。
"""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import repository, tools
from app.agent.tools import ToolContext, execute_tool
from app.core.exceptions import NotFoundError
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


# ---- F14：写入工具（登记 pending ≠ 落库；U1-U9 见 docs/tests/F14_agent_write_tools.md）----


class WriteSettingsStub:
    """写入工具配置桩（轮内上限可调）。"""

    def __init__(self, limit: int = 8) -> None:
        self.agent_max_pending_writes = limit


@pytest.fixture
def write_world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """注入写入世界：待写入内存存储 + 文档/段 + 配置桩（每用例独享）。"""
    pendings: list[Any] = []
    docs = {
        "mdoc-1": SimpleNamespace(
            id="mdoc-1", project_id="proj-1", kind="style", title="风格约定", version=1
        ),
    }
    sections = {
        "msec-1": SimpleNamespace(
            id="msec-1",
            doc_id="mdoc-1",
            seq=1,
            title="叙事视角",
            content="第一人称。",
            version=3,
            updated_by="user",
        ),
        "msec-2": SimpleNamespace(
            id="msec-2",
            doc_id="mdoc-1",
            seq=2,
            title="影像风格",
            content="冷色调。",
            version=3,
            updated_by="user",
        ),
    }

    async def fake_add_pending(_s: Any, pending: Any) -> Any:
        pending.status = "pending"
        pendings.append(pending)
        return pending

    async def fake_get_pending(_s: Any, pending_id: str) -> Any:
        return next((p for p in pendings if p.id == pending_id), None)

    async def fake_find_doc_by_kind(_s: Any, project_id: str, kind: str) -> Any:
        return next(
            (d for d in docs.values() if d.project_id == project_id and d.kind == kind), None
        )

    async def fake_get_doc(_s: Any, doc_id: str) -> Any:
        return docs.get(doc_id)

    async def fake_list_sections(_s: Any, doc_id: str) -> list[Any]:
        return [s for s in sections.values() if s.doc_id == doc_id]

    monkeypatch.setattr(repository, "add_pending", fake_add_pending)
    monkeypatch.setattr(repository, "get_pending", fake_get_pending)
    monkeypatch.setattr(repository, "find_doc_by_kind", fake_find_doc_by_kind)
    monkeypatch.setattr(repository, "get_doc", fake_get_doc)
    monkeypatch.setattr(repository, "list_sections", fake_list_sections)
    monkeypatch.setattr(tools, "get_settings", lambda: WriteSettingsStub(8))
    return {"pendings": pendings, "docs": docs, "sections": sections}


def _wctx() -> ToolContext:
    """写入工具执行上下文（会话归属 proj-1/conv-1）。"""
    return ToolContext(
        session=_SESSION, project_id="proj-1", perspective="author", conversation_id="conv-1"
    )


def _payload(world: dict[str, Any], index: int = -1) -> dict[str, Any]:
    """取第 index 条登记的 payload 反序列化。"""
    return json.loads(world["pendings"][index].payload_json)


async def test_create_entity_registers_pending(
    write_world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F14-U1: create_entity 有效登记（有效类-白名单字段全量）→ 行字段与结果正确。

    设计依据: 等价类-有效（type/name/description/aliases/properties 全量）。
    """
    text = await execute_tool(
        "create_entity",
        json.dumps(
            {
                "type": "character",
                "name": "周兰",
                "description": "船医",
                "aliases": ["兰医生"],
                "audience_known": True,
                "properties": {"age": 30},
            },
            ensure_ascii=False,
        ),
        _wctx(),
    )
    assert "已登记" in text and "待作者" in text and "尚未写入" in text, (
        f"登记成功必须声明待确认且未落库: {text}"
    )
    row = write_world["pendings"][0]
    assert row.kind == "create_entity" and row.conversation_id == "conv-1"
    assert row.project_id == "proj-1" and row.status == "pending"
    payload = _payload(write_world)
    assert payload["name"] == "周兰" and payload["type"] == "character"
    assert payload["aliases"] == ["兰医生"] and payload["properties"] == {"age": 30}


@pytest.mark.parametrize(
    "extra",
    [{"id": "ent-hack"}, {"project_id": "proj-other"}, {"unknown_key": 1}],
    ids=["携带id", "携带project_id", "未知字段"],
)
async def test_create_entity_strips_non_whitelist_fields(
    write_world: dict[str, Any], extra: dict[str, Any]
) -> None:
    """F14-U2 参数化: 服务端注入字段/未知键被白名单剔除（无效类-多余字段）。"""
    await execute_tool(
        "create_entity",
        json.dumps({"type": "item", "name": "罗盘", **extra}, ensure_ascii=False),
        _wctx(),
    )
    payload = _payload(write_world)
    assert set(payload) == {
        "type",
        "name",
        "description",
        "aliases",
        "audience_known",
        "properties",
    }, f"payload 必须只含白名单字段: {payload}"


@pytest.mark.parametrize(
    "args",
    [{"name": "无类型"}, {"type": "item"}, {"type": "item", "name": ""}],
    ids=["缺type", "缺name", "name空串"],
)
async def test_create_entity_required_fields(
    write_world: dict[str, Any], args: dict[str, Any]
) -> None:
    """F14-U3 参数化: 必填缺失/空串 → 白名单校验错误文本，不登记（无效类-必填缺失）。"""
    text = await execute_tool("create_entity", json.dumps(args, ensure_ascii=False), _wctx())
    assert "白名单校验" in text, f"必须折叠为白名单校验错误: {text}"
    assert write_world["pendings"] == [], "校验失败不得登记"


@pytest.mark.parametrize(
    ("entity", "expect_registered", "label"),
    [
        (SimpleNamespace(id="ent-1", project_id="proj-1", name="阿诚"), True, "有效-本项目实体"),
        (None, False, "无效-不存在"),
        (SimpleNamespace(id="ent-2", project_id="proj-OTHER", name="他者"), False, "无效-跨项目"),
    ],
    ids=["有效-本项目", "无效-不存在", "无效-跨项目"],
)
async def test_update_entity_target_validation(
    write_world: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    entity: Any,
    expect_registered: bool,
    label: str,
) -> None:
    """F14-U4 参数化: 目标存在且同项目才登记（exclude_unset 仅显式字段）。"""

    async def fake_get(_s: Any, _entity_id: str) -> Any:
        if entity is None:
            raise NotFoundError(problem="实体不存在", cause="id 未命中", fix="检索后重试")
        return entity

    async def fake_filter(_s: Any, *, entity_ids: list[str], **_: Any) -> list[Any]:
        return [SimpleNamespace(id=i) for i in entity_ids]

    monkeypatch.setattr(entities_service, "get", fake_get)
    monkeypatch.setattr(perspectives_service, "filter_entities_for_agent", fake_filter)
    text = await execute_tool(
        "update_entity",
        json.dumps({"entity_id": "ent-1", "description": "新简介"}, ensure_ascii=False),
        _wctx(),
    )
    assert label
    if expect_registered:
        assert "已登记" in text, f"有效目标必须登记: {text}"
        payload = _payload(write_world)
        assert payload["entity_id"] == "ent-1" and payload["entity_name"] == "阿诚"
        assert payload["description"] == "新简介" and "name" not in payload, (
            f"仅显式提供字段进入 payload: {payload}"
        )
    else:
        assert "工具执行失败" in text and write_world["pendings"] == []


async def test_update_entity_empty_patch_rejected(
    write_world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F14-U4 补充: 无任何更新字段 → 三要素错误（无效类-空补丁）。"""

    async def fake_get(_s: Any, _entity_id: str) -> Any:
        return SimpleNamespace(id="ent-1", project_id="proj-1", name="阿诚")

    async def fake_filter(_s: Any, *, entity_ids: list[str], **_: Any) -> list[Any]:
        return [SimpleNamespace(id=i) for i in entity_ids]

    monkeypatch.setattr(entities_service, "get", fake_get)
    monkeypatch.setattr(perspectives_service, "filter_entities_for_agent", fake_filter)
    text = await execute_tool("update_entity", '{"entity_id": "ent-1"}', _wctx())
    assert "未携带任何更新字段" in text and write_world["pendings"] == []


@pytest.mark.parametrize(
    ("briefs", "expect_hit", "label"),
    [
        ([SimpleNamespace(id="ent-a", name="阿诚", aliases=[])], True, "有效-名称精确命中"),
        ([SimpleNamespace(id="ent-b", name="周老太", aliases=["阿诚"])], True, "有效-别名命中"),
        ([SimpleNamespace(id="ent-c", name="无关者", aliases=[])], False, "无效-未命中"),
    ],
    ids=["名称命中", "别名命中", "未命中"],
)
async def test_create_relation_name_resolution(
    write_world: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    briefs: list[Any],
    expect_hit: bool,
    label: str,
) -> None:
    """F14-U5 参数化: 端点名称/别名精确解析为 id（经视角过滤）；未命中提示先检索。"""

    async def fake_search(
        _s: Any, q: str = "", project_id: str | None = None, **_: Any
    ) -> list[Any]:
        assert project_id == "proj-1", "名称解析必须在会话项目内"
        return briefs

    async def fake_filter(_s: Any, *, entity_ids: list[str], **_: Any) -> list[Any]:
        # 全部放行（视角可见）；不可见分支由 test_update_entity_perspective_guard 覆盖
        return [SimpleNamespace(id=i) for i in entity_ids]

    monkeypatch.setattr(entities_service, "search", fake_search)
    monkeypatch.setattr(perspectives_service, "filter_entities_for_agent", fake_filter)
    text = await execute_tool(
        "create_relation",
        json.dumps(
            {"source_name": "阿诚", "target_name": "阿诚", "relation_type": "师徒"},
            ensure_ascii=False,
        ),
        _wctx(),
    )
    assert label
    if expect_hit:
        assert "已登记" in text, f"命中必须登记: {text}"
        payload = _payload(write_world)
        assert payload["source"] == briefs[0].id and payload["type"] == "师徒"
    else:
        assert "关系端点未命中" in text and write_world["pendings"] == []


async def test_create_relation_resolves_known_by_names(
    write_world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F14-U5 补充（P1-1 审查修复）: known_by 成员名称登记时解析为实体 id。

    设计依据: 等价类-有效（成员名称命中）；缺失该解析 approve 会因
    relations service 校验 id 而恒失败。
    """
    resolve_targets = {
        "阿诚": ("ok", "ent-a", "阿诚"),
        "老周": ("ok", "ent-b", "老周"),
        "小翠": ("ok", "ent-c", "小翠"),
    }

    async def fake_resolve(_ctx: Any, name: str) -> tuple[str, str, str]:
        return resolve_targets[name]

    monkeypatch.setattr(tools, "_resolve_entity_by_name", fake_resolve)
    text = await execute_tool(
        "create_relation",
        json.dumps(
            {
                "source_name": "阿诚",
                "target_name": "老周",
                "relation_type": "师徒",
                "known_by": ["阿诚", "小翠"],
            },
            ensure_ascii=False,
        ),
        _wctx(),
    )
    assert "已登记" in text, f"known_by 命中必须登记: {text}"
    payload = _payload(write_world)
    assert payload["known_by"] == ["ent-a", "ent-c"], (
        f"known_by 必须解析为 id 列表（与 source/target 同路径）: {payload}"
    )


async def test_create_relation_known_by_name_unresolved(
    write_world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F14-U5 补充（无效类）: known_by 成员名称未命中 → 三要素错误，不登记。"""

    async def fake_resolve(_ctx: Any, name: str) -> tuple[str, str, str]:
        if name in ("阿诚", "老周"):
            return ("ok", f"ent-{name}", name)
        return ("miss", "", name)

    monkeypatch.setattr(tools, "_resolve_entity_by_name", fake_resolve)
    text = await execute_tool(
        "create_relation",
        json.dumps(
            {
                "source_name": "阿诚",
                "target_name": "老周",
                "relation_type": "师徒",
                "known_by": ["路人甲"],
            },
            ensure_ascii=False,
        ),
        _wctx(),
    )
    assert "关系端点未命中" in text and "路人甲" in text, f"未命中成员必须三要素错误: {text}"
    assert write_world["pendings"] == []


@pytest.mark.parametrize(
    ("target", "expect_ok", "label"),
    [
        ("ok", True, "有效-可见实体"),
        ("invisible", False, "无效-视角不可见"),
        ("miss", False, "无效-不存在"),
    ],
    ids=["可见", "不可见", "不存在"],
)
async def test_update_entity_perspective_guard(
    write_world: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    expect_ok: bool,
    label: str,
) -> None:
    """F14-U4 视角守卫参数化（P1-2 审查修复）: update_entity 目标名称快照进
    上下文前必须过视角过滤——不可见实体拒绝登记（存在性不泄露）。"""
    assert label

    async def fake_get(_s: Any, _entity_id: str) -> Any:
        if target == "miss":
            raise NotFoundError(problem="实体不存在", cause="id 未命中", fix="检索后重试")
        return SimpleNamespace(id="ent-1", project_id="proj-1", name="机密人物")

    async def fake_filter(_s: Any, *, entity_ids: list[str], **__: Any) -> list[Any]:
        return [] if target == "invisible" else [SimpleNamespace(id=i) for i in entity_ids]

    monkeypatch.setattr(entities_service, "get", fake_get)
    monkeypatch.setattr(perspectives_service, "filter_entities_for_agent", fake_filter)
    text = await execute_tool(
        "update_entity",
        json.dumps({"entity_id": "ent-1", "description": "x"}, ensure_ascii=False),
        _wctx(),
    )
    if expect_ok:
        assert "已登记" in text
    else:
        assert "工具执行失败" in text and write_world["pendings"] == []
        if target == "invisible":
            assert "不可见" in text, f"不可见分支必须显式提示: {text}"


@pytest.mark.parametrize(
    ("kind", "existing", "expect_ok", "label"),
    [
        ("positioning", False, True, "有效-模板合法且无重复"),
        ("unknown_kind", False, False, "无效-未知模板"),
        ("style", True, False, "无效-指导类已存在"),
    ],
    ids=["有效", "未知kind", "指导类重复"],
)
async def test_create_memory_doc_validation(
    write_world: dict[str, Any], kind: str, existing: bool, expect_ok: bool, label: str
) -> None:
    """F14-U6 参数化: 模板合法 + 指导类查重通过才登记（title 透传）。

    write_world 预置 mdoc-1（kind=style）：请求 positioning 无重复、请求
    style 命中重复，天然覆盖查重两分支。
    """
    text = await execute_tool(
        "create_memory_doc",
        json.dumps({"kind": kind, "title": "自定义标题"}, ensure_ascii=False),
        _wctx(),
    )
    assert label
    if expect_ok:
        assert "已登记" in text
        payload = _payload(write_world)
        assert payload == {"kind": "positioning", "title": "自定义标题"}
    else:
        assert "工具执行失败" in text and write_world["pendings"] == []


async def test_create_memory_doc_title_defaults_to_template(
    write_world: dict[str, Any],
) -> None:
    """F14-U6 补充: title 缺省取模板默认标题（边界值-缺省）。"""
    await execute_tool("create_memory_doc", '{"kind": "positioning"}', _wctx())
    payload = _payload(write_world)
    assert payload["title"] == "世界观定位", f"缺省 title 必须为模板标题: {payload}"


@pytest.mark.parametrize(
    ("doc_id", "seq", "expect_ok", "label"),
    [
        ("mdoc-1", 2, True, "有效-doc 与段存在"),
        ("mdoc-x", 1, False, "无效-doc 不存在"),
        ("mdoc-1", 9, False, "无效-seq 越界"),
        ("mdoc-2", 1, False, "无效-跨项目 doc"),
    ],
    ids=["有效", "doc不存在", "seq越界", "跨项目"],
)
async def test_write_doc_section_validation(
    write_world: dict[str, Any], doc_id: str, seq: int, expect_ok: bool, label: str
) -> None:
    """F14-U7 参数化: doc 存在/同项目/段在界才登记（登记时记录段版本 CAS 基线）。"""
    write_world["docs"]["mdoc-2"] = SimpleNamespace(
        id="mdoc-2", project_id="proj-OTHER", kind="style", title="别家的文档", version=1
    )
    text = await execute_tool(
        "write_doc_section",
        json.dumps({"doc_id": doc_id, "seq": seq, "content": "新内容"}, ensure_ascii=False),
        _wctx(),
    )
    assert label
    if expect_ok:
        assert "已登记" in text
        row = write_world["pendings"][0]
        payload = json.loads(row.payload_json)
        assert payload["content"] == "新内容" and payload["doc_title"] == "风格约定"
        baseline = json.loads(row.baseline_json)
        assert baseline == {"section_id": "msec-2", "expected_version": 3}, (
            f"基线必须记录段当前版本: {baseline}"
        )
    else:
        assert "工具执行失败" in text and write_world["pendings"] == []


async def test_pending_limit_boundary(
    write_world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F14-U8 边界值: 第 N=上限 项恰好成功；第 +1 项失败（错误文本不打断轮）。"""
    monkeypatch.setattr(tools, "get_settings", lambda: WriteSettingsStub(2))
    ctx = _wctx()  # 上限计数挂在同一轮上下文（三次调用必须共享 ctx）
    for i in range(2):
        text = await execute_tool(
            "create_entity",
            json.dumps({"type": "item", "name": f"物品{i}"}, ensure_ascii=False),
            ctx,
        )
        assert "已登记" in text, f"上限内第 {i + 1} 项必须成功: {text}"
    third = await execute_tool(
        "create_entity",
        json.dumps({"type": "item", "name": "超限"}, ensure_ascii=False),
        ctx,
    )
    assert "已达上限" in third, f"超限项必须错误文本: {third}"
    assert len(write_world["pendings"]) == 2, "超限不得登记"


def test_tool_specs_cover_nine_tools() -> None:
    """F14-U9: 四检索 + 五写入工具名稳定（prompt 契约回归）。"""
    names = {spec["function"]["name"] for spec in tools.TOOL_SPECS}
    assert names == {
        "search_entities",
        "get_entity_detail",
        "get_neighborhood",
        "read_doc_section",
        "create_entity",
        "update_entity",
        "create_relation",
        "create_memory_doc",
        "write_doc_section",
    }, f"工具集必须为九件: {names}"

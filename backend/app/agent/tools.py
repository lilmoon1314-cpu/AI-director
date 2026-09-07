"""agent 模块检索工具：受控 ReAct 的图谱与记忆文档按需读取。

设计约束:
    - 一切图谱数据经 perspectives（视角过滤单一事实源）；本模块禁止直查
      entities/relations 的写路径，也禁止 import 其 schemas（经 service 层）。
    - 工具结果一律为纯文本数据（service 注入前经 wrap_data 包裹 + 截断）；
      工具内部失败返回可读错误文本（模型可自纠），不抛异常打断对话轮。
"""

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import repository
from app.agent.prompts import render_entity_details
from app.agent.schemas import Perspective
from app.entities import service as entities_service
from app.perspectives import service as perspectives_service

# 工具定义（openai function 格式；名称/描述是 prompt 契约的一部分）
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": "按名称或别名检索项目内当前视角可见的实体，返回完整详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "检索关键词（名称或别名片段）"}
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_detail",
            "description": "按 id 查看单个实体的完整属性（须为当前视角可见实体）。",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string", "description": "实体 id"}},
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_neighborhood",
            "description": "查看某实体的全部一度关系（仅当前视角可见的关系）。",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string", "description": "实体 id"}},
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_doc_section",
            "description": "按段读取记忆文档的完整内容（doc_id 与段号见文档目录）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id"},
                    "seq": {"type": "integer", "description": "段序号（从 1 开始）"},
                },
                "required": ["doc_id", "seq"],
            },
        },
    },
]


@dataclass
class ToolContext:
    """工具执行上下文（一次对话轮内共享）。

    参数: session — 数据库会话（对话轮自管理）；project_id — 会话归属项目；
        perspective — 当前视角；character_id — character 视角的角色 id。
    返回值: 无（数据类）。异常: 无。依赖: 无。
    """

    session: AsyncSession
    project_id: str
    perspective: Perspective
    character_id: str = ""


def _error_result(problem: str, cause: str, fix: str) -> str:
    """工具失败的可读结果文本（三要素，模型可据此自纠）。

    参数: problem/cause/fix — 三要素。返回值: str。异常: 无。依赖: 无。
    """
    return f"工具执行失败。问题：{problem} 原因：{cause} 修复：{fix}"


async def _tool_search_entities(ctx: ToolContext, args: dict[str, Any]) -> str:
    """search_entities 实现：名称/别名检索 + 视角过滤 + 完整详情。"""
    q = str(args.get("q", ""))
    briefs = await entities_service.search(ctx.session, q=q, project_id=ctx.project_id)
    visible = await perspectives_service.filter_entities_for_agent(
        ctx.session,
        perspective=ctx.perspective,
        character_id=ctx.character_id or None,
        project_id=ctx.project_id,
        entity_ids=[b.id for b in briefs],
    )
    return render_entity_details(visible)


async def _tool_get_entity_detail(ctx: ToolContext, args: dict[str, Any]) -> str:
    """get_entity_detail 实现：单实体完整属性（不可见/不存在返回占位说明）。"""
    entity_id = str(args.get("entity_id", ""))
    visible = await perspectives_service.filter_entities_for_agent(
        ctx.session,
        perspective=ctx.perspective,
        character_id=ctx.character_id or None,
        project_id=ctx.project_id,
        entity_ids=[entity_id],
    )
    return render_entity_details(visible)


async def _tool_get_neighborhood(ctx: ToolContext, args: dict[str, Any]) -> str:
    """get_neighborhood 实现：一度关系的可读文本（仅可见边，名称来自可见节点）。"""
    entity_id = str(args.get("entity_id", ""))
    graph = await perspectives_service.get_graph(
        ctx.session,
        perspective=ctx.perspective,
        character_id=ctx.character_id or None,
        project_id=ctx.project_id,
    )
    names = {n.id: n.name for n in graph.nodes}
    if entity_id not in names:
        return _error_result(
            problem=f"实体 {entity_id} 不在当前视角可见范围内",
            cause="该实体不存在，或对当前视角不可见（视角过滤拦截）",
            fix="先用 search_entities 确认实体 id 后重试",
        )
    lines = [
        f"{names.get(e.source, e.source)} -[{e.type}]-> {names.get(e.target, e.target)} (id:{e.id})"
        for e in graph.edges
        if entity_id in (e.source, e.target)
    ]
    if not lines:
        return f"实体 {names[entity_id]} 当前视角下没有可见关系"
    return "\n".join(lines)


async def _tool_read_doc_section(ctx: ToolContext, args: dict[str, Any]) -> str:
    """read_doc_section 实现：单段全文（跨项目文档拒绝）。"""
    doc_id = str(args.get("doc_id", ""))
    try:
        # 缺省空串触发 ValueError 走统一错误分支（seq 必填）
        seq = int(args.get("seq", ""))
    except (TypeError, ValueError):
        return _error_result(
            problem="read_doc_section 参数 seq 非法",
            cause=f"seq 需要整数，收到 {args.get('seq')!r}",
            fix="以文档目录中的段序号重试",
        )
    doc = await repository.get_doc(ctx.session, doc_id)
    if doc is None or doc.project_id != ctx.project_id:
        return _error_result(
            problem=f"记忆文档 {doc_id} 不存在",
            cause="文档 id 错误，或不属于当前会话的项目（跨项目读取被拒）",
            fix="以文档目录中的 doc_id 重试",
        )
    sections = await repository.list_sections(ctx.session, doc_id)
    for sec in sections:
        if sec.seq == seq:
            return f"《{doc.title}》第 {sec.seq} 段「{sec.title}」：\n\n{sec.content}"
    return _error_result(
        problem=f"文档 {doc_id} 不存在第 {seq} 段",
        cause=f"该文档共 {len(sections)} 段，段号越界",
        fix="以文档目录中的段序号重试",
    )


_TOOL_IMPLS = {
    "search_entities": _tool_search_entities,
    "get_entity_detail": _tool_get_entity_detail,
    "get_neighborhood": _tool_get_neighborhood,
    "read_doc_section": _tool_read_doc_section,
}


async def execute_tool(name: str, arguments: str, ctx: ToolContext) -> str:
    """执行单个工具调用并返回文本结果（失败返回三要素错误文本，不抛异常）。

    作用: 受控 ReAct 的工具出口——参数 JSON 解析失败、未知工具名、工具内部
        业务失败均折叠为可读文本，保证对话轮不被打断。
    参数: name — 工具名；arguments — JSON 参数串；ctx — 执行上下文。
    返回值: str — 工具结果文本（由调用方包裹/截断后注入）。
    异常: 无（全部失败模式折叠为文本）。
    依赖: _TOOL_IMPLS。
    """
    impl = _TOOL_IMPLS.get(name)
    if impl is None:
        return _error_result(
            problem=f"未知工具 {name}",
            cause="工具名不在可用集合内",
            fix=f"改用以下工具之一：{', '.join(sorted(_TOOL_IMPLS))}",
        )
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return _error_result(
            problem=f"工具 {name} 的参数不是合法 JSON",
            cause=f"收到参数串：{arguments[:200]}",
            fix="以合法 JSON 对象重新调用",
        )
    if not isinstance(args, dict):
        return _error_result(
            problem=f"工具 {name} 的参数必须是 JSON 对象",
            cause=f"收到 {type(args).__name__}",
            fix="以 JSON 对象（键值对）重新调用",
        )
    return await impl(ctx, args)

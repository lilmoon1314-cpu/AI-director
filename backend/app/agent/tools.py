"""agent 模块工具：受控 ReAct 的图谱/文档读取与写入登记（F14 轮末统一确认）。

设计约束:
    - 一切图谱数据经 perspectives（视角过滤单一事实源）；本模块禁止直查
      entities/relations 的写路径，也禁止 import 其 schemas（经 service 层）。
    - 写入类工具执行 ≠ 落库——仅登记 agent_pending_writes（随对话轮事务
      提交/回滚），返回「已登记待作者确认」tool result；落库只发生在
      service.approve_pending_writes（服务端复核，OQ-8）。
    - 工具结果一律为纯文本数据（service 注入前经 wrap_data 包裹 + 截断）；
      工具内部失败返回可读错误文本（模型可自纠），不抛异常打断对话轮
      （参数白名单校验失败折叠为文本；repository 层运行时异常仍上抛，
      由 stream_chat 统一转 error 事件）。
    - 写入参数经 Pydantic 白名单模型（extra=ignore 剔除多余字段；id/
      project_id 等服务端注入字段不可经工具参数指定）。
"""

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import repository
from app.agent.models import PendingWrite
from app.agent.prompts import render_entity_details
from app.agent.schemas import Perspective, generate_pending_write_id
from app.agent.templates import DOC_TEMPLATES, GUIDE_KINDS
from app.config import get_settings
from app.core.exceptions import NotFoundError
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
    # ---- 写入类工具（F14：执行仅登记待写入，落库需作者在轮末确认卡批准）----
    {
        "type": "function",
        "function": {
            "name": "create_entity",
            "description": (
                "登记新建实体（不立即写入——待作者在本轮结束的确认卡批准后生效；"
                "实体类型：character/faction/location/item/skill/event/concept）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "实体类型"},
                    "name": {"type": "string", "description": "实体名称（必填）"},
                    "description": {"type": "string", "description": "简介"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "别名列表",
                    },
                    "audience_known": {
                        "type": "boolean",
                        "description": "观众视角是否已知（缺省 false）",
                    },
                    "properties": {"type": "object", "description": "类型扩展属性"},
                },
                "required": ["type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_entity",
            "description": (
                "登记更新实体属性（不立即写入——待作者确认后生效）；"
                "properties_patch 为与既有属性的浅合并补丁。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 id"},
                    "name": {"type": "string", "description": "新名称（可选）"},
                    "description": {"type": "string", "description": "新简介（可选）"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新别名全量列表（可选，整体替换）",
                    },
                    "audience_known": {"type": "boolean", "description": "（可选）"},
                    "properties_patch": {
                        "type": "object",
                        "description": "属性补丁（浅合并进既有 properties）",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_relation",
            "description": (
                "登记新建关系（不立即写入——待作者确认后生效）；端点用实体名称"
                "（或别名）指定，登记时解析为实体 id，未命中会返回错误提示先检索。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "description": "源实体名称"},
                    "target_name": {"type": "string", "description": "目标实体名称"},
                    "relation_type": {"type": "string", "description": "关系类型"},
                    "known_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "知晓该关系的角色名称列表（可选）",
                    },
                    "trust": {"type": "number", "description": "信任 0-1（可选）"},
                    "intimacy": {"type": "number", "description": "亲密 0-1（可选）"},
                    "dependency": {"type": "number", "description": "依赖 0-1（可选）"},
                    "resentment": {"type": "number", "description": "怨恨 0-1（可选）"},
                },
                "required": ["source_name", "target_name", "relation_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_memory_doc",
            "description": (
                "登记按模板新建记忆文档（positioning/style，指导类每项目仅一份；"
                "不立即写入——待作者确认后生效）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "模板键（positioning/style）",
                    },
                    "title": {"type": "string", "description": "文档标题（可选，缺省模板标题）"},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_doc_section",
            "description": (
                "登记写入记忆文档单段内容（不立即写入——待作者确认后生效）；"
                "登记时记录段版本基线，作者此后手改该段则登记自动失效（CAS）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "文档 id"},
                    "seq": {"type": "integer", "description": "段序号（从 1 开始）"},
                    "content": {"type": "string", "description": "新段内容（全量替换）"},
                    "title": {"type": "string", "description": "新段标题（可选）"},
                },
                "required": ["doc_id", "seq", "content"],
            },
        },
    },
]


@dataclass
class ToolContext:
    """工具执行上下文（一次对话轮内共享）。

    参数: session — 数据库会话（对话轮自管理）；project_id — 会话归属项目；
        perspective — 当前视角；character_id — character 视角的角色 id；
        conversation_id — 会话 id（写入登记行的归属键）；
        pending_writes — 本轮登记的待写入行（service 轮末放进 done 事件；
        登记行属对话轮事务，轮失败回滚则一并消失）。
    返回值: 无（数据类）。异常: 无。依赖: 无。
    """

    session: AsyncSession
    project_id: str
    perspective: Perspective
    character_id: str = ""
    conversation_id: str = ""
    pending_writes: list[PendingWrite] = field(default_factory=list)


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


# ---- 写入类工具（F14：登记 ≠ 落库，OQ-8 轮末统一确认）----

# 参数白名单模型：extra=ignore 剔除多余字段（id/project_id 等服务端注入字段
# 不在白名单内，工具参数即使携带也不会进入登记 payload）


class _CreateEntityArgs(BaseModel):
    """create_entity 参数白名单。"""

    model_config = ConfigDict(extra="ignore")

    type: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    audience_known: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class _UpdateEntityArgs(BaseModel):
    """update_entity 参数白名单（仅显式提供的字段进入登记 payload）。"""

    model_config = ConfigDict(extra="ignore")

    entity_id: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    aliases: list[str] | None = None
    audience_known: bool | None = None
    properties_patch: dict[str, Any] | None = None


class _CreateRelationArgs(BaseModel):
    """create_relation 参数白名单（端点经名称解析为 id）。"""

    model_config = ConfigDict(extra="ignore")

    source_name: str = Field(min_length=1, max_length=200)
    target_name: str = Field(min_length=1, max_length=200)
    relation_type: str = Field(min_length=1, max_length=100)
    known_by: list[str] = Field(default_factory=list)
    trust: float | None = Field(default=None, ge=0.0, le=1.0)
    intimacy: float | None = Field(default=None, ge=0.0, le=1.0)
    dependency: float | None = Field(default=None, ge=0.0, le=1.0)
    resentment: float | None = Field(default=None, ge=0.0, le=1.0)


class _CreateMemoryDocArgs(BaseModel):
    """create_memory_doc 参数白名单。"""

    model_config = ConfigDict(extra="ignore")

    kind: str = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class _WriteDocSectionArgs(BaseModel):
    """write_doc_section 参数白名单。"""

    model_config = ConfigDict(extra="ignore")

    doc_id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    content: str = Field(min_length=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)


def _limit_reached_result(limit: int) -> str:
    """本轮待写入达到上限的可读结果文本（三要素）。"""
    return _error_result(
        problem=f"本轮待写入登记已达上限（{limit} 项）",
        cause="为控制确认复杂度，单轮登记数量有上限",
        fix="先总结当前进展请作者确认本轮已登记项，下一轮再继续",
    )


async def _register_pending(
    ctx: ToolContext,
    kind: str,
    payload: dict[str, Any],
    summary: str,
    baseline: dict[str, Any] | None = None,
) -> str | None:
    """登记一条待写入行（超限返回错误文本，成功返回 None）。

    作用: 写入工具共用出口——上限判定 + ORM 落行（flush 不 commit，随
        对话轮事务）+ 轮内累积（service 轮末放入 done 事件清单）。
    参数: ctx — 工具上下文；kind — 写入类别；payload — 白名单化参数；
        summary — 一句话摘要（登记成功文本使用）；baseline — 段 CAS 基线。
    返回值: str | None — 超限时为错误文本，成功为 None。
    异常: 无。依赖: app.agent.repository、app.config。
    """
    limit = get_settings().agent_max_pending_writes
    if len(ctx.pending_writes) >= limit:
        return _limit_reached_result(limit)
    row = PendingWrite(
        id=generate_pending_write_id(),
        conversation_id=ctx.conversation_id,
        project_id=ctx.project_id,
        kind=kind,
        payload_json=json.dumps(payload, ensure_ascii=False),
        baseline_json=json.dumps(baseline, ensure_ascii=False) if baseline is not None else None,
    )
    row = await repository.add_pending(ctx.session, row)
    ctx.pending_writes.append(row)
    return None


def _registered_result(summary: str) -> str:
    """登记成功的 tool result（告知模型未落库、待作者确认）。"""
    return (
        f"已登记写入申请：{summary}。该项尚未写入——待作者在本轮结束的"
        "确认卡批准后生效，请勿声称已写入。"
    )


async def _resolve_entity_by_name(ctx: ToolContext, name: str) -> tuple[str, str, bool]:
    """按名称/别名精确解析项目内实体（三态：未命中/不可见/可见命中）。

    作用: 解析结果（名称快照）经工具结果注入 LLM 上下文——必须过 perspectives
        视角过滤（agent/CONSTRAINTS.md：禁止注入当前视角不可见的实体）。
    参数: ctx — 工具上下文；name — 名称或别名。
    返回值: (状态, id, 名称)——状态 "miss"（项目内无此名/别名）|
        "invisible"（存在但当前视角不可见）| "ok"。
    异常: 无。依赖: entities_service.search、perspectives_service.filter_entities_for_agent。
    """
    briefs = await entities_service.search(ctx.session, q=name, project_id=ctx.project_id)
    lowered = name.strip().lower()
    matched = [
        b for b in briefs if b.name.lower() == lowered or lowered in (a.lower() for a in b.aliases)
    ]
    if not matched:
        return ("miss", "", name)
    visible = await perspectives_service.filter_entities_for_agent(
        ctx.session,
        perspective=ctx.perspective,
        character_id=ctx.character_id or None,
        project_id=ctx.project_id,
        entity_ids=[b.id for b in matched],
    )
    visible_ids = {e.id for e in visible}
    for brief in matched:
        if brief.id in visible_ids:
            return ("ok", brief.id, brief.name)
    return ("invisible", matched[0].id, name)


def _entity_not_visible_error(entity_ref: str) -> str:
    """目标实体对当前视角不可见的工具错误文本（三要素）。"""
    return _error_result(
        problem=f"实体「{entity_ref}」对当前视角不可见",
        cause="名称存在但视角过滤未放行（角色/观众视角下不可见实体不参与写入）",
        fix="切换到 author 视角，或改用当前视角可见的实体",
    )


async def _tool_create_entity(ctx: ToolContext, args: dict[str, Any]) -> str:
    """create_entity 实现：登记新建实体（不落库）。"""
    parsed = _CreateEntityArgs(**args)
    payload = parsed.model_dump()
    summary = f"新增实体「{payload['name']}」（{payload['type']}）"
    limit_error = await _register_pending(ctx, "create_entity", payload, summary)
    return limit_error if limit_error is not None else _registered_result(summary)


async def _tool_update_entity(ctx: ToolContext, args: dict[str, Any]) -> str:
    """update_entity 实现：校验目标（项目 + 视角可见）后登记属性补丁（不落库）。"""
    parsed = _UpdateEntityArgs(**args)
    try:
        entity = await entities_service.get(ctx.session, parsed.entity_id)
    except NotFoundError:
        return _error_result(
            problem=f"实体 {parsed.entity_id} 不存在",
            cause="id 未命中本项目实体",
            fix="先用 search_entities 确认实体 id 后重试",
        )
    if entity.project_id != ctx.project_id:
        return _error_result(
            problem=f"实体 {parsed.entity_id} 不在当前项目",
            cause="跨项目更新被拒（会话与实体必须同项目）",
            fix="只在当前会话所属项目内更新实体",
        )
    # 目标名称快照进上下文——视角过滤放行才可登记（P1-2 审查修复）
    visible = await perspectives_service.filter_entities_for_agent(
        ctx.session,
        perspective=ctx.perspective,
        character_id=ctx.character_id or None,
        project_id=ctx.project_id,
        entity_ids=[entity.id],
    )
    if not visible:
        return _entity_not_visible_error(entity.name)
    patch = parsed.model_dump(exclude={"entity_id"}, exclude_unset=True)
    if not patch:
        return _error_result(
            problem="update_entity 未携带任何更新字段",
            cause="至少提供 name/description/aliases/audience_known/properties_patch 之一",
            fix="补充要修改的字段后重试",
        )
    payload = {"entity_id": parsed.entity_id, "entity_name": entity.name, **patch}
    summary = f"更新实体「{entity.name}」（{'、'.join(sorted(patch))}）"
    limit_error = await _register_pending(ctx, "update_entity", payload, summary)
    return limit_error if limit_error is not None else _registered_result(summary)


async def _tool_create_relation(ctx: ToolContext, args: dict[str, Any]) -> str:
    """create_relation 实现：端点与 known_by 名称解析为 id 后登记（不落库）。"""
    parsed = _CreateRelationArgs(**args)
    source = await _resolve_entity_by_name(ctx, parsed.source_name)
    target = await _resolve_entity_by_name(ctx, parsed.target_name)

    def _endpoint_error(label: str, raw: str, state: tuple[str, str, str]) -> str:
        """端点解析失败的分支文案（未命中 vs 视角不可见）。"""
        if state[0] == "invisible":
            return _entity_not_visible_error(raw)
        return _error_result(
            problem=f"关系端点未命中：{label}「{raw}」",
            cause="名称未精确匹配到当前项目的实体名或别名",
            fix="先用 search_entities 确认双方名称（或改用别名）后重试",
        )

    if source[0] != "ok":
        return _endpoint_error("source", parsed.source_name, source)
    if target[0] != "ok":
        return _endpoint_error("target", parsed.target_name, target)

    # known_by 成员同样是名称——登记时解析为 character 实体 id（P1-1 审查修复；
    # relations service 落库校验的是 id，透传名称会让 approve 恒失败）
    known_by_ids: list[str] = []
    for member_name in parsed.known_by:
        member = await _resolve_entity_by_name(ctx, member_name)
        if member[0] != "ok":
            return _endpoint_error("known_by 成员", member_name, member)
        known_by_ids.append(member[1])

    payload: dict[str, Any] = {
        "source": source[1],
        "target": target[1],
        "type": parsed.relation_type,
        "source_name": source[2],
        "target_name": target[2],
    }
    if known_by_ids:
        payload["known_by"] = known_by_ids
    for optional in ("trust", "intimacy", "dependency", "resentment"):
        value = getattr(parsed, optional)
        if value is not None:
            payload[optional] = value
    summary = f"新增关系：{source[2]} -[{parsed.relation_type}]-> {target[2]}"
    limit_error = await _register_pending(ctx, "create_relation", payload, summary)
    return limit_error if limit_error is not None else _registered_result(summary)


async def _tool_create_memory_doc(ctx: ToolContext, args: dict[str, Any]) -> str:
    """create_memory_doc 实现：模板校验 + 指导类查重后登记（不落库）。"""
    parsed = _CreateMemoryDocArgs(**args)
    template = DOC_TEMPLATES.get(parsed.kind)
    if template is None:
        return _error_result(
            problem=f"未知的记忆文档模板 kind '{parsed.kind}'",
            cause=f"kind 必须为内置模板之一（{', '.join(sorted(DOC_TEMPLATES))}）",
            fix="改用内置模板 kind",
        )
    if parsed.kind in GUIDE_KINDS:
        existing = await repository.find_doc_by_kind(ctx.session, ctx.project_id, parsed.kind)
        if existing is not None:
            return _error_result(
                problem=f"「{template['label']}」文档已存在（每项目仅一份）",
                cause=f"项目内已存在同 kind 文档《{existing.title}》（{existing.id}）",
                fix="改用 write_doc_section 直接编辑既有文档的对应段",
            )
    payload = {"kind": parsed.kind, "title": parsed.title or str(template["title"])}
    summary = f"新建文档「{payload['title']}」（{parsed.kind}）"
    limit_error = await _register_pending(ctx, "create_memory_doc", payload, summary)
    return limit_error if limit_error is not None else _registered_result(summary)


async def _tool_write_doc_section(ctx: ToolContext, args: dict[str, Any]) -> str:
    """write_doc_section 实现：校验段存在后登记（含 CAS 基线，不落库）。"""
    parsed = _WriteDocSectionArgs(**args)
    doc = await repository.get_doc(ctx.session, parsed.doc_id)
    if doc is None or doc.project_id != ctx.project_id:
        return _error_result(
            problem=f"记忆文档 {parsed.doc_id} 不存在",
            cause="文档 id 错误，或不属于当前会话的项目（跨项目写入被拒）",
            fix="以文档目录中的 doc_id 重试",
        )
    sections = await repository.list_sections(ctx.session, doc.id)
    section = next((s for s in sections if s.seq == parsed.seq), None)
    if section is None:
        return _error_result(
            problem=f"文档 {doc.id} 不存在第 {parsed.seq} 段",
            cause=f"该文档共 {len(sections)} 段，段号越界",
            fix="以文档目录中的段序号重试",
        )
    payload: dict[str, Any] = {
        "doc_id": doc.id,
        "seq": parsed.seq,
        "content": parsed.content,
        "doc_title": doc.title,
    }
    if parsed.title is not None:
        payload["title"] = parsed.title
    baseline = {"section_id": section.id, "expected_version": section.version}
    summary = f"写入《{doc.title}》第 {parsed.seq} 段「{section.title}」"
    limit_error = await _register_pending(
        ctx, "write_doc_section", payload, summary, baseline=baseline
    )
    return limit_error if limit_error is not None else _registered_result(summary)


_TOOL_IMPLS = {
    "search_entities": _tool_search_entities,
    "get_entity_detail": _tool_get_entity_detail,
    "get_neighborhood": _tool_get_neighborhood,
    "read_doc_section": _tool_read_doc_section,
    "create_entity": _tool_create_entity,
    "update_entity": _tool_update_entity,
    "create_relation": _tool_create_relation,
    "create_memory_doc": _tool_create_memory_doc,
    "write_doc_section": _tool_write_doc_section,
}


async def execute_tool(name: str, arguments: str, ctx: ToolContext) -> str:
    """执行单个工具调用并返回文本结果（失败返回三要素错误文本，不抛异常）。

    作用: 受控 ReAct 的工具出口——参数 JSON 解析失败、未知工具名、写入参数
        白名单校验失败（Pydantic）、工具内部业务失败均折叠为可读文本，
        保证对话轮不被打断。
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
    try:
        return await impl(ctx, args)
    except PydanticValidationError as exc:
        return _error_result(
            problem=f"工具 {name} 的参数未通过白名单校验",
            cause=f"{exc.errors()[:3]}",
            fix="按工具参数说明修正类型/必填项后重试",
        )

"""Agent legacy drafts and confirmed/pending write owner."""

import json
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import context, conversations, documents, llm, repository
from app.agent.models import PendingWrite
from app.agent.schemas import (
    ApproveFailedItem,
    ApproveResponse,
    ApproveResultItem,
    ConfirmFailedItem,
    ConfirmRequest,
    ConfirmResponse,
    ConfirmResultItem,
    DraftItem,
    PendingWriteActionRequest,
    PendingWriteRead,
    ProposeRequest,
    ProposeResponse,
    RejectResponse,
    SectionUpdate,
    generate_draft_id,
)
from app.config import Settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.entities import service as entities_service
from app.relations import service as relations_service

_PROPOSE_RULES = (
    "\n当前任务：根据上面的对话产出写入图谱的结构化草案。只输出一个 JSON 对象：\n"
    '{"drafts": [{"kind": "entity", "payload": {"type": "实体类型", "name": "名称", '
    '"aliases": ["别名"], "description": "简介", "audience_known": false, "properties": {}}, '
    '"summary": "给作者看的一句话说明"}]}。\n'
    "kind 取 entity 或 relation；relation 的 payload 至少含 type/source/target"
    '（source/target 为实体 id）。没有值得写入的内容时输出 {"drafts": []}。'
    "不要输出 JSON 以外的任何文字。"
)


async def propose_drafts(
    db_session: AsyncSession, schema: ProposeRequest, *, settings: Settings
) -> ProposeResponse:
    """生成 legacy JSON 草案；保持既有宽松 draft 与严格 confirm 分工。"""
    conversation = await conversations.load_conversation(db_session, schema.session_id)
    messages = await context.assemble_chat_context(
        db_session,
        conversation,
        perspective=schema.perspective,
        character_id=schema.character_id,
        user_message=schema.message,
        settings=settings,
    )
    system = messages[0]["content"] + _PROPOSE_RULES
    payload = await llm.complete_json(system, messages[1:])
    raw_drafts = payload.get("drafts")
    if not isinstance(raw_drafts, list):
        raise ValidationError(
            problem="LLM 草案缺少 drafts 列表",
            cause=f"JSON 顶层键 drafts 缺失或类型为 {type(raw_drafts).__name__}",
            fix="重试一次；持续失败请简化输入描述",
        )
    drafts: list[DraftItem] = []
    for raw in raw_drafts:
        if not isinstance(raw, dict):
            raise ValidationError(
                problem="LLM 草案项格式非法",
                cause="drafts 中存在非对象元素",
                fix="重试一次；持续失败请简化输入描述",
                detail={"item": str(raw)[:120]},
            )
        kind = raw.get("kind")
        if kind not in ("entity", "relation"):
            raise ValidationError(
                problem="LLM 草案 kind 非法",
                cause=f"kind 必须为 entity/relation，收到 {kind!r}",
                fix="重试一次；持续失败请简化输入描述",
                detail={"item": str(raw)[:120]},
            )
        item_payload = raw.get("payload")
        if not isinstance(item_payload, dict):
            raise ValidationError(
                problem="LLM 草案 payload 非法",
                cause="payload 必须是对象",
                fix="重试一次；持续失败请简化输入描述",
                detail={"item": str(raw)[:120]},
            )
        drafts.append(
            DraftItem(
                draft_id=generate_draft_id(),
                kind=kind,
                payload=item_payload,
                summary=str(raw.get("summary", "")),
            )
        )
    return ProposeResponse(session_id=schema.session_id, drafts=drafts)


def _format_failure(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return f"{exc.problem}；原因：{exc.cause}；修复：{exc.fix}"
    if isinstance(exc, PydanticValidationError):
        return f"草案 payload 未通过服务端校验：{exc.errors()[:3]}"
    return f"落库失败（{type(exc).__name__}），请检查 payload 字段"


@checkpoint
async def confirm_write(db_session: AsyncSession, schema: ConfirmRequest) -> ConfirmResponse:
    """确认 legacy 草案；逐项校验，单项失败不阻断其余项。"""
    created: list[ConfirmResultItem] = []
    failed: list[ConfirmFailedItem] = []
    project_id: str | None = None
    if schema.session_id:
        conversation = await conversations.load_conversation(db_session, schema.session_id)
        project_id = conversation.project_id
    for item in schema.items:
        if not item.confirmed:
            continue
        payload = dict(item.payload)
        if project_id is not None:
            payload["project_id"] = project_id
        try:
            if item.kind == "entity":
                entity = await entities_service.create(
                    db_session, entities_service.EntityCreate(**payload)
                )
                created.append(
                    ConfirmResultItem(
                        draft_id=item.draft_id,
                        kind="entity",
                        target_id=entity.id,
                        name=entity.name,
                    )
                )
            else:
                relation = await relations_service.create(
                    db_session, relations_service.RelationCreate(**payload)
                )
                created.append(
                    ConfirmResultItem(
                        draft_id=item.draft_id,
                        kind="relation",
                        target_id=relation.id,
                        name=f"{relation.type}({relation.source}->{relation.target})",
                    )
                )
        except Exception as exc:  # noqa: BLE001 - contract is per-item failure
            failed.append(ConfirmFailedItem(draft_id=item.draft_id, reason=_format_failure(exc)))
    return ConfirmResponse(created=created, failed=failed)


def _pending_summary(kind: str, payload: dict[str, Any]) -> str:
    if kind == "create_entity":
        return f"新增实体「{payload.get('name', '?')}」（{payload.get('type', '?')}）"
    if kind == "update_entity":
        return f"更新实体「{payload.get('entity_name', payload.get('entity_id', '?'))}」"
    if kind == "create_relation":
        return (
            f"新增关系：{payload.get('source_name', '?')}"
            f" -[{payload.get('type', '?')}]-> {payload.get('target_name', '?')}"
        )
    if kind == "create_memory_doc":
        return f"新建文档「{payload.get('title', '?')}」（{payload.get('kind', '?')}）"
    doc_title = payload.get("doc_title", payload.get("doc_id", "?"))
    return f"写入《{doc_title}》第 {payload.get('seq', '?')} 段"


def pending_read(row: PendingWrite) -> PendingWriteRead:
    payload = json.loads(row.payload_json)
    baseline = json.loads(row.baseline_json) if row.baseline_json else None
    return PendingWriteRead(
        id=row.id,
        conversation_id=row.conversation_id,
        kind=row.kind,
        payload=payload,
        baseline=baseline,
        status=row.status,
        summary=_pending_summary(row.kind, payload),
        created_at=row.created_at,
    )


async def _apply_pending_write(
    db_session: AsyncSession, row: PendingWrite, project_id: str
) -> ApproveResultItem:
    payload = json.loads(row.payload_json)
    if row.kind == "create_entity":
        entity = await entities_service.create(
            db_session,
            entities_service.EntityCreate(
                type=payload.get("type", ""),
                name=payload.get("name", ""),
                description=payload.get("description", ""),
                aliases=list(payload.get("aliases", [])),
                audience_known=bool(payload.get("audience_known", False)),
                properties=dict(payload.get("properties", {})),
                project_id=project_id,
            ),
        )
        return ApproveResultItem(id=row.id, kind=row.kind, target_id=entity.id, name=entity.name)
    if row.kind == "update_entity":
        entity_id = str(payload.get("entity_id", ""))
        if not entity_id:
            raise ValidationError(
                problem="登记载荷缺少 entity_id",
                cause="写入工具登记时的必填键在载荷中缺失（载荷损坏或被篡改）",
                fix="放弃该项登记，由 agent 重新发起",
                detail={"payload": str(payload)[:120]},
            )
        entity = await entities_service.get(db_session, entity_id)
        if entity.project_id != project_id:
            raise ValidationError(
                problem="待更新实体不在会话所属项目",
                cause=f"实体 {entity_id} 归属 {entity.project_id}，会话归属 {project_id}",
                fix="放弃该项登记，在正确的项目会话中重新发起",
                detail={"entity_id": entity_id},
            )
        patch: dict[str, Any] = {}
        for key in ("name", "description", "aliases", "audience_known"):
            if key in payload:
                patch[key] = payload[key]
        if "properties_patch" in payload:
            patch["properties"] = payload["properties_patch"]
        updated = await entities_service.update(
            db_session, entity_id, entities_service.EntityUpdate(**patch)
        )
        return ApproveResultItem(id=row.id, kind=row.kind, target_id=updated.id, name=updated.name)
    if row.kind == "create_relation":
        relation = await relations_service.create(
            db_session,
            relations_service.RelationCreate(
                source=payload.get("source", ""),
                target=payload.get("target", ""),
                type=payload.get("type", ""),
                known_by=list(payload.get("known_by", [])),
                project_id=project_id,
                **{
                    key: payload[key]
                    for key in ("trust", "intimacy", "dependency", "resentment")
                    if key in payload
                },
            ),
        )
        return ApproveResultItem(
            id=row.id,
            kind=row.kind,
            target_id=relation.id,
            name=f"{relation.type}({relation.source}->{relation.target})",
        )
    if row.kind == "create_memory_doc":
        doc_read = await documents.create_doc(
            db_session,
            project_id=project_id,
            kind=str(payload.get("kind", "")),
            title=payload.get("title"),
        )
        return ApproveResultItem(
            id=row.id,
            kind=row.kind,
            target_id=doc_read.id,
            name=doc_read.title,
        )
    baseline = json.loads(row.baseline_json or "{}")
    doc_id = str(payload.get("doc_id", ""))
    doc_row = await repository.get_doc(db_session, doc_id)
    if doc_row is None or doc_row.project_id != project_id:
        raise NotFoundError(
            problem=f"记忆文档 {doc_id} 不存在或不在会话项目",
            cause="文档已删除，或登记后项目归属变化",
            fix="放弃该项登记，重新确认文档状态后由 agent 再次发起",
            detail={"doc_id": doc_id},
        )
    section = await repository.get_section(db_session, baseline.get("section_id", ""))
    if section is None or section.doc_id != doc_row.id:
        raise NotFoundError(
            problem=f"记忆文档《{doc_row.title}》的登记段已不存在",
            cause="段在登记后被删除（文档结构变更）",
            fix="放弃该项登记，由 agent 按新文档目录重新发起",
            detail={"doc_id": doc_row.id, "section_id": baseline.get("section_id")},
        )
    updated_section = await documents.update_section(
        db_session,
        doc_row.id,
        section.id,
        SectionUpdate(
            content=payload.get("content", ""),
            expected_version=int(baseline.get("expected_version", 0)),
            title=payload.get("title"),
        ),
        updated_by="agent",
    )
    return ApproveResultItem(
        id=row.id,
        kind=row.kind,
        target_id=updated_section.id,
        name=f"《{doc_row.title}》第 {updated_section.seq} 段",
    )


@checkpoint
async def approve_pending_writes(
    db_session: AsyncSession, schema: PendingWriteActionRequest
) -> ApproveResponse:
    conversation = await conversations.load_conversation(db_session, schema.conversation_id)
    created: list[ApproveResultItem] = []
    failed: list[ApproveFailedItem] = []
    for pending_id in schema.ids:
        row = await repository.get_pending(db_session, pending_id)
        if row is None or row.conversation_id != conversation.id:
            failed.append(
                ApproveFailedItem(
                    id=pending_id,
                    reason="登记行不存在或不属于该会话（已被清理或归属不符）",
                )
            )
            continue
        if row.status != "pending":
            failed.append(
                ApproveFailedItem(
                    id=pending_id,
                    reason=f"登记行状态为 {row.status}，仅 pending 可确认",
                )
            )
            continue
        try:
            result = await _apply_pending_write(db_session, row, conversation.project_id)
            row.status = "approved"
            await repository.save_pending(db_session, row)
            await db_session.commit()
            created.append(result)
        except Exception as exc:  # noqa: BLE001 - contract is per-item failure
            await db_session.rollback()
            failed.append(ApproveFailedItem(id=pending_id, reason=_format_failure(exc)))
    return ApproveResponse(created=created, failed=failed)


def _pending_not_found(pending_id: str) -> NotFoundError:
    return NotFoundError(
        problem="待写入登记不存在",
        cause=f"登记行 '{pending_id}' 未在库中，或不属于该会话",
        fix="以 done 事件清单 / GET /api/agent/pending-writes 中的 id 重试",
        detail={"pending_id": pending_id},
    )


@checkpoint
async def reject_pending_writes(
    db_session: AsyncSession, schema: PendingWriteActionRequest
) -> RejectResponse:
    conversation = await conversations.load_conversation(db_session, schema.conversation_id)
    rejected: list[str] = []
    for pending_id in schema.ids:
        row = await repository.get_pending(db_session, pending_id)
        if row is None or row.conversation_id != conversation.id:
            raise _pending_not_found(pending_id)
        if row.status == "pending":
            row.status = "rejected"
            await repository.save_pending(db_session, row)
            rejected.append(pending_id)
    await db_session.commit()
    return RejectResponse(rejected=rejected)


@checkpoint
async def list_pending_writes(
    db_session: AsyncSession, conversation_id: str
) -> list[PendingWriteRead]:
    await conversations.load_conversation(db_session, conversation_id)
    rows = await repository.list_pending_by_conversation(db_session, conversation_id)
    return [pending_read(row) for row in rows]
